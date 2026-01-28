import os
import re
import json
import logging
import uuid
from typing import List, Dict, Optional

from config.settings import settings
from src.search_engine import SearchEngine
from src.rag.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, LIBRARY_INFO
from src.rag.model_manager import ModelManager  # NEW IMPORT
from config.rag_config import (
    GEMINI_API_KEYS, # NEW CONFIG
    GEMINI_MODELS,   # NEW CONFIG
    GEMINI_MODEL,    # Keep for backward compatibility or default
    DEFAULT_TOP_K,
    SCORE_THRESHOLD,
    MIN_QUERY_LENGTH,
    TEMPERATURE,
    MAX_OUTPUT_TOKENS,
    QUERY_CACHE_THRESHOLD,
    SEARCH_EXPAND_FACTOR
)


# Logger cho module RAG
logger = logging.getLogger("RAGEngine")


class ChatSession:
    """
    Lưu trữ trạng thái hội thoại của một user/session.
    Persists to disk to survive restarts.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: List[Dict] = []  # [{"role": "user", "text": "..."}, ...]
        self.last_search_results: List[Dict] = []  # Kết quả tìm sách gần nhất
        self.file_path = os.path.join(settings.DATA_PROCESSED_DIR, "chat_sessions", f"rag_{session_id}.json")
        
    def add_message(self, role: str, text: str):
        self.history.append({"role": role, "text": text})
        # FULL HISTORY: No truncation here anymore!
        # if len(self.history) > 20: ... (REMOVED)
        self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            data = {
                "session_id": self.session_id,
                "history": self.history,
                "last_search_results": self.last_search_results
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session {self.session_id}: {e}")

    def load(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    self.last_search_results = data.get("last_search_results", [])
        except Exception as e:
            logger.error(f"Failed to load session {self.session_id}: {e}")

class RAGEngine:
    """
    ========================================================
    🤖 RAGEngine (Improved)
    --------------------------------------------------------
    Chức năng:
    - Quản lý session chat (Persistent)
    - Phân loại intent (Greeting / Follow-up / Search)
    - RAG flow với context memory
    - Multi-Model Rotation & Rate Limit Handling (NEW)
    ========================================================
    """

    def __init__(self, top_k: int = DEFAULT_TOP_K):
        # 1. SEARCH ENGINE
        self.search_engine = SearchEngine()
        self.embedder = self.search_engine.embedder
        self.vector_db = self.search_engine.vector_db
        self.top_k = top_k

        # 2. Model Manager (replaces single client)
        self.model_manager = ModelManager(
            api_keys=GEMINI_API_KEYS, 
            models=GEMINI_MODELS
        )
        
        # 3. Session storage {session_id: ChatSession}
        self.sessions: Dict[str, ChatSession] = {}

    def get_session(self, session_id: str) -> ChatSession:
        if session_id not in self.sessions:
            session = ChatSession(session_id)
            session.load()  # Try loading from disk
            self.sessions[session_id] = session
        return self.sessions[session_id]

    # ==================================================
    # INTENT CLASSIFICATION
    # ==================================================
    def classify_intent(self, query: str, session: ChatSession) -> str:
        q = query.strip().lower()

        # 1. Garbage check
        if len(q) < 2 or not re.search(r"[a-zA-ZÀ-ỹ0-9]", q):
            return "GARBAGE"

        # 2. Greeting check
        greetings = ["hi", "hello", "chào", "xin chào", "hey", "bạn ơi", "giúp mình"]
        if q in greetings:
            return "GREETING"

        # 3. Follow-up check
        if session.last_search_results:
            followup_keywords = [
                "cuốn này", "cuốn đó", "cuốn thứ", "sách này", "sách đó", 
                "chi tiết", "nó nói về", "tác giả là ai", "giá bao nhiêu"
            ]
            if any(k in q for k in followup_keywords):
                return "FOLLOWUP"
            
            if re.search(r"(cuốn|số|quyển)\s*\d+", q):
                return "FOLLOWUP"

        # 4. Default to SEARCH
        return "SEARCH"

    # ==================================================
    # HANDLERS
    # ==================================================
    def answer_greeting(self) -> str:
        return "👋 Xin chào! Tôi là trợ lý thư viện AI. Tôi có thể giúp gì cho bạn hôm nay? (Tìm sách, hỏi nội quy, v.v...)"

    def answer_followup(self, question: str, session: ChatSession) -> str:
        """Trả lời follow-up dựa trên last_search_results của session"""
        q = question.lower()
        
        # 1. Check for "all" / "summarize all"
        if any(k in q for k in ["tất cả", "cả hai", "cả 2", "cả 3", "mọi cuốn", "những cuốn này", "các cuốn", "hai cuốn", "2 cuốn", "ba cuốn", "3 cuốn"]):
            # Synthesize all books in context
            books_text = "\n".join([
                 f"{i}. {d['title']} – {d['authors']}" for i, d in enumerate(session.last_search_results, 1)
            ])
            ctx = self._build_library_context()
            prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books=books_text, **ctx)}"""
            return self._call_gemini(prompt)

        # 2. Extract specific index (digits or text)
        idx = -1
        
        # Mapping text to number
        text_nums = {
            "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
            "nhất": 1, "nhì": 2, "đầu tiên": 1, "cuối cùng": len(session.last_search_results)
        }
        
        # Regex for text numbers
        text_pattern = r"(thứ|số|cuốn|quyển)\s*(" + "|".join(text_nums.keys()) + r")"
        match_text = re.search(text_pattern, q)
        
        # Regex for digits (flexible: "cuốn 1", "số 1", "1.")
        digit_pattern = r"(?:thứ|số|cuốn|quyển|^)\s*(\d+)"
        match_digit = re.search(digit_pattern, q)

        if match_text:
            key = match_text.group(2)
            idx = text_nums.get(key, 0) - 1
        elif match_digit:
            idx = int(match_digit.group(1)) - 1
            
        # 3. Return info if index valid
        if 0 <= idx < len(session.last_search_results):
            b = session.last_search_results[idx]
            # Use LLM description if simple info return
            return (
                f"📘 **{b['title']}**\n"
                f"- Tác giả: {b['authors']}\n"
                f"- Năm xuất bản: {b['publish_year']}\n"
                f"- Mã sách: {b['identifier']}\n\n"
                f"📝 **Nội dung:**\n{b.get('richtext','')[:1000]}..."
            )

        # Fallback: Ask for clarification
        if session.last_search_results:
            return "Bạn muốn hỏi về cuốn sách số mấy trong danh sách trên? (Ví dụ: 'cuốn số 1', 'quyển đầu tiên', 'tất cả')"
        
        # Should not happen if detected as Followup
        return "❌ Tôi không nhớ chúng ta đang nói về cuốn nào. Bạn hãy tìm kiếm lại nhé."

    def needs_synthesis(self, question: str) -> bool:
        q = question.lower()
        return any(k in q for k in [
            "nên", "phù hợp", "gợi ý", "so sánh", "đánh giá", 
            "phân tích", "tổng hợp", "giải thích", "vì sao", "như thế nào"
        ])

    def _build_library_context(self) -> dict:
        return {
            "opening_hours": LIBRARY_INFO["opening_hours"],
            "library_rules": "\n".join(f"- {r}" for r in LIBRARY_INFO["library_rules"]),
            "borrow_policy": "\n".join(f"- {k}: {v}" for k, v in LIBRARY_INFO["borrow_policy"].items()),
            "penalty_policy": "\n".join(f"- {k}: {v}" for k, v in LIBRARY_INFO["penalty_policy"].items()),
        }

    # ==================================================
    # MAIN GENERATE FUNCTION
    # ==================================================
    def generate_answer(self, question: str, session_id: str = "default") -> Dict:
        """
        Generate answer for a question.
        
        Returns: {
            "answer": str,
            "intent": str,  # GREETING, SEARCH, FOLLOWUP, LIBRARY_INFO, etc.
            "sources": List[Dict]  # Only populated for SEARCH, empty for others
        }
        """
        session = self.get_session(session_id)
        session.add_message("user", question)

        intent = self.classify_intent(question, session)
        logger.info(f"Session: {session_id} | Intent: {intent} | Query: {question}")

        answer = ""
        sources = []  # Only return sources for SEARCH intent
        
        if intent == "GARBAGE":
            answer = "❌ Câu hỏi không hợp lệ hoặc quá ngắn."
        elif intent == "GREETING":
            answer = self.answer_greeting()
        elif intent == "FOLLOWUP":
            answer = self.answer_followup(question, session)
            # Follow-up: don't return sources, user is asking about previous results
        else: 
            if self.is_library_stats_query(question):
                total = self.vector_db.get_collection_stats().get("count", 0)
                answer = f"📚 Hiện tại thư viện có **{total} cuốn sách** trong hệ thống."
            elif self.is_library_info_query(question):
                answer = self._generate_library_info_answer(question)
            else:
                # SEARCH: return answer and sources
                answer, sources = self._perform_book_search(question, session)

        session.add_message("model", answer)
        
        return {
            "answer": answer,
            "intent": intent,
            "sources": sources
        }

    # ==================================================
    # SUB-HANDLERS
    # ==================================================
    def is_library_stats_query(self, q: str) -> bool:
        return any(k in q.lower() for k in ["bao nhiêu sách", "tổng số sách", "số lượng sách"])

    def is_library_info_query(self, q: str) -> bool:
        return any(k in q.lower() for k in ["mở cửa", "quy định", "mượn sách", "trả sách", "phí phạt"])

    def _generate_library_info_answer(self, question: str) -> str:
        ctx = self._build_library_context()
        prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books="(Không áp dụng)", **ctx)}"""
        return self._call_gemini(prompt)

    def _perform_book_search(self, question: str, session: ChatSession) -> tuple:
        """
        Perform book search and return (answer, sources).
        Returns: (answer: str, sources: List[Dict])
        """
        q_vec = self.embedder.embed_text(question, is_query=True)
        if q_vec:
            cached = self.vector_db.search_query_memory(q_vec, threshold=QUERY_CACHE_THRESHOLD)
            if cached:
                logger.info("⚡ Query memory HIT")
                # Cached response: return answer but no sources (can't reconstruct)
                return f"⚡ {cached}", []

        raw_docs = self.search_engine.search(query=question, top_k=self.top_k * SEARCH_EXPAND_FACTOR)
        if not raw_docs: 
            return self._gemini_fallback(question), []
             
        best_score = max(d.get("score", 0) for d in raw_docs)
        if best_score < SCORE_THRESHOLD: 
            return self._gemini_fallback(question), []

        docs = raw_docs[:self.top_k]
        
        # Save to session for follow-up questions
        session.last_search_results = docs
        session.save()

        book_lines = [
            f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
            for i, d in enumerate(docs, 1)
        ]
        books_text = "\n".join(book_lines)

        if not self.needs_synthesis(question):
            answer = f"📚 Danh sách sách liên quan:\n\n{books_text}"
            if q_vec: self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_list")
            return answer, docs

        ctx = self._build_library_context()
        prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books=books_text, **ctx)}"""
        
        synthesis = self._call_gemini(prompt)
        answer = f"📚 Danh sách sách liên quan:\n\n{books_text}\n\n📝 Tổng hợp:\n{synthesis}"
        
        if q_vec: self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_synthesis")
        return answer, docs

    def _gemini_fallback(self, question: str) -> str:
        prompt = f"""Bạn là trợ lý thư viện AI. Thư viện KHÔNG có dữ liệu cho câu hỏi: "{question}". Yêu cầu: Nói rõ không có dữ liệu, KHÔNG bịa tên sách."""
        return self._call_gemini(prompt)

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini via ModelManager (handles rotation & rate limits)"""
        try:
            # New call using ModelManager
            result = self.model_manager.generate_content(
                prompt=prompt,
                temperature=TEMPERATURE,
                max_tokens=MAX_OUTPUT_TOKENS
            )
            return result if result else "❌ Xin lỗi, không có phản hồi."
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "❌ Hệ thống đang bận hoặc gặp sự cố kết nối."
