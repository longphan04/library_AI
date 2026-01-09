import os
import google.generativeai as genai
from ..search_engine import SearchEngine
from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

genai.configure(api_key=os.getenv("OPENAI_API_KEY"))

class RAGEngine:
    def __init__(self, top_k: int = 5):
        self.search_engine = SearchEngine()
        self.top_k = top_k
        self.model = genai.GenerativeModel("gemini-3-flash-preview")

    def retrieve(self, question: str):
        if not question or not question.strip():
            return []
        return self.search_engine.search(query=question, top_k=self.top_k)

    def generate_answer(self, question: str) -> str:
        docs = self.retrieve(question)

        # ❌ Không có dữ liệu → trả thẳng
        if not docs:
            return "❌ Tôi không tìm thấy sách phù hợp trong thư viện."

        # ==================================================
        # 1️⃣ BƯỚC FACTUAL – CODE TỰ LIỆT KÊ SÁCH (KHÔNG LLM)
        # ==================================================
        book_lines = []
        for i, d in enumerate(docs, start=1):
            title = d.get("title", "Không rõ")
            authors = d.get("authors", "Không rõ")
            year = d.get("published_year", "N/A")
            category = d.get("category", "")

            book_lines.append(
                f"{i}. {title} – {authors} ({year})"
                + (f" | Thể loại: {category}" if category else "")
            )

        books_text = "\n".join(book_lines)

        # ==================================================
        # 2️⃣ PROMPT – LLM CHỈ ĐƯỢC GIẢI THÍCH
        # ==================================================
        prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    books=books_text
)}
"""

        resp = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 512
            }
        )

        explanation = resp.text.strip() if resp and resp.text else ""

        # ==================================================
        # 3️⃣ OUTPUT CUỐI – CÓ KIỂM SOÁT
        # ==================================================
        return f"""📚 **Danh sách sách liên quan trong thư viện**

{books_text}

📝 **Nhận xét**
{explanation}
"""