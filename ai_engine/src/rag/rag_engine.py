import os
import re
import json
import logging
import google.genai as genai
from typing import List, Dict

from ..search_engine import SearchEngine
from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, LIBRARY_INFO

# ==========================
# CONFIG
# ==========================
DEFAULT_TOP_K = 5
SEARCH_EXPAND_FACTOR = 3
SCORE_THRESHOLD = 0.80

logger = logging.getLogger("RAGEngine")


class RAGEngine:
    def __init__(self, top_k: int = DEFAULT_TOP_K):
        self.search_engine = SearchEngine()
        self.top_k = top_k

        # Gemini client (stable)
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

        # Memory cho follow-up
        self.last_docs: List[Dict] = []

    # ==================================================
    # 🔧 GEMINI HELPER (STABLE – NO CONFIG)
    # ==================================================
    def _genai_generate(self, prompt: str) -> str:
        resp = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return resp.text.strip() if resp and resp.text else ""

    # ==================================================
    # 🚫 GARBAGE FILTER
    # ==================================================
    def is_garbage_query(self, query: str) -> bool:
        if not query or not query.strip():
            return True
        q = query.strip().lower()
        if len(q) < 3:
            return True
        if q.isdigit():
            return True
        if not re.search(r"[a-zA-ZÀ-ỹ]", q):
            return True
        return False

    # ==================================================
    # 📊 THỐNG KÊ THƯ VIỆN
    # ==================================================
    def is_library_stats_query(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "bao nhiêu sách",
            "bao nhiêu cuốn",
            "tổng số sách",
            "số lượng sách",
            "thư viện có bao nhiêu"
        ]
        return any(k in q for k in keywords)

    # ==================================================
    # 🏛️ THÔNG TIN THƯ VIỆN
    # ==================================================
    def is_library_info_query(self, question: str) -> bool:
        q = question.lower()
        keywords = [
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
        ]
        return any(k in q for k in keywords)

    # ==================================================
    # 🧠 FOLLOW-UP (CUỐN THỨ 2, CUỐN ĐÓ…)
    # ==================================================
    def is_followup_query(self, question: str) -> bool:
        if not self.last_docs:
            return False
        q = question.lower()
        patterns = [
            "cuốn này",
            "cuốn đó",
            "cuốn thứ",
            "sách này",
            "sách đó"
        ]
        return any(p in q for p in patterns)

    def answer_followup(self, question: str) -> str:
        q = question.lower()
        idx = None

        match = re.search(r"thứ\s*(\d+)", q)
        if match:
            idx = int(match.group(1)) - 1

        if idx is not None and 0 <= idx < len(self.last_docs):
            book = self.last_docs[idx]
            return (
                f"📘 **{book['title']}**\n"
                f"- Tác giả: {book['authors']}\n"
                f"- Năm xuất bản: {book['published_year']}\n"
                f"- Thể loại: {book.get('category','')}\n\n"
                f"📝 Tóm tắt:\n{book.get('snippet','')}"
            )

        return "❌ Tôi không xác định được cuốn sách bạn đang hỏi."

    # ==================================================
    # 🧠 CÓ CẦN TỔNG HỢP KHÔNG?
    # ==================================================
    def needs_synthesis(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "nên",
            "phù hợp",
            "gợi ý",
            "so sánh",
            "đánh giá",
            "phân tích",
            "tổng hợp",
            "giải thích",
            "theo bạn",
            "vì sao",
            "như thế nào"
        ]
        return any(k in q for k in keywords)

    # ==================================================
    # 🎯 SCORE THRESHOLD
    # ==================================================
    def apply_score_threshold(self, docs):
        if not docs:
            return []
        best_score = max(d.get("score", 0) for d in docs)
        return docs if best_score >= SCORE_THRESHOLD else []

    # ==================================================
    # 🏛️ LIBRARY CONTEXT
    # ==================================================
    def _build_library_context(self) -> dict:
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
    # 🤖 FALLBACK (NO HALLUCINATION)
    # ==================================================
    def gemini_fallback(self, question: str) -> str:
        prompt = f"""
Bạn là trợ lý thư viện AI.

Thư viện KHÔNG có dữ liệu phù hợp cho câu hỏi:
"{question}"

Yêu cầu:
- Nói rõ không có dữ liệu
- KHÔNG bịa tên sách
- Có thể gợi ý chung
"""
        return self._genai_generate(prompt)

    # ==================================================
    # 🤖 MAIN ROUTER
    # ==================================================
    def generate_answer(self, question: str) -> str:

        # 1. Garbage
        if self.is_garbage_query(question):
            return "❌ Câu hỏi không hợp lệ hoặc quá ngắn."

        # 2. Thống kê (NO LLM)
        if self.is_library_stats_query(question):
            total = self.search_engine.vector_db.get_collection_stats().get("count", 0)
            return f"📚 Hiện tại thư viện có **{total} cuốn sách** trong hệ thống."

        # 3. Thông tin thư viện (NO SEARCH)
        if self.is_library_info_query(question):
            ctx = self._build_library_context()
            prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books="(Không áp dụng)",
    **ctx
)}
"""
            return self._genai_generate(prompt)

        # 4. Follow-up
        if self.is_followup_query(question):
            return self.answer_followup(question)

        # 5. Book search (RAG)
        raw_docs = self.search_engine.search(
            query=question,
            top_k=self.top_k * SEARCH_EXPAND_FACTOR
        )
        docs = self.apply_score_threshold(raw_docs)

        if docs:
            self.last_docs = docs[:self.top_k]

            book_lines = []
            reasons = []

            for i, d in enumerate(self.last_docs, start=1):
                book_lines.append(
                    f"{i}. {d['title']} – {d['authors']} ({d['published_year']})"
                )
                reasons.append(
                    f"- **{d['title']}** phù hợp vì nội dung liên quan trực tiếp đến truy vấn."
                )

            books_text = "\n".join(book_lines)
            explain_text = "\n".join(reasons)

            # ❌ KHÔNG tổng hợp nếu không cần
            if not self.needs_synthesis(question):
                return f"""📚 Danh sách sách liên quan

{books_text}

🔍 Vì sao chọn các sách này
{explain_text}
"""

            # ✅ Chỉ tổng hợp khi cần
            ctx = self._build_library_context()
            prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books=books_text,
    **ctx
)}

Giải thích vì sao chọn sách:
{explain_text}
"""
            synthesis = self._genai_generate(prompt)

            return f"""📚 Danh sách sách liên quan

{books_text}

🔍 Vì sao chọn các sách này
{explain_text}

📝 Tổng hợp
{synthesis}
"""

        # 6. Fallback
        return self.gemini_fallback(question)
