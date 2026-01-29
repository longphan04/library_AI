"""
=====================================================
RAG ENGINE - MERGED VERSION
=====================================================
Giữ lại: origin/main (Session persistent, ModelManager)
Thêm từ HEAD:
1. Smalltalk detection chi tiết (tiếng Việt có/không dấu)
2. _is_book_related_query() để skip cache thông minh
3. Prompt templates cho smalltalk và general QA
=====================================================
"""

import os
import re
import json
import logging
from typing import List, Dict

from config.settings import settings
from src.search_engine import SearchEngine
from src.rag.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, LIBRARY_INFO
from src.rag.model_manager import ModelManager
from config.rag_config import (
    GEMINI_API_KEYS,
    GEMINI_MODELS,
    GEMINI_MODEL,
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


# =====================================================
# 💬 PROMPT TEMPLATES (THÊM TỪ HEAD)
# =====================================================
# Lý do: Các template này giúp Gemini trả lời thông minh hơn
# cho các trường hợp smalltalk và câu hỏi tổng quát

SMALLTALK_PROMPT_TEMPLATE = """
Bạn là trợ lý AI thân thiện của thư viện.

Lịch sử hội thoại:
{history}

Người dùng nói: "{question}"

Hãy trả lời một cách thân thiện, tự nhiên bằng tiếng Việt.
- Nếu là lời chào: chào lại và giới thiệu ngắn gọn bạn có thể giúp tìm sách, tra cứu thông tin thư viện
- Nếu là cảm ơn: đáp lại lịch sự và hỏi có cần giúp gì thêm không
- Nếu là tạm biệt: chào tạm biệt thân thiện
- Nếu hỏi về bạn: giới thiệu bạn là trợ lý AI thư viện
- Nếu là câu hỏi chung: trả lời ngắn gọn, thông minh

Trả lời ngắn gọn (1-3 câu), thân thiện, có thể dùng emoji phù hợp.
KHÔNG đưa ra danh sách sách nếu không được hỏi.
"""

GENERAL_QA_PROMPT_TEMPLATE = """
Bạn là trợ lý AI thông minh của thư viện.

Lịch sử hội thoại gần đây:
{history}

Câu hỏi của người dùng: "{question}"

Hướng dẫn trả lời:
1. Nếu là câu hỏi kiến thức chung (toán, khoa học, lịch sử, v.v.): Trả lời chính xác, ngắn gọn
2. Nếu là câu hỏi về sách nhưng thư viện không có: Nói rõ thư viện chưa có sách phù hợp
3. Nếu là câu hỏi cá nhân hoặc không phù hợp: Nhẹ nhàng từ chối và hướng về chức năng thư viện
4. Nếu là câu hỏi tiếp nối: Dựa vào lịch sử để trả lời chính xác

Trả lời bằng tiếng Việt, thân thiện, chính xác. Có thể dùng emoji phù hợp.
KHÔNG bịa tên sách hoặc thông tin không chính xác.
"""

FOLLOWUP_PROMPT_TEMPLATE = """
Bạn là TRỢ LÝ THƯ VIỆN AI thông minh.

============================
Lịch sử hội thoại:
============================
{history}

============================
Danh sách sách đã đề cập trước đó:
============================
{previous_books}

============================
Câu hỏi tiếp theo của người dùng:
============================
{question}

============================
Hướng dẫn trả lời:
============================
1. Đây là câu hỏi TIẾP NỐI, hãy dựa vào ngữ cảnh trước đó
2. Nếu hỏi "cuốn nào hay/dễ/tốt nhất" → chọn từ danh sách sách đã đề cập và giải thích lý do
3. Nếu hỏi "cuốn thứ X" → tham chiếu đến vị trí trong danh sách
4. Nếu hỏi chi tiết về một cuốn → cung cấp thông tin có sẵn
5. Trả lời tự nhiên, thân thiện, có thể dùng emoji
6. KHÔNG bịa thông tin không có
"""


class ChatSession:
    """
    Lưu trữ trạng thái hội thoại của một user/session.
    Persists to disk to survive restarts.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: List[Dict] = []
        self.last_search_results: List[Dict] = []
        self.file_path = os.path.join(
            settings.DATA_PROCESSED_DIR,
            "chat_sessions",
            f"rag_{session_id}.json"
        )

    def add_message(self, role: str, text: str):
        self.history.append({"role": role, "text": text})
        self.save()

    def get_history_text(self, max_turns: int = 8) -> str:
        """Chuyển history thành text cho prompt (THÊM TỪ HEAD)"""
        if not self.history:
            return "(chưa có lịch sử)"
        lines = []
        for h in self.history[-max_turns:]:
            prefix = "Người dùng" if h["role"] == "user" else "Trợ lý"
            lines.append(f"{prefix}: {h['text']}")
        return "\n".join(lines)

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
    🤖 RAGEngine (Merged Version)
    --------------------------------------------------------
    Chức năng:
    - Quản lý session chat (Persistent)
    - Phân loại intent thông minh (THÊM: Smalltalk chi tiết)
    - RAG flow với context memory
    - Multi-Model Rotation & Rate Limit Handling
    ========================================================
    """

    def __init__(self, top_k: int = DEFAULT_TOP_K):
        # 1. SEARCH ENGINE
        self.search_engine = SearchEngine()
        self.embedder = self.search_engine.embedder
        self.vector_db = self.search_engine.vector_db
        self.top_k = top_k

        # 2. Model Manager (multi-key rotation)
        self.model_manager = ModelManager(
            api_keys=GEMINI_API_KEYS,
            models=GEMINI_MODELS
        )

        # 3. Session storage {session_id: ChatSession}
        self.sessions: Dict[str, ChatSession] = {}

    def get_session(self, session_id: str) -> ChatSession:
        if session_id not in self.sessions:
            session = ChatSession(session_id)
            session.load()
            self.sessions[session_id] = session
        return self.sessions[session_id]

    # ==================================================
    # 🆕 SMALLTALK DETECTION (THÊM TỪ HEAD)
    # ==================================================
    # Lý do thêm: Phiên bản HEAD có nhận diện smalltalk chi tiết hơn,
    # hỗ trợ cả tiếng Việt có dấu và không dấu, giúp bot phản hồi
    # chính xác hơn khi user chào hỏi

    def is_smalltalk(self, question: str) -> bool:
        """
        Nhận diện câu hỏi smalltalk / chào hỏi.
        Hỗ trợ cả tiếng Việt có dấu và không dấu.
        """
        q = question.lower().strip()
        q = re.sub(r'[?.!,;:]', '', q)

        smalltalk_keywords = [
            # Chào hỏi có dấu
            "xin chào", "chào bạn", "chào", "chào buổi sáng", "chào buổi tối",
            # Chào hỏi không dấu
            "xin chao", "chao ban", "chao", "chao buoi sang", "chao buoi toi",
            # Tiếng Anh
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
            # Cảm ơn có dấu
            "cảm ơn", "cám ơn", "cảm ơn bạn", "cám ơn bạn",
            # Cảm ơn không dấu
            "cam on", "cam on ban",
            # Tiếng Anh
            "thank", "thanks", "thank you", "tks", "ty",
            # Tạm biệt có dấu
            "tạm biệt", "hẹn gặp lại", "gặp lại sau",
            # Tạm biệt không dấu
            "tam biet", "hen gap lai", "gap lai sau",
            # Tiếng Anh
            "bye", "goodbye", "see you", "see ya",
            # Hỏi thăm có dấu
            "bạn là ai", "tên gì", "khỏe không", "bạn ổn không", "bạn có khỏe không",
            # Hỏi thăm không dấu
            "ban la ai", "ten gi", "khoe khong", "ban on khong", "ban co khoe khong",
            # Hỏi thăm tiếng Anh
            "how are you", "what's up", "who are you", "what is your name",
            # Các câu đơn giản
            "alo", "yo", "hii", "hiii", "helloo", "helo"
        ]

        if q in smalltalk_keywords:
            return True
        return any(k in q for k in smalltalk_keywords)

    def answer_smalltalk(self, question: str, session: ChatSession) -> str:
        """
        Dùng Gemini trả lời smalltalk thông minh (THÊM TỪ HEAD)
        Lý do: Thay vì trả lời cứng, dùng LLM để trả lời tự nhiên hơn
        """
        prompt = SMALLTALK_PROMPT_TEMPLATE.format(
            history=session.get_history_text(),
            question=question
        )
        return self._call_gemini(prompt, temperature=0.7, max_tokens=150)

    # ==================================================
    # 🆕 BOOK RELATED CHECK (THÊM TỪ HEAD)
    # ==================================================
    # Lý do thêm: Giúp skip cache sách khi user hỏi câu không liên quan sách
    # Ví dụ: "xin chào" không nên hit cache có danh sách sách

    def _is_book_related_query(self, question: str) -> bool:
        """
        Kiểm tra xem câu hỏi có liên quan đến việc tìm/hỏi về sách không.
        Dùng để quyết định có nên dùng cache sách hay không.
        """
        q = question.lower()
        q = re.sub(r'[?.!,;:]', '', q)

        book_keywords = [
            # Từ khóa sách tiếng Việt
            "sách", "cuốn", "quyển", "tài liệu", "giáo trình", "truyện",
            "tiểu thuyết", "tác phẩm", "ebook", "pdf",
            # Từ khóa sách không dấu
            "sach", "cuon", "quyen", "tai lieu", "giao trinh", "truyen",
            "tieu thuyet", "tac pham",
            # Từ khóa tìm kiếm
            "tìm", "tìm kiếm", "gợi ý", "đề xuất", "cho tôi", "có không",
            "tim", "tim kiem", "goi y", "de xuat", "cho toi", "co khong",
            # Thể loại sách
            "python", "java", "programming", "lập trình", "lap trinh",
            "machine learning", "ai", "deep learning", "data science",
            "toán", "văn", "lịch sử", "địa lý", "vật lý", "hóa học",
            "toan", "van", "lich su", "dia ly", "vat ly", "hoa hoc",
            # Tiếng Anh
            "book", "novel", "textbook", "recommend", "find", "search"
        ]

        return any(k in q for k in book_keywords)

    # ==================================================
    # INTENT CLASSIFICATION (CẢI TIẾN)
    # ==================================================
    def classify_intent(self, query: str, session: ChatSession) -> str:
        q = query.strip().lower()

        # 1. Garbage check
        if len(q) < 2 or not re.search(r"[a-zA-Z\u00c0-\u1ef90-9]", q):
            return "GARBAGE"

        # 1b. Library stats check (NEW): ưu tiên cao, tránh bị search sách
        if self.is_library_stats_query(query):
            return "STATS"

        # 2. Smalltalk check
        if self.is_smalltalk(query):
            return "SMALLTALK"

        # 3. Follow-up check
        if session.last_search_results:
            followup_keywords = [
                "cuốn này", "cuốn đó", "cuốn thứ", "sách này", "sách đó",
                "chi tiết", "nó nói về", "tác giả là ai", "giá bao nhiêu",
                "trong số", "cuốn nào", "cái nào", "dễ học", "tốt nhất",
                "phù hợp", "nên chọn", "ở trên", "vừa rồi", "trong danh sách"
            ]
            if any(k in q for k in followup_keywords):
                return "FOLLOWUP"
            if re.search(r"(cuốn|số|quyển)\s*\d+", q):
                return "FOLLOWUP"

        # 4. Default
        return "SEARCH"

    def is_library_stats_query(self, q: str) -> bool:
        ql = q.lower()
        # Bổ sung thêm mẫu hỏi phổ biến
        return any(k in ql for k in [
            "bao nhiêu cuốn sách",
            "bao nhiêu quyển sách",
            "bao nhiêu sách",
            "tổng số sách",
            "số lượng sách",
            "thư viện có bao nhiêu",
            "hiện có bao nhiêu",
        ])

    def _normalize_book_query(self, question: str) -> str:
        """Chuẩn hoá một số câu gợi ý để search trúng chủ đề hơn."""
        q = question.strip()
        ql = q.lower()

        # Nếu user hỏi kiểu: "Sách Machine Learning hay nhất" → thêm từ khoá 'sách'
        if "machine learning" in ql and "sách" in ql:
            return "sách machine learning"

        # "Tìm sách về Python" hay "sách python" → chuẩn hoá
        if "python" in ql and ("tìm" in ql or "sách" in ql):
            return "sách python"

        return q

    # ==================================================
    # HANDLERS
    # ==================================================
    def answer_greeting(self) -> str:
        return "👋 Xin chào! Tôi là trợ lý thư viện AI. Tôi có thể giúp gì cho bạn hôm nay? (Tìm sách, hỏi nội quy, v.v...)"

    def answer_followup(self, question: str, session: ChatSession) -> str:
        """Trả lời follow-up dựa trên last_search_results của session"""
        q = question.lower()

        # 1. Check for "all" / "summarize all"
        if any(k in q for k in ["tất cả", "cả hai", "cả 2", "cả 3", "mọi cuốn", "những cuốn này", "các cuốn"]):
            books_text = "\n".join([
                f"{i}. {d['title']} – {d['authors']}"
                for i, d in enumerate(session.last_search_results, 1)
            ])
            # THÊM: Dùng FOLLOWUP_PROMPT_TEMPLATE thay vì prompt cứng
            prompt = FOLLOWUP_PROMPT_TEMPLATE.format(
                history=session.get_history_text(),
                previous_books=books_text,
                question=question
            )
            return self._call_gemini(prompt)

        # 2. Extract specific index
        idx = -1
        text_nums = {
            "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
            "nhất": 1, "nhì": 2, "đầu tiên": 1,
            "cuối cùng": len(session.last_search_results)
        }

        text_pattern = r"(thứ|số|cuốn|quyển)\s*(" + "|".join(text_nums.keys()) + r")"
        match_text = re.search(text_pattern, q)
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
            return (
                f"📘 **{b['title']}**\n"
                f"- Tác giả: {b['authors']}\n"
                f"- Năm xuất bản: {b['publish_year']}\n"
                f"- Mã sách: {b['identifier']}\n\n"
                f"📝 **Nội dung:**\n{b.get('richtext','')[:1000]}..."
            )

        # 4. THÊM: Dùng LLM để trả lời follow-up phức tạp (từ HEAD)
        if session.last_search_results:
            books_text = "\n".join([
                f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
                for i, d in enumerate(session.last_search_results, 1)
            ])
            prompt = FOLLOWUP_PROMPT_TEMPLATE.format(
                history=session.get_history_text(),
                previous_books=books_text,
                question=question
            )
            return self._call_gemini(prompt)

        return "Bạn muốn hỏi về cuốn sách số mấy? (Ví dụ: 'cuốn số 1', 'quyển đầu tiên')"

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
    # MAIN GENERATE FUNCTION (CẢI TIẾN)
    # ==================================================
    def generate_answer(self, question: str, session_id: str = "default", filters: dict = None) -> str:
        """
        Generate answer for a chat question.

        Args:
            question: User's question
            session_id: Session identifier for conversation context
            filters: Optional filters from FE (category, authors, year, etc.)

        Returns:
            AI-generated answer string
        """
        session = self.get_session(session_id)
        session.add_message("user", question)

        intent = self.classify_intent(question, session)
        logger.info(f"Session: {session_id} | Intent: {intent} | Query: {question} | Filters: {filters}")

        answer = ""

        if intent == "GARBAGE":
            answer = "❌ Câu hỏi không hợp lệ hoặc quá ngắn."

        elif intent == "SMALLTALK":
            answer = self.answer_smalltalk(question, session)

        elif intent == "FOLLOWUP":
            answer = self.answer_followup(question, session)

        elif intent == "STATS":
            total = self.vector_db.get_collection_stats().get("count", 0)
            answer = f"📚 Hiện tại thư viện có **{total} cuốn sách** trong hệ thống."

        else:  # SEARCH
            if self.is_library_info_query(question):
                answer = self._generate_library_info_answer(question, session)
            else:
                # Normalize topic queries và truyền filters từ FE
                normalized_query = self._normalize_book_query(question)
                answer = self._perform_book_search(normalized_query, session, filters=filters)

        session.add_message("model", answer)
        return answer

    # ==================================================
    # SUB-HANDLERS
    # ==================================================
    def is_library_info_query(self, q: str) -> bool:
        return any(k in q.lower() for k in ["mở cửa", "quy định", "mượn sách", "trả sách", "phí phạt"])

    def _generate_library_info_answer(self, question: str, session: ChatSession) -> str:
        ctx = self._build_library_context()
        prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books="(Không áp dụng)", **ctx)}"""
        return self._call_gemini(prompt)

    def _perform_book_search(self, question: str, session: ChatSession, filters: dict = None) -> str:
        q_vec = self.embedder.embed_text(question, is_query=True)

        # THÊM: Smart cache skip (từ HEAD)
        # Skip cache nếu có filters (để đảm bảo kết quả chính xác)
        if q_vec and not filters:
            cached = self.vector_db.search_query_memory(q_vec, threshold=QUERY_CACHE_THRESHOLD)
            if cached:
                # Skip cache nếu cache là sách nhưng query không liên quan sách
                is_book_cache = "📚" in cached or "Danh sách sách" in cached
                if is_book_cache and not self._is_book_related_query(question):
                    logger.info("⚠️ Query memory SKIP (cached books for non-book query)")
                else:
                    logger.info("⚡ Query memory HIT")
                    return f"⚡ {cached}"

        # Search với filters nếu được cung cấp
        raw_docs = self.search_engine.search(query=question, filters=filters, top_k=self.top_k * SEARCH_EXPAND_FACTOR)
        if not raw_docs:
            return self._gemini_fallback(question, session)

        best_score = max(d.get("score", 0) for d in raw_docs)
        if best_score < SCORE_THRESHOLD:
            return self._gemini_fallback(question, session)

        docs = raw_docs[:self.top_k]

        session.last_search_results = docs
        session.save()

        book_lines = [
            f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
            for i, d in enumerate(docs, 1)
        ]
        books_text = "\n".join(book_lines)

        if not self.needs_synthesis(question):
            answer = f"📚 Danh sách sách liên quan:\n\n{books_text}"
            if q_vec:
                self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_list")
            return answer

        ctx = self._build_library_context()
        prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books=books_text, **ctx)}"""

        synthesis = self._call_gemini(prompt)
        answer = f"📚 Danh sách sách liên quan:\n\n{books_text}\n\n📝 Tổng hợp:\n{synthesis}"

        if q_vec:
            self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_synthesis")
        return answer

    def _gemini_fallback(self, question: str, session: ChatSession) -> str:
        """THÊM: Dùng GENERAL_QA_PROMPT_TEMPLATE để trả lời thông minh hơn (từ HEAD)"""
        prompt = GENERAL_QA_PROMPT_TEMPLATE.format(
            history=session.get_history_text(),
            question=question
        )
        return self._call_gemini(prompt)

    def _call_gemini(self, prompt: str, temperature: float = None, max_tokens: int = None) -> str:
        """Call Gemini via ModelManager (handles rotation & rate limits)"""
        try:
            result = self.model_manager.generate_content(
                prompt=prompt,
                temperature=temperature or TEMPERATURE,
                max_tokens=max_tokens or MAX_OUTPUT_TOKENS
            )
            return result if result else "❌ Xin lỗi, không có phản hồi."
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "❌ Hệ thống đang bận hoặc gặp sự cố kết nối."

    # ==================================================
    # 🆕 SUGGESTED QUESTIONS (THÊM TỪ HEAD)
    # ==================================================
    def get_suggested_questions(self) -> List[str]:
        """Danh sách gợi ý mặc định cho giao diện chat"""
        return [
            "Thư viện mở cửa lúc mấy giờ?",
            "Làm sao để gia hạn sách?",
            "Có sách nào về trí tuệ nhân tạo không?",
            "Phí phạt trả sách trễ là bao nhiêu?",
        ]