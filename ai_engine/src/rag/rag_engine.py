import os
import re
import json
import logging
import google.generativeai as genai

from ..search_engine import SearchEngine
from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, LIBRARY_INFO

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
DEFAULT_TOP_K = 5
SCORE_THRESHOLD = 0.80

genai.configure(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger("RAGEngine")


class RAGEngine:
    def __init__(self, top_k: int = DEFAULT_TOP_K):
        self.search_engine = SearchEngine()
        self.top_k = top_k
        self.model = genai.GenerativeModel("gemini-3-flash-preview")

    # ==================================================
    # 🚫 CHẶN QUERY RÁC
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
        if re.fullmatch(r"(.)\1{3,}", q):
            return True

        return False

    # ==================================================
    # 🧠 PHÂN LOẠI CÂU HỎI (LLM)
    # ==================================================
    def classify_question(self, question: str) -> dict:
        prompt = f"""
Chỉ trả lời JSON, không giải thích.

Câu hỏi:
"{question}"

Xác định:
- is_book_query: true | false
- number_of_books: số nguyên hoặc null
"""
        resp = self.model.generate_content(
            prompt,
            generation_config={"temperature": 0}
        )

        try:
            return json.loads(resp.text.strip())
        except Exception:
            return {"is_book_query": False, "number_of_books": None}

    # ==================================================
    # 🏛️ BUILD CONTEXT THƯ VIỆN (FIX KEYERROR)
    # ==================================================
    def _build_library_context(self) -> dict:
        return {
            "opening_hours": LIBRARY_INFO["opening_hours"],
            "library_rules": "\n".join(
                f"- {r}" for r in LIBRARY_INFO["library_rules"]
            ),
            "borrow_policy": "\n".join(
                f"- {k}: {v}"
                for k, v in LIBRARY_INFO["borrow_policy"].items()
            ),
            "penalty_policy": "\n".join(
                f"- {k}: {v}"
                for k, v in LIBRARY_INFO["penalty_policy"].items()
            ),
        }

    # ==================================================
    # 🎯 SCORE THRESHOLD
    # ==================================================
    def apply_score_threshold(self, docs):
        if not docs:
            return []

        best_score = max(d.get("score", 0) for d in docs)
        return docs if best_score >= SCORE_THRESHOLD else []

    # ==================================================
    # 🤖 GENERATE ANSWER
    # ==================================================
    def generate_answer(self, question: str) -> str:

        if self.is_garbage_query(question):
            return "❌ Câu hỏi không hợp lệ hoặc quá ngắn."

        intent = self.classify_question(question)
        is_book_query = intent.get("is_book_query", False)
        number_of_books = intent.get("number_of_books")

        library_ctx = self._build_library_context()

        # ------------------------------
        # KHÔNG PHẢI HỎI SÁCH
        # ------------------------------
        if not is_book_query:
            prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books="(Không áp dụng)",
    **library_ctx
)}
"""
            resp = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 512}
            )
            return resp.text.strip()

        # ------------------------------
        # HỎI SÁCH
        # ------------------------------
        top_k = number_of_books if number_of_books else self.top_k
        docs = self.search_engine.search(query=question, top_k=top_k)
        docs = self.apply_score_threshold(docs)

        if not docs:
            return "❌ Không có kết quả sách phù hợp."

        book_lines = []
        for i, d in enumerate(docs, start=1):
            book_lines.append(
                f"{i}. {d['title']} – {d['authors']} ({d['published_year']})"
            )

        books_text = "\n".join(book_lines)

        prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books=books_text,
    **library_ctx
)}
"""
        resp = self.model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 512}
        )

        explanation = resp.text.strip() if resp and resp.text else ""

        return f"""📚 Danh sách sách liên quan

{books_text}

📝 Nhận xét
{explanation}
"""
