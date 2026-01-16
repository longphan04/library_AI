#!/usr/bin/env python3
"""
Flask REST API for the ai_engine project using the /ai prefix as requested.

Endpoints:
  GET    /ai/health
  POST   /ai/chat                -> chat with the "AI" (RAG-lite using SearchEngine)
  POST   /ai/search              -> semantic search for books
  GET    /ai/recommend/<book_id> -> recommend similar books
  GET    /ai/filters             -> available filters (categories, years, authors)
  POST   /ai/chat/suggest        -> return starter prompt suggestions for chat
  GET    /ai/chat/history/<sid>  -> load chat history for session
  DELETE /ai/chat/history/<sid>  -> clear chat history for session
  POST   /ai/data/sync           -> trigger data sync/index when new books are added

Notes:
- This file relies on existing project modules (src.search_engine, src.indexer, etc).
- Chat is implemented as a simple RAG-like helper: it retrieves top passages and
  synthesizes a short response by listing relevant titles/snippets. You can replace
  the synthesis part with a real LLM call later.
- Chat sessions are persisted to disk under <DATA_PROCESSED_DIR>/chat_sessions for
  simple persistence across restarts.
"""
import os
import threading
import logging
import uuid
import json
from datetime import datetime
from typing import Any, Dict, Optional, List

from flask import Flask, request, jsonify
from flask_cors import CORS

from config.settings import settings
from src.indexer import Indexer
from src.crawler import GoogleBooksCrawler
from src.data_processor import run_processor
from src.search_engine import SearchEngine
from src.database import get_db, DatabaseConnection


def factory_get_search_engine() -> Any:
    """Factory for SearchEngine.

    Kept as a small abstraction so app wiring can change later without touching
    the singleton accessors.
    """
    return SearchEngine()


def factory_get_database() -> Any:
    """Factory for DB connection.

    Returns a MySQL connection from the project's connection pool.
    """
    return get_db()

# ---- App & logging ----
app = Flask(__name__)
if os.getenv("API_ENABLE_CORS", "true").lower() in ("1", "true", "yes"):
    CORS(app)

logging.basicConfig(
    level=os.getenv("API_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
)
logger = logging.getLogger("ai_engine_api")

# ---- Ensure chat session folder exists ----
CHAT_SESSION_DIR = os.path.join(settings.DATA_PROCESSED_DIR, "chat_sessions")
os.makedirs(CHAT_SESSION_DIR, exist_ok=True)

# ---- Singletons (lazy init) ----
_singletons: Dict[str, Any] = {}
_singletons_lock = threading.Lock()


def get_search_engine() -> Any:
    """Return a SearchEngine instance from the factory. Uses a singleton for the process."""
    with _singletons_lock:
        if "search_engine" not in _singletons:
            logger.info("Initializing SearchEngine via factory (lazy)...")
            _singletons["search_engine"] = factory_get_search_engine()
        return _singletons["search_engine"]


def get_database() -> Any:
    with _singletons_lock:
        if "database" not in _singletons:
            logger.info("Initializing Database via factory (lazy)...")
            _singletons["database"] = factory_get_database()
        return _singletons["database"]


# ---- Job tracking for background tasks ----
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()


def _new_job(job_type: str) -> str:
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": "running",
            "created_at": now,
            "finished_at": None,
            "error": None,
        }
    logger.info("Created job %s (%s)", job_id, job_type)
    return job_id


def _finish_job(job_id: str, ok: bool = True, error: Optional[str] = None):
    now = datetime.utcnow().isoformat() + "Z"
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            logger.warning("Attempted to finish unknown job %s", job_id)
            return
        job["status"] = "completed" if ok else "failed"
        job["finished_at"] = now
        job["error"] = error
    logger.info("Finished job %s: %s", job_id, job["status"])


