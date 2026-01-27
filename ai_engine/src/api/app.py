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
  POST   /ai/description         -> generate detailed book description
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
from src.rag.rag_engine_new import RAGEngine
from src.database import get_db, DatabaseConnection
from src.description import BookDescriptionGenerator


def _normalize_filters(filters: Optional[Dict]) -> Optional[Dict]:
    """
    Normalize incoming filter keys to the names expected by SearchEngine.

    Accepts common variants used by clients and converts them to the
    canonical keys used by SearchEngine (title, authors, category, published_year).

    Examples:
      {"year": "2023"} -> {"published_year": "2023"}
      {"author": "Jane"} -> {"authors": "Jane"}
      {"authors": ["A","B"]} -> {"authors": "A, B"}
    """
    if not filters:
        return None

    if not isinstance(filters, dict):
        return None

    f = dict(filters)  # shallow copy

    # map common synonyms
    if "year" in f and "publish_year" not in f:
        f["publish_year"] = f.pop("year")
    if "years" in f and "publish_year" not in f:
        # accept both list or single value
        yrs = f.pop("years")
        if isinstance(yrs, (list, tuple)) and len(yrs) > 0:
            f["publish_year"] = str(yrs[0])
        else:
            f["publish_year"] = str(yrs)
    if "author" in f and "authors" not in f:
        f["authors"] = f.pop("author")

    # normalize authors list -> comma separated string
    if "authors" in f and isinstance(f["authors"], (list, tuple)):
        f["authors"] = ", ".join([str(a).strip() for a in f["authors"] if a])

    # normalize title list -> take first or join
    if "title" in f and isinstance(f["title"], (list, tuple)):
        f["title"] = " ".join([str(t).strip() for t in f["title"] if t])

    # ensure string values for exact-match fields
    for key in ("category", "publish_year", "title", "authors"):
        if key in f and f[key] is not None and not isinstance(f[key], str):
            f[key] = str(f[key])

    return f


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
    """Return a SearchEngine instance. Uses a singleton for the process."""
    with _singletons_lock:
        if "search_engine" not in _singletons:
            logger.info("Initializing SearchEngine (lazy)...")
            _singletons["search_engine"] = SearchEngine()
        return _singletons["search_engine"]


def get_database() -> Any:
    """Return database connection. Uses a singleton for the process."""
    with _singletons_lock:
        if "database" not in _singletons:
            logger.info("Initializing Database connection (lazy)...")
            _singletons["database"] = get_db()
        return _singletons["database"]


def get_rag_engine(top_k=5) -> Any:
    """Return a RAGEngine instance. Uses a singleton for the process."""
    with _singletons_lock:
        if "rag_engine" not in _singletons:
            logger.info("Initializing RAGEngine (lazy)...")
            _singletons["rag_engine"] = RAGEngine(top_k=top_k)
        # Update top_k just in case
        _singletons["rag_engine"].top_k = top_k
        return _singletons["rag_engine"]

def get_description_generator() -> Any:
    """Return a BookDescriptionGenerator instance. Uses a singleton for the process."""
    with _singletons_lock:
        if "description_generator" not in _singletons:
            logger.info("Initializing BookDescriptionGenerator (lazy)...")
            _singletons["description_generator"] = BookDescriptionGenerator()
        return _singletons["description_generator"]


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
    # Normalize filter keys to what SearchEngine expects
    filters = _normalize_filters(filters)
    try:
        se = get_search_engine()
        results = se.search(query=query_text, filters=filters, top_k=top_k)
        # Return the actual count of books found instead of the requested top_k
        actual_count = len(results) if results else 0
        return success({"query": query_text, "top_k": actual_count, "filters": filters, "results": results})
    except Exception as e:
        logger.exception("Search failed for query=%s", query_text)
        return error(str(e), 500)


