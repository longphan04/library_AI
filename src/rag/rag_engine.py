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

    def build_context(self, docs):
        return "\n\n".join(f"📘 {d['title']}\n{d['snippet']}" for d in docs)

    def generate_answer(self, question: str) -> str:
        docs = self.retrieve(question)
        if not docs:
            return "❌ Tôi không tìm thấy thông tin phù hợp trong thư viện."

        prompt = f"""{SYSTEM_PROMPT}

{USER_PROMPT_TEMPLATE.format(
    question=question,
    context=self.build_context(docs)
)}"""

        resp = self.model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 512}
        )
        return resp.text.strip()
