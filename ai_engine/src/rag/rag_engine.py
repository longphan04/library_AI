import os
import re
import json
import logging
import google.genai as genai
from typing import List, Dict
from pathlib import Path

from ..search_engine import SearchEngine
from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, LIBRARY_INFO

# ==========================
# CONFIG
# ==========================
DEFAULT_TOP_K = 5
SEARCH_EXPAND_FACTOR = 3
SCORE_THRESHOLD = 0.80
QUERY_CACHE_THRESHOLD = 0.95

logger = logging.getLogger("RAGEngine")


class RAGEngine:
    def __init__(self, user_id: str, top_k: int = DEFAULT_TOP_K):
        self.user_id = user_id
        self.search_engine = SearchEngine()
        self.embedder = self.search_engine.embedder
        self.vector_db = self.search_engine.vector_db
        self.top_k = top_k

        # Gemini client
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

        # Short-term context (RAM)
        self.last_docs: List[Dict] = []

    # ==================================================
    # 🔧 GEMINI
    # ==================================================
    def _genai_generate(self, prompt: str) -> str:
        resp = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return resp.text.strip() if resp and resp.text else ""

    # ==================================================
    # 🧹 CLEAR CONTEXT / NEW CHAT
    # ==================================================
    def clear_context(self):
        """
        Reset short-term memory for a new topic.
        DOES NOT delete user history in DB.
        """
        self.last_docs.clear()
        logger.info(f"Context cleared for user {self.user_id}")

    # ==================================================
    # 🚫 GARBAGE
    # ==================================================
    def is_garbage_query(self, q: str) -> bool:
        if not q or not q.strip():
            return True
        q = q.lower()
        if len(q) < 3 or q.isdigit():
            return True
        if not re.search(r"[a-zA-ZÀ-ỹ]", q):
            return True
        return False

    # ==================================================
    # 📊 STATS
    # ==================================================
    def is_library_stats_query(self, q: str) -> bool:
        q = q.lower()
        return any(k in q for k in [
            "bao nhiêu sách", "bao nhiêu cuốn",
            "tổng số sách", "số lượng sách"
        ])

    # ==================================================
    # 🏛️ LIBRARY INFO
    # ==================================================
    def is_library_info_query(self, q: str) -> bool:
        q = q.lower()
        return any(k in q for k in [
            "mở cửa", "đóng cửa", "giờ mở", "giờ làm việc",
            "nội quy", "mượn sách", "trả sách", "phí phạt"
        ])

    # ==================================================
    # 🧠 FOLLOW-UP
    # ==================================================
    def is_followup_query(self, q: str) -> bool:
        return bool(self.last_docs) and any(k in q.lower() for k in [
            "cuốn này", "cuốn đó", "cuốn thứ", "sách này"
        ])

    # ==================================================
    # 🤖 MAIN
    # ==================================================
    def generate_answer(self, question: str) -> str:

        # 🔁 Clear context command
        if question.lower() in ["/new", "/clear", "new chat", "clear context"]:
            self.clear_context()
            return "🆕 Đã bắt đầu một cuộc trò chuyện mới."

        # Garbage
        if self.is_garbage_query(question):
            return "❌ Câu hỏi không hợp lệ."

        # Embed query
        q_vec = self.embedder.embed_text(question, is_query=True)

        # 1️⃣ USER VECTOR MEMORY
        cached = self.vector_db.search_user_memory(
            self.user_id, q_vec, threshold=0.90
        )
        if cached:
            return f"⚡ (ghi nhớ)\n{cached}"

        # 2️⃣ STATS
        if self.is_library_stats_query(question):
            total = self.vector_db.get_collection_stats()["count"]
            answer = f"📚 Thư viện hiện có **{total} cuốn sách**."
            self.vector_db.add_user_memory(
                self.user_id, question, q_vec, answer
            )
            return answer

        # 3️⃣ LIBRARY INFO
        if self.is_library_info_query(question):
            ctx = {
                "opening_hours": LIBRARY_INFO["opening_hours"],
                "library_rules": "\n".join(f"- {r}" for r in LIBRARY_INFO["library_rules"]),
                "borrow_policy": "\n".join(
                    f"- {k}: {v}" for k, v in LIBRARY_INFO["borrow_policy"].items()
                ),
                "penalty_policy": "\n".join(
                    f"- {k}: {v}" for k, v in LIBRARY_INFO["penalty_policy"].items()
                ),
            }
            prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books="(Không áp dụng)",
    **ctx
)}
"""
            answer = self._genai_generate(prompt)
            self.vector_db.add_user_memory(
                self.user_id, question, q_vec, answer
            )
            return answer

        # 4️⃣ FOLLOW-UP (no cache)
        if self.is_followup_query(question):
            return self.answer_followup(question)

        # 5️⃣ RAG
        docs = self.search_engine.search(
            query=question,
            top_k=self.top_k * SEARCH_EXPAND_FACTOR
        )
        if docs:
            self.last_docs = docs[:self.top_k]
            lines = [
                f"{i}. {d['title']} – {d['authors']} ({d['published_year']})"
                for i, d in enumerate(self.last_docs, 1)
            ]
            answer = "📚 Danh sách sách liên quan\n\n" + "\n".join(lines)
            self.vector_db.add_user_memory(
                self.user_id, question, q_vec, answer
            )
            return answer

        # 6️⃣ FALLBACK
        answer = self._genai_generate(
            f"Trả lời ngắn gọn:\n{question}"
        )
        self.vector_db.add_user_memory(
            self.user_id, question, q_vec, answer
        )
        return answer