@app.route("/ai/recommend/<identifier>", methods=["GET"])
def api_recommend(identifier):
    """
    Recommend similar books based on identifier.
    identifier có thể là ISBN hoặc internal book ID.
    """
    try:
        # Convert identifier to string (Vector DB uses string IDs)
        identifier_str = str(identifier)

        se = get_search_engine()
        top_k = int(request.args.get("top_k", 5))

        # Recommend vẫn dùng internal book_id của Vector DB
        # Nếu cần lookup từ ISBN → book_id, implement sau
        recs = se.recommend(book_id=identifier_str, top_k=top_k)

        if not recs:
            return success({
                "identifier": identifier_str,
                "recommendations": [],
                "message": f"Book with identifier '{identifier_str}' not found or no similar books available"
            })

        return success({"identifier": identifier_str, "recommendations": recs})
    except Exception as e:
        logger.exception("Recommend failed for %s", identifier)
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
    Chat endpoint with RAG integration.

    Body JSON:
      {
        "session_id": "<optional - auto-generated if not provided>",
        "message": "<user text - required>",
        "top_k": 5,
        "filters": {
            "category": "AI",          # optional - filter by category (từ FE)
            "authors": "Author Name",  # optional
            "year": "2024"             # optional
        }
      }

    Response:
      {
        "status": "success",
        "message": "ok",
        "data": {
          "session_id": "...",
          "answer": "...",
          "sources": [ {identifier, title, authors, category, publish_year, score, richtext}, ... ],
          "history": [...],
          "intent": "SEARCH|SMALLTALK|FOLLOWUP|STATS|GARBAGE"  # debug info
        }
      }
    """
    payload = request.get_json(silent=True) or {}

    # ===== 1. INPUT VALIDATION =====
    message = (payload.get("message") or "").strip()
    if not message:
        return error("Missing 'message' in body", 400)

    # Validate message length
    if len(message) > 2000:
        return error("Message too long. Maximum 2000 characters allowed.", 400)

    # Sanitize session_id (allow alphanumeric, dash, underscore only)
    session_id = (payload.get("session_id") or "").strip()
    if session_id:
        # Validate session_id format
        import re
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', session_id):
            return error("Invalid session_id format. Use only alphanumeric, dash, underscore (max 64 chars).", 400)
    else:
        session_id = "s_" + uuid.uuid4().hex[:12]

    # ===== 2. PARSE TOP_K =====
    try:
        top_k = int(payload.get("top_k", 5))
        top_k = max(1, min(top_k, 20))  # Clamp between 1 and 20
    except Exception:
        top_k = 5

    # ===== 3. PARSE & NORMALIZE FILTERS (CATEGORY TỪ FE) =====
    filters = payload.get("filters")
    filters = _normalize_filters(filters)

    # Extract category from filters if provided by FE
    category_filter = None
    if filters and filters.get("category"):
        category_filter = filters.get("category")
        logger.info(f"Chat with category filter from FE: {category_filter}")

    # ===== 4. LOAD/CREATE SESSION =====
    session = load_session(session_id)
    append_message(session, "user", message)

    # ===== 5. INITIALIZE RAG ENGINE =====
    try:
        rag = get_rag_engine(top_k=top_k)
    except Exception as e:
        logger.exception("Failed to init RAG Engine")
        return error(f"Failed to init RAG Engine: {e}", 500)

    # ===== 6. GENERATE ANSWER USING RAG =====
    intent = "UNKNOWN"
    results = []

    try:
        # Generate answer with filters (RAG handles intent classification internally)
        answer = rag.generate_answer(question=message, session_id=session_id, filters=filters)

        # Get context sources and intent from RAGEngine session
        rag_session = rag.get_session(session_id)
        results = rag_session.last_search_results if rag_session.last_search_results else []

        # Get intent for debugging/analytics
        intent = rag.classify_intent(message, rag_session)

    except TimeoutError:
        logger.warning("RAG generation timed out for session %s", session_id)
        answer = "⏳ Yêu cầu mất quá nhiều thời gian. Vui lòng thử lại với câu hỏi ngắn hơn."

    except Exception as e:
        logger.exception("RAG generation failed for session %s", session_id)
        answer = "❌ Đã có lỗi xảy ra khi xử lý câu hỏi của bạn. Vui lòng thử lại sau."

    # ===== 7. SAVE TO SESSION =====
    append_message(session, "assistant", answer)

    # ===== 8. BUILD RESPONSE =====
    # Build sources structure to return
    sources = []
    for r in results:
        sources.append({
            "identifier": r.get("identifier"),
            "title": r.get("title"),
            "authors": r.get("authors"),
            "category": r.get("category"),
            "publish_year": r.get("publish_year"),
            "score": round(r.get("score", 0), 4) if r.get("score") else None,
            "richtext": r.get("richtext", "")[:500] if r.get("richtext") else None  # Truncate richtext
        })

    response_data = {
        "session_id": session_id,
        "answer": answer,
        "sources": sources,
        "sources_count": len(sources),
        "history": session["messages"],
        "intent": intent,  # Useful for debugging/analytics
    }

    # Add filters info if provided
    if filters:
        response_data["applied_filters"] = filters

    return success(response_data)


@app.route("/ai/chat/history/<session_id>", methods=["GET"])
def api_chat_history(session_id: str):
    """
    Get chat history for a session.

    Query params:
      - limit: max number of messages to return (default: 50)
      - offset: skip first N messages (default: 0)

    Response:
      {
        "session_id": "...",
        "messages": [...],
        "total_count": 100,
        "has_more": true
      }
    """
    # Validate session_id
    import re
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', session_id):
        return error("Invalid session_id format", 400)

    # Pagination params
    try:
        limit = int(request.args.get("limit", 50))
        limit = max(1, min(limit, 200))  # Clamp between 1 and 200
    except:
        limit = 50

    try:
        offset = int(request.args.get("offset", 0))
        offset = max(0, offset)
    except:
        offset = 0

    session = load_session(session_id)
    if not session or not session.get("messages"):
        return success({
            "session_id": session_id,
            "messages": [],
            "total_count": 0,
            "has_more": False
        })

    all_messages = session.get("messages", [])
    total_count = len(all_messages)
    paginated_messages = all_messages[offset:offset + limit]
    has_more = (offset + limit) < total_count

    return success({
        "session_id": session_id,
        "messages": paginated_messages,
        "total_count": total_count,
        "has_more": has_more,
        "created_at": session.get("created_at")
    })


@app.route("/ai/chat/history/<session_id>", methods=["DELETE"])
def api_chat_history_clear(session_id: str):
    """
    Clear chat history for a session.
    Also clears the RAG session state.
    """
    # Validate session_id
    import re
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', session_id):
        return error("Invalid session_id format", 400)

    # Remove app session file
    path = _session_path(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            logger.error("Failed to remove session file %s: %s", path, e)
            return error("Failed to clear session", 500)

    # Also try to clear RAG session file
    rag_session_path = os.path.join(CHAT_SESSION_DIR, f"rag_{session_id}.json")
    if os.path.exists(rag_session_path):
        try:
            os.remove(rag_session_path)
        except Exception as e:
            logger.warning("Failed to remove RAG session file %s: %s", rag_session_path, e)

    logger.info("Cleared chat session: %s", session_id)
    return success({
        "session_id": session_id,
        "messages": [],
        "cleared": True
    })


@app.route("/ai/chat/sessions", methods=["GET"])
def api_chat_sessions_list():
    """
    List all active chat sessions (admin/debug endpoint).

    Query params:
      - limit: max number of sessions to return (default: 20)

    Response:
      {
        "sessions": [
          {"session_id": "...", "message_count": 10, "created_at": "...", "last_activity": "..."},
          ...
        ],
        "total_count": 50
      }
    """
    try:
        limit = int(request.args.get("limit", 20))
        limit = max(1, min(limit, 100))
    except:
        limit = 20

    sessions_info = []

    try:
        # List all session files
        if os.path.exists(CHAT_SESSION_DIR):
            for filename in os.listdir(CHAT_SESSION_DIR):
                if filename.endswith(".json") and not filename.startswith("rag_"):
                    filepath = os.path.join(CHAT_SESSION_DIR, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            messages = data.get("messages", [])
                            last_activity = messages[-1].get("time") if messages else data.get("created_at")
                            sessions_info.append({
                                "session_id": data.get("id", filename.replace(".json", "")),
                                "message_count": len(messages),
                                "created_at": data.get("created_at"),
                                "last_activity": last_activity
                            })
                    except Exception as e:
                        logger.warning("Failed to read session file %s: %s", filename, e)

        # Sort by last activity (most recent first)
        sessions_info.sort(key=lambda x: x.get("last_activity", ""), reverse=True)

        return success({
            "sessions": sessions_info[:limit],
            "total_count": len(sessions_info)
        })

    except Exception as e:
        logger.exception("Failed to list chat sessions")
        return error(f"Failed to list sessions: {str(e)}", 500)


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


@app.route("/ai/description", methods=["POST"])
def api_description():
    """
    Generate detailed book description from title, authors, and category.

    Request body (JSON):
    {
        "title": "Book Title",
        "authors": "Author Name",
        "category": "Category Name"
    }

    Response:
    {
        "status": "success",
        "message": "ok",
        "data": {
            "title": "Book Title",
            "authors": ["Author Name"],
            "category": "Category",
            "description": "Detailed description (min 2000 chars)",
            "description_length": 2500,
            "source": "google_books" or "template",
            "book_info": {...}
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return error("No JSON data provided", 400)

        title = data.get("title", "").strip()
        authors = data.get("authors", "").strip()
        category = data.get("category", "").strip()

        if not title:
            return error("Title is required", 400)
        if not authors:
            return error("Authors is required", 400)
        if not category:
            return error("Category is required", 400)

        logger.info(f"Generating description for: {title} by {authors} ({category})")

        desc_gen = get_description_generator()
        result = desc_gen.generate_description(
            title=title,
            authors=authors,
            category=category
        )

        if result["status"] == "error":
            return error(result["message"], 500)

        # Chỉ trả về description và description_length
        response_data = {
            "description": result["data"]["description"],
            "description_length": result["data"]["description_length"]
        }

        return success(response_data, message="Description generated successfully")

    except Exception as e:
        logger.exception("Description generation failed")
        return error(f"Failed to generate description: {str(e)}", 500)


# ---- Runner ----
def run(host: str = "0.0.0.0", port: int = 10000, debug: bool = False):
    print(f">>> Starting server at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    host = "0.0.0.0"

    # ⚠️ Render BẮT BUỘC dùng biến PORT
    port = int(os.environ.get("PORT", 10000))

    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")

    run(host=host, port=port, debug=debug)