# ---- Response helpers ----
def success(data: Any = None, message: str = "ok", code: int = 200):
    payload = {"status": "success", "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), code


def error(message: str, code: int = 400):
    payload = {"status": "error", "message": message}
    return jsonify(payload), code


# ---- Utility: chat session persistence ----
def _session_path(session_id: str) -> str:
    safe = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
    return os.path.join(CHAT_SESSION_DIR, f"{safe}.json")


def load_session(session_id: str) -> Dict:
    path = _session_path(session_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load session %s: %s", session_id, e)
    # default new session shape
    return {
        "id": session_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "messages": []  # list of {"role": "user"|"assistant", "text": "...", "time": "..."}
    }


def save_session(session: Dict):
    path = _session_path(session["id"])
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save session %s: %s", session.get("id"), e)


def append_message(session: Dict, role: str, text: str):
    msg = {"role": role, "text": text, "time": datetime.utcnow().isoformat() + "Z"}
    session["messages"].append(msg)
    # keep reasonable history length
    if len(session["messages"]) > 200:
        session["messages"] = session["messages"][-200:]
    save_session(session)


# ---- Routes (prefix /ai) ----
@app.route("/ai/health", methods=["GET"])
def health():
    info = {
        "service": "ai_engine",
        "time": datetime.utcnow().isoformat() + "Z",
        "paths": {
            "BASE_DIR": settings.BASE_DIR,
            "DATA_RAW_DIR": settings.DATA_RAW_DIR,
            "DATA_PROCESSED_DIR": settings.DATA_PROCESSED_DIR,
            "DATA_RICH_TEXT_DIR": settings.DATA_RICH_TEXT_DIR,
            "VECTOR_DB_DIR": settings.VECTOR_DB_DIR,
        },
        "env": {
            "GOOGLE_API_KEY_SET": bool(settings.GOOGLE_API_KEY),
        },
    }
    return success(info)


@app.route("/ai/search", methods=["POST"])
def api_search():
    """
    Body JSON:
    { "query": "<text>", "top_k": 10, "filters": { ... } }
    """
    payload = request.get_json(silent=True) or {}
    query_text = (payload.get("query") or "").strip()
    if not query_text:
        return error("Missing 'query' in request body", 400)

    try:
        top_k = int(payload.get("top_k", 10))
    except Exception:
        return error("'top_k' must be integer", 400)

    filters = payload.get("filters")
    try:
        se = get_search_engine()
        results = se.search(query=query_text, filters=filters, top_k=top_k)
        return success({"query": query_text, "top_k": top_k, "filters": filters, "results": results})
    except Exception as e:
        logger.exception("Search failed for query=%s", query_text)
        return error(str(e), 500)


@app.route("/ai/recommend/<book_id>", methods=["GET"])
def api_recommend(book_id: str):
    try:
        se = get_search_engine()
        recs = se.recommend(book_id=book_id, top_k=int(request.args.get("top_k", 5)))
        return success({"book_id": book_id, "recommendations": recs})
    except Exception as e:
        logger.exception("Recommend failed for %s", book_id)
        return error(str(e), 500)


@app.route("/ai/filters", methods=["GET"])
def api_filters():
    try:
        se = get_search_engine()
        filters = se.get_filters()
        return success(filters)
    except Exception as e:
        logger.exception("Filters failed")
        return error(str(e), 500)


@app.route("/ai/chat/suggest", methods=["POST"])
def api_chat_suggest():
    """
    Provide starter prompt suggestions for chat.
    Body optional:
      { "context": "<optional user text>", "max": 5 }
    """
    payload = request.get_json(silent=True) or {}
    context = (payload.get("context") or "").strip()
    max_items = int(payload.get("max", 5))
    # Try to make suggestions based on top categories if possible
    try:
        se = get_search_engine()
        filters = se.get_filters()
        categories = filters.get("categories", [])[:5]
        suggestions = []
        if context:
            suggestions.append(context)
        # Build suggestions from categories
        for c in categories:
            suggestions.append(f"Tìm sách về {c}")
            if len(suggestions) >= max_items:
                break
        # Add fallback examples
        examples = [
            "Tìm sách IT?",
            "Sách mới nhất?",
            "Sách cho người mới học Python?",
            "Sách hay về trí tuệ nhân tạo?"
        ]
        for ex in examples:
            if len(suggestions) >= max_items:
                break
            if ex not in suggestions:
                suggestions.append(ex)
        return success({"suggestions": suggestions[:max_items]})
    except Exception as e:
        logger.exception("chat suggest failed")
        # fallback static suggestions
        return success({"suggestions": ["Tìm sách IT?", "Sách mới nhất?", "Sách cho người mới học Python?"]})


@app.route("/ai/chat", methods=["POST"])
def api_chat():
    """
    Minimal chat endpoint (RAG-lite).
    Body JSON:
      {
        "session_id": "<optional>",
        "message": "<user text>",
        "top_k": 5,
        "filters": { ... }   # optional, forwarded to search
      }
    Response:
      {
        "session_id": "...",
        "answer": "...",
        "sources": [ {id, title, authors, snippet, score}, ... ],
        "history": [...]
      }
    """
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return error("Missing 'message' in body", 400)

    session_id = (payload.get("session_id") or "").strip()
    if not session_id:
        session_id = "s_" + uuid.uuid4().hex[:12]

    session = load_session(session_id)
    append_message(session, "user", message)

    try:
        top_k = int(payload.get("top_k", 5))
    except Exception:
        top_k = 5
    filters = payload.get("filters")

    # 1) Retrieve top passages/books using semantic search
    try:
        se = get_search_engine()
        results = se.search(query=message, filters=filters, top_k=top_k)
    except Exception as e:
        logger.exception("Search during chat failed")
        results = []

    # 2) Synthesize a short answer (simple rule-based RAG)
    #    For now create an answer that lists top titles and a suggested next action.
    if results:
        titles = [f"{r.get('title','Unknown')} (score={r.get('score',0)})" for r in results]
        snippets = [r.get("snippet","") for r in results]
        # Build short answer
        answer_lines = []
        answer_lines.append("Mình tìm thấy một số cuốn liên quan:")
        for i, r in enumerate(results[:5], start=1):
            t = r.get("title", "Unknown")
            a = r.get("authors", "")
            cat = r.get("category", "")
            snippet = r.get("snippet", "")
            answer_lines.append(f"{i}. {t} — {a} [{cat}]")
            if snippet:
                # include short snippet
                answer_lines.append(f"   \"{snippet[:180]}...\"")
        answer_lines.append("")
        answer_lines.append("Bạn muốn mình trả kết quả chi tiết hơn, gợi ý sách tương tự, hay lưu vào danh sách?")
        answer = "\n".join(answer_lines)
    else:
        answer = "Mình không tìm thấy kết quả phù hợp. Bạn muốn mình thử tìm rộng hơn hoặc gợi ý thể loại?"

    append_message(session, "assistant", answer)

    # Save session (already saved in append_message)
    # Build sources structure to return
    sources = []
    for r in results:
        sources.append({
            "id": r.get("id"),
            "title": r.get("title"),
            "authors": r.get("authors"),
            "category": r.get("category"),
            "published_year": r.get("published_year"),
            "score": r.get("score"),
            "snippet": r.get("snippet")
        })

    return success({
        "session_id": session_id,
        "answer": answer,
        "sources": sources,
        "history": session["messages"]
    })


@app.route("/ai/chat/history/<session_id>", methods=["GET"])
def api_chat_history(session_id: str):
    session = load_session(session_id)
    if not session or not session.get("messages"):
        return success({"session_id": session_id, "messages": []})
    return success({"session_id": session_id, "messages": session["messages"]})


@app.route("/ai/chat/history/<session_id>", methods=["DELETE"])
def api_chat_history_clear(session_id: str):
    path = _session_path(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            logger.error("Failed to remove session file %s: %s", path, e)
            return error("Failed to clear session", 500)
    # ensure removed from disk and return empty session
    return success({"session_id": session_id, "messages": []})


@app.route("/ai/data/sync", methods=["POST"])
def api_data_sync():
    """
    Trigger data sync when new books added.
    Body JSON: { "action": "index" | "process" | "crawl" | "all" }
    Default: "index"
    """
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "index").strip().lower()
    allowed = {"index", "process", "crawl", "all"}
    if action not in allowed:
        return error("Invalid action. Allowed: index, process, crawl, all", 400)

    if action == "crawl" and not settings.GOOGLE_API_KEY:
        return error("GOOGLE_API_KEY not set; cannot crawl", 400)

    # For convenience, accept "all" meaning process -> index
    job_type = "index" if action in ("index",) else action

    job_id = _new_job(f"data_sync:{action}")

    def _worker(jid: str, act: str):
        try:
            if act in ("process", "all"):
                # run processor
                run_processor()
            if act in ("index", "all", "process"):
                # run indexer (index rich text)
                idx = Indexer()
                idx.run_indexing()
                # invalidate cache
                try:
                    se = get_search_engine()
                    if hasattr(se, "invalidate_cache"):
                        se.invalidate_cache()
                except Exception:
                    logger.debug("Could not invalidate cache")
            if act == "crawl":
                crawler = GoogleBooksCrawler()
                crawler.run()
            _finish_job(jid, ok=True)
        except Exception as e:
            logger.exception("Data sync worker failed for %s: %s", act, e)
            _finish_job(jid, ok=False, error=str(e))

    t = threading.Thread(target=_worker, args=(job_id, action), daemon=True)
    t.start()
    return success({"job_id": job_id, "action": action}, code=202)


@app.route("/ai/jobs", methods=["GET"])
def list_jobs():
    with jobs_lock:
        all_jobs = list(jobs.values())
    all_jobs_sorted = sorted(all_jobs, key=lambda j: j["created_at"], reverse=True)
    return success({"jobs": all_jobs_sorted})


@app.route("/ai/jobs/<job_id>", methods=["GET"])
def job_detail(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return error("Job not found", 404)
    return success(job)


# ---- Runner ----
def run(host: str = "0.0.0.0", port: int = 9999, debug: bool = False):
    logger.info("Starting API on %s:%s (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "9999"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    run(host=host, port=port, debug=debug)