import os
import re
import json
import logging
from google import genai
from google.genai import types
from typing import List, Dict

from src.search_engine import SearchEngine
from src.rag.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, LIBRARY_INFO
from config.rag_config import (
    GEMINI_API_KEY,
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


class RAGEngine:
    """
    ========================================================
    🤖 RAGEngine
    --------------------------------------------------------
    Chức năng:
    - Nhận câu hỏi người dùng
    - Phân loại: thống kê / nội quy / follow-up / tìm sách / tổng hợp / fallback
    - Search vector DB
    - Build prompt cho Gemini
    - Cache lại câu hỏi đã hỏi (Query Memory)
    ========================================================
    """

    def __init__(self, top_k: int = DEFAULT_TOP_K):
        # ===============================
        # ️⃣ SEARCH ENGINE (Vector DB + Embedder)
        # ===============================
        self.search_engine = SearchEngine()
        self.embedder = self.search_engine.embedder
        self.vector_db = self.search_engine.vector_db
        self.top_k = top_k

        # Initialize Gemini client
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.last_docs = []  # For follow-up queries

    # ==================================================
    # FILTER GARBAGE QUERIES
    # ==================================================
    def is_garbage_query(self, query: str) -> bool:
        """
        Lọc các câu hỏi rác:
        - Rỗng
        - Quá ngắn
        - Toàn số
        - Không chứa chữ cái
        """
        if not query or not query.strip():
            return True

        q = query.strip().lower()

        if len(q) < MIN_QUERY_LENGTH:
            return True
        if q.isdigit():
            return True

        # Không có chữ cái (kể cả tiếng Việt)
        if not re.search(r"[a-zA-ZÀ-ỹ]", q):
            return True

        return False

    # ==================================================
    # 📊 NHẬN DIỆN CÂU HỎI THỐNG KÊ
    # ==================================================
    def is_library_stats_query(self, question: str) -> bool:
        """
        Ví dụ:
        - "Thư viện có bao nhiêu cuốn sách?"
        - "Tổng số sách là bao nhiêu?"
        """
        q = question.lower()
        return any(k in q for k in [
            "bao nhiêu sách",
            "bao nhiêu cuốn",
            "tổng số sách",
            "số lượng sách",
            "thư viện có bao nhiêu"
        ])

    # ==================================================
    # 🏛️ NHẬN DIỆN CÂU HỎI NỘI QUY / GIỜ GIẤC
    # ==================================================
    def is_library_info_query(self, question: str) -> bool:
        """
        Ví dụ:
        - Mấy giờ mở cửa?
        - Quy định mượn sách?
        - Phí phạt thế nào?
        """
        q = question.lower()
        return any(k in q for k in [
            "mở cửa",
            "đóng cửa",
            "giờ mở",
            "giờ đóng",
            "giờ làm việc",
            "nội quy",
            "quy định",
            "mượn sách",
            "trả sách",
            "gia hạn",
            "phí phạt"
        ])

    # ==================================================
    # 🧠 NHẬN DIỆN FOLLOW-UP QUESTION
    # ==================================================
    def is_followup_query(self, question: str) -> bool:
        """
        Ví dụ:
        - "Cuốn thứ thì sao?"
        - "Cuốn này ai viết?"
        """
        if not self.last_docs:
            return False

        q = question.lower()
        return any(k in q for k in [
            "cuốn này",
            "cuốn đó",
            "cuốn thứ",
            "sách này",
            "sách đó"
        ])

    def answer_followup(self, question: str) -> str:
        """
        Trả lời follow-up dựa trên danh sách sách lần trước
        """
        q = question.lower()
        match = re.search(r"thứ\s*(\d+)", q)

        if not match:
            return "❌ Tôi chưa xác định được cuốn sách bạn đang hỏi."
        idx = int(match.group(1)) - 1

        if 0 <= idx < len(self.last_docs):
            b = self.last_docs[idx]
            return (
                f"📘 **{b['title']}**\n"
                f"- Tác giả: {b['authors']}\n"
                f"- Năm xuất bản: {b['published_year']}\n\n"
                f"{b.get('snippet','')}"
            )

        return "❌ Không tìm thấy cuốn sách bạn yêu cầu."

    # ==================================================
    # 🧠 CÓ CẦN GỌI LLM ĐỂ TỔNG HỢP KHÔNG?
    # ==================================================
    def needs_synthesis(self, question: str) -> bool:
        """
        Nếu chỉ hỏi:
        - "Sách về AI" → chỉ list

        Nếu hỏi:
        - "Nên đọc sách nào?"
        - "So sánh giúp tôi"
        → cần LLM tổng hợp
        """
        q = question.lower()
        return any(k in q for k in [
            "nên",
            "phù hợp",
            "gợi ý",
            "so sánh",
            "đánh giá",
            "phân tích",
            "tổng hợp",
            "giải thích",
            "vì sao",
            "như thế nào"
        ])

    # ==================================================
    # 🎯 LỌC THEO SCORE
    # ==================================================
    def apply_score_threshold(self, docs):
        """
        Nếu document tốt nhất < threshold → coi như không có kết quả
        """
        if not docs:
            return []

        best = max(d.get("score", 0) for d in docs)
        return docs if best >= SCORE_THRESHOLD else []

    # ==================================================
    # 🏛️ BUILD CONTEXT NỘI QUY THƯ VIỆN
    # ==================================================
    def _build_library_context(self) -> dict:
        """
        Convert LIBRARY_INFO thành text cho prompt
        """
        return {
            "opening_hours": LIBRARY_INFO["opening_hours"],
            "library_rules": "\n".join(f"- {r}" for r in LIBRARY_INFO["library_rules"]),
            "borrow_policy": "\n".join(
                f"- {k}: {v}" for k, v in LIBRARY_INFO["borrow_policy"].items()
            ),
            "penalty_policy": "\n".join(
                f"- {k}: {v}" for k, v in LIBRARY_INFO["penalty_policy"].items()
            ),
        }

    # ==================================================
    # 🤖 FALLBACK KHI KHÔNG CÓ DATA
    # ==================================================
    def gemini_fallback(self, question: str) -> str:
        """
        Gọi Gemini trả lời chung chung nhưng:
        - Phải nói rõ là thư viện không có dữ liệu
        - Không được bịa sách
        """
        prompt = f"""
Bạn là trợ lý thư viện AI.

Thư viện KHÔNG có dữ liệu phù hợp cho câu hỏi:
"{question}"

Yêu cầu:
- Nói rõ không có dữ liệu
- KHÔNG bịa tên sách
"""
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_OUTPUT_TOKENS
                )
            )
            return response.text.strip() if response and response.text else "❌ Xin lỗi, tôi không thể trả lời câu hỏi này."
        except Exception as e:
            logger.error(f"Gemini fallback error: {e}")
            return "❌ Xin lỗi, thư viện không có thông tin phù hợp với câu hỏi của bạn."

    # ==================================================
    # GENERATE ANSWER
    # ==================================================
    def generate_answer(self, question: str) -> str:

        # ==================================================
        # ️⃣ CHẶN CÂU HỎI RÁC
        # ==================================================
        if self.is_garbage_query(question):
            return "❌ Câu hỏi không hợp lệ hoặc quá ngắn."

        # ==================================================
        # ️⃣ QUERY MEMORY (CACHE CÂU HỎI CŨ)
        # ==================================================
        q_vec = self.embedder.embed_text(question, is_query=True)

        if q_vec:
            cached = self.vector_db.search_query_memory(
                q_vec, threshold=QUERY_CACHE_THRESHOLD
            )
            if cached:
                logger.info("⚡ Query memory HIT")
                return f"⚡ {cached}"

        # ==================================================
        # ️⃣ THỐNG KÊ
        # ==================================================
        if self.is_library_stats_query(question):
            total = self.vector_db.get_collection_stats().get("count", 0)
            answer = f"📚 Hiện tại thư viện có **{total} cuốn sách** trong hệ thống."

            self.vector_db.add_query_memory(
                question, q_vec, answer, qtype="stats"
            )
            return answer

        # ==================================================
        # ️⃣ NỘI QUY / GIỜ GIẤC
        # ==================================================
        if self.is_library_info_query(question):
            ctx = self._build_library_context()

            prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books="(Không áp dụng)",
    **ctx
)}
"""
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=TEMPERATURE,
                        max_output_tokens=MAX_OUTPUT_TOKENS
                    )
                )
                answer = response.text.strip() if response and response.text else "❌ Không th��� trả lời câu hỏi này."
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                answer = "❌ Không thể trả lời câu hỏi này."

            self.vector_db.add_query_memory(
                question, q_vec, answer, qtype="library_info"
            )
            return answer

        # ==================================================
        # ️⃣ FOLLOW-UP (KHÔNG CACHE)
        # ==================================================
        if self.is_followup_query(question):
            return self.answer_followup(question)

        # ==================================================
        # ️⃣ BOOK RAG PIPELINE
        # ==================================================
        raw_docs = self.search_engine.search(
            query=question,
            top_k=self.top_k * SEARCH_EXPAND_FACTOR
        )

        # Lọc theo score
        docs = self.apply_score_threshold(raw_docs)

        if docs:
            # Lưu lại để dùng cho follow-up
            self.last_docs = docs[:self.top_k]

            # Build danh sách sách
            book_lines = [
                f"{i}. {d['title']} – {d['authors']} ({d['published_year']})"
                for i, d in enumerate(self.last_docs, 1)
            ]

            books_text = "\n".join(book_lines)

            # ==================================================
            # .️⃣ CHỈ LIST, KHÔNG TỔNG HỢP
            # ==================================================
            if not self.needs_synthesis(question):
                answer = f"📚 Danh sách sách liên quan\n\n{books_text}"

                self.vector_db.add_query_memory(
                    question, q_vec, answer, qtype="rag_list"
                )
                return answer

            # ==================================================
            # .️⃣ CÓ GỌI LLM ĐỂ TỔNG HỢP
            # ==================================================
            ctx = self._build_library_context()

            prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books=books_text,
    **ctx
)}
"""
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=TEMPERATURE,
                        max_output_tokens=MAX_OUTPUT_TOKENS
                    )
                )
                synthesis = response.text.strip() if response and response.text else "❌ Không thể tổng hợp thông tin."
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                synthesis = "❌ Không thể tổng hợp thông tin."

            answer = f"""📚 Danh sách sách liên quan

{books_text}

📝 Tổng hợp
{synthesis}
"""
            self.vector_db.add_query_memory(
                question, q_vec, answer, qtype="rag_synthesis"
            )
            return answer

        # ==================================================
        # ️⃣ FALLBACK: KHÔNG CÓ DATA
        # ==================================================
        answer = self.gemini_fallback(question)

        self.vector_db.add_query_memory(
            question, q_vec, answer, qtype="fallback"
        )
        return answer
