# <<<<<<< HEAD
# # import os
# # import re
# # import json
# # import logging
# # import uuid
# # from typing import List, Dict, Optional
# #
# # from config.settings import settings
# # from src.search_engine import SearchEngine
# # <<<<<<< HEAD
# # from src.rag.prompt import (
# #     SYSTEM_PROMPT,
# #     USER_PROMPT_TEMPLATE,
# #     LIBRARY_INFO,
# #     FOLLOWUP_PROMPT_TEMPLATE,
# #     SMALLTALK_PROMPT_TEMPLATE,
# #     GENERAL_QA_PROMPT_TEMPLATE
# # )
# # =======
# # from src.rag.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, LIBRARY_INFO
# # from src.rag.model_manager import ModelManager  # NEW IMPORT
# # >>>>>>> origin/main
# # from config.rag_config import (
# #     GEMINI_API_KEYS, # NEW CONFIG
# #     GEMINI_MODELS,   # NEW CONFIG
# #     GEMINI_MODEL,    # Keep for backward compatibility or default
# #     DEFAULT_TOP_K,
# #     SCORE_THRESHOLD,
# #     MIN_QUERY_LENGTH,
# #     TEMPERATURE,
# #     MAX_OUTPUT_TOKENS,
# #     QUERY_CACHE_THRESHOLD,
# #     SEARCH_EXPAND_FACTOR
# # )
# #
# #
# # # Logger cho module RAG
# # logger = logging.getLogger("RAGEngine")
# #
# #
# # class ChatSession:
# #     """
# #     Lưu trữ trạng thái hội thoại của một user/session.
# #     Persists to disk to survive restarts.
# #     """
# #     def __init__(self, session_id: str):
# #         self.session_id = session_id
# #         self.history: List[Dict] = []  # [{"role": "user", "text": "..."}, ...]
# #         self.last_search_results: List[Dict] = []  # Kết quả tìm sách gần nhất
# #         self.file_path = os.path.join(settings.DATA_PROCESSED_DIR, "chat_sessions", f"rag_{session_id}.json")
# #
# #     def add_message(self, role: str, text: str):
# #         self.history.append({"role": role, "text": text})
# #         # FULL HISTORY: No truncation here anymore!
# #         # if len(self.history) > 20: ... (REMOVED)
# #         self.save()
# #
# #     def save(self):
# #         try:
# #             os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
# #             data = {
# #                 "session_id": self.session_id,
# #                 "history": self.history,
# #                 "last_search_results": self.last_search_results
# #             }
# #             with open(self.file_path, "w", encoding="utf-8") as f:
# #                 json.dump(data, f, ensure_ascii=False, indent=2)
# #         except Exception as e:
# #             logger.error(f"Failed to save session {self.session_id}: {e}")
# #
# #     def load(self):
# #         try:
# #             if os.path.exists(self.file_path):
# #                 with open(self.file_path, "r", encoding="utf-8") as f:
# #                     data = json.load(f)
# #                     self.history = data.get("history", [])
# #                     self.last_search_results = data.get("last_search_results", [])
# #         except Exception as e:
# #             logger.error(f"Failed to load session {self.session_id}: {e}")
# #
# # class RAGEngine:
# #     """
# #     ========================================================
# #     🤖 RAGEngine (Improved)
# #     --------------------------------------------------------
# #     Chức năng:
# #     - Quản lý session chat (Persistent)
# #     - Phân loại intent (Greeting / Follow-up / Search)
# #     - RAG flow với context memory
# #     - Multi-Model Rotation & Rate Limit Handling (NEW)
# #     ========================================================
# #     """
# #
# #     def __init__(self, top_k: int = DEFAULT_TOP_K):
# #         # 1. SEARCH ENGINE
# #         self.search_engine = SearchEngine()
# #         self.embedder = self.search_engine.embedder
# #         self.vector_db = self.search_engine.vector_db
# #         self.top_k = top_k
# #
# # <<<<<<< HEAD
# #         # Initialize Gemini client
# #         self.client = genai.Client(api_key=GEMINI_API_KEY)
# #         self.last_docs = []  # For follow-up queries
# #         self.last_books_text = ""
# #         self.history: list[dict] = []  # [{role: user/assistant, content: str}]
# #
# #     def _add_history(self, role: str, content: str, max_turns: int = 6):
# #         # Lưu ngắn gọn lịch sử để LLM có ngữ cảnh follow-up
# #         self.history.append({"role": role, "content": content})
# #         if len(self.history) > max_turns * 2:
# #             self.history = self.history[-max_turns * 2 :]
# #
# #     def _history_to_text(self) -> str:
# #         if not self.history:
# #             return "(chưa có lịch sử)"
# #         lines = []
# #         for h in self.history[-8:]:
# #             prefix = "Người dùng" if h["role"] == "user" else "Trợ lý"
# #             lines.append(f"{prefix}: {h['content']}")
# #         return "\n".join(lines)
# #
# #     def _shorten_text(self, text: str | None, max_len: int = 480) -> str:
# #         if not text:
# #             return "(không có mô tả)"
# #         text = text.strip()
# #         return text[:max_len] + "…" if len(text) > max_len else text
# #
# #     def _books_to_context(self, docs: List[Dict]) -> str:
# #         lines = []
# #         for i, b in enumerate(docs, 1):
# #             snippet = self._shorten_text(b.get("richtext") or b.get("snippet"))
# #             lines.append(
# #                 f"{i}. {b.get('title')} – {b.get('authors')} ({b.get('publish_year')})\n{snippet}"
# #             )
# #         return "\n\n".join(lines)
# #
# #     def is_smalltalk(self, question: str) -> bool:
# #         """
# #         Nhận diện câu hỏi smalltalk / chào hỏi.
# #         Hỗ trợ cả tiếng Việt có dấu và không dấu.
# #         """
# #         q = question.lower().strip()
# #
# #         # Loại bỏ dấu câu
# #         q = re.sub(r'[?.!,;:]', '', q)
# #
# #         smalltalk_keywords = [
# #             # Chào hỏi có dấu
# #             "xin chào", "chào bạn", "chào", "chào buổi sáng", "chào buổi tối",
# #             # Chào hỏi không dấu
# #             "xin chao", "chao ban", "chao", "chao buoi sang", "chao buoi toi",
# #             # Tiếng Anh
# #             "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
# #             # Cảm ơn có dấu
# #             "cảm ơn", "cám ơn", "cảm ơn bạn", "cám ơn bạn",
# #             # Cảm ơn không dấu
# #             "cam on", "cam on ban",
# #             # Tiếng Anh
# #             "thank", "thanks", "thank you", "tks", "ty",
# #             # Tạm biệt có dấu
# #             "tạm biệt", "hẹn gặp lại", "gặp lại sau",
# #             # Tạm biệt không dấu
# #             "tam biet", "hen gap lai", "gap lai sau",
# #             # Tiếng Anh
# #             "bye", "goodbye", "see you", "see ya",
# #             # Hỏi thăm có dấu
# #             "bạn là ai", "tên gì", "khỏe không", "bạn ổn không", "bạn có khỏe không",
# #             # Hỏi thăm không dấu
# #             "ban la ai", "ten gi", "khoe khong", "ban on khong", "ban co khoe khong",
# #             # Hỏi thăm tiếng Anh
# #             "how are you", "what's up", "who are you", "what is your name",
# #             # Các câu đơn giản
# #             "alo", "yo", "hii", "hiii", "helloo", "helo"
# #         ]
# #
# #         # Kiểm tra exact match trước
# #         if q in smalltalk_keywords:
# #             return True
# #
# #         # Kiểm tra contains
# #         return any(k in q for k in smalltalk_keywords)
# #
# #     def smalltalk_answer(self, question: str) -> str:
# #         """
# #         Dùng Gemini trả lời smalltalk một cách thông minh và tự nhiên.
# #         """
# #         prompt = SMALLTALK_PROMPT_TEMPLATE.format(
# #             history=self._history_to_text(),
# #             question=question
# #         )
# #
# #         try:
# #             response = self.client.models.generate_content(
# #                 model=GEMINI_MODEL,
# #                 contents=prompt,
# #                 config=types.GenerateContentConfig(
# #                     temperature=0.7,  # Cao hơn để trả lời tự nhiên hơn
# #                     max_output_tokens=150  # Ngắn gọn
# #                 )
# #             )
# #             return response.text.strip() if response and response.text else "👋 Chào bạn! Mình có thể giúp gì cho bạn?"
# #         except Exception as e:
# #             logger.error(f"Gemini smalltalk error: {e}")
# #             # Fallback nếu API lỗi
# #             return "👋 Chào bạn! Mình là trợ lý thư viện AI. Bạn cần tìm sách gì hôm nay?"
# #
# #     def general_llm_answer(self, question: str) -> str:
# #         """
# #         Dùng Gemini trả lời các câu hỏi tổng quát khi không tìm thấy sách phù hợp.
# #         """
# #         prompt = GENERAL_QA_PROMPT_TEMPLATE.format(
# #             history=self._history_to_text(),
# #             question=question
# #         )
# #
# #         try:
# #             response = self.client.models.generate_content(
# #                 model=GEMINI_MODEL,
# #                 contents=prompt,
# #                 config=types.GenerateContentConfig(
# #                     temperature=0.5,
# #                     max_output_tokens=MAX_OUTPUT_TOKENS
# #                 )
# #             )
# #             return response.text.strip() if response and response.text else "❌ Tôi chưa có câu trả lời phù hợp."
# #         except Exception as e:
# #             logger.error(f"Gemini general QA error: {e}")
# #             return "❌ Không thể trả lời câu hỏi này lúc này. Vui lòng thử lại sau."
# #
# #     def get_suggested_questions(self) -> List[str]:
# #         # Danh sách gợi ý mặc định cho giao diện chat
# #         return [
# #             "Thư viện mở cửa lúc mấy giờ?",
# #             "Làm sao để gia hạn sách?",
# #             "Có sách nào về trí tuệ nhân tạo không?",
# #             "Phí phạt trả sách trễ là bao nhiêu?",
# #         ]
# #
# #     def _is_book_related_query(self, question: str) -> bool:
# #         """
# #         Kiểm tra xem câu hỏi có liên quan đến việc tìm/hỏi về sách không.
# #         Dùng để quyết định có nên dùng cache sách hay không.
# #         """
# #         q = question.lower()
# #         q = re.sub(r'[?.!,;:]', '', q)
# #
# #         book_keywords = [
# #             # Từ khóa sách tiếng Việt
# #             "sách", "cuốn", "quyển", "tài liệu", "giáo trình", "truyện",
# #             "tiểu thuyết", "tác phẩm", "ebook", "pdf",
# #             # Từ khóa sách không dấu
# #             "sach", "cuon", "quyen", "tai lieu", "giao trinh", "truyen",
# #             "tieu thuyet", "tac pham",
# #             # Từ khóa tìm kiếm
# #             "tìm", "tìm kiếm", "gợi ý", "đề xuất", "cho tôi", "có không",
# #             "tim", "tim kiem", "goi y", "de xuat", "cho toi", "co khong",
# #             # Thể loại sách
# #             "python", "java", "programming", "lập trình", "lap trinh",
# #             "machine learning", "ai", "deep learning", "data science",
# #             "toán", "văn", "lịch sử", "địa lý", "vật lý", "hóa học",
# #             "toan", "van", "lich su", "dia ly", "vat ly", "hoa hoc",
# #             # Tiếng Anh
# #             "book", "novel", "textbook", "recommend", "find", "search"
# #         ]
# #
# #         return any(k in q for k in book_keywords)
# # =======
# #         # 2. Model Manager (replaces single client)
# #         self.model_manager = ModelManager(
# #             api_keys=GEMINI_API_KEYS,
# #             models=GEMINI_MODELS
# #         )
# #
# #         # 3. Session storage {session_id: ChatSession}
# #         self.sessions: Dict[str, ChatSession] = {}
# #
# #     def get_session(self, session_id: str) -> ChatSession:
# #         if session_id not in self.sessions:
# #             session = ChatSession(session_id)
# #             session.load()  # Try loading from disk
# #             self.sessions[session_id] = session
# #         return self.sessions[session_id]
# # >>>>>>> origin/main
# #
# #     # ==================================================
# #     # INTENT CLASSIFICATION
# #     # ==================================================
# #     def classify_intent(self, query: str, session: ChatSession) -> str:
# #         q = query.strip().lower()
# #
# #         # 1. Garbage check
# #         if len(q) < 2 or not re.search(r"[a-zA-ZÀ-ỹ0-9]", q):
# #             return "GARBAGE"
# #
# #         # 2. Greeting check
# #         greetings = ["hi", "hello", "chào", "xin chào", "hey", "bạn ơi", "giúp mình"]
# #         if q in greetings:
# #             return "GREETING"
# #
# #         # 3. Follow-up check
# #         if session.last_search_results:
# #             followup_keywords = [
# #                 "cuốn này", "cuốn đó", "cuốn thứ", "sách này", "sách đó",
# #                 "chi tiết", "nó nói về", "tác giả là ai", "giá bao nhiêu"
# #             ]
# #             if any(k in q for k in followup_keywords):
# #                 return "FOLLOWUP"
# #
# #             if re.search(r"(cuốn|số|quyển)\s*\d+", q):
# #                 return "FOLLOWUP"
# #
# #         # 4. Default to SEARCH
# #         return "SEARCH"
# #
# #     # ==================================================
# #     # HANDLERS
# #     # ==================================================
# #     def answer_greeting(self) -> str:
# #         return "👋 Xin chào! Tôi là trợ lý thư viện AI. Tôi có thể giúp gì cho bạn hôm nay? (Tìm sách, hỏi nội quy, v.v...)"
# #
# #     def answer_followup(self, question: str, session: ChatSession) -> str:
# #         """Trả lời follow-up dựa trên last_search_results của session"""
# #         q = question.lower()
# #
# #         # 1. Check for "all" / "summarize all"
# #         if any(k in q for k in ["tất cả", "cả hai", "cả 2", "cả 3", "mọi cuốn", "những cuốn này", "các cuốn", "hai cuốn", "2 cuốn", "ba cuốn", "3 cuốn"]):
# #             # Synthesize all books in context
# #             books_text = "\n".join([
# #                  f"{i}. {d['title']} – {d['authors']}" for i, d in enumerate(session.last_search_results, 1)
# #             ])
# #             ctx = self._build_library_context()
# #             prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books=books_text, **ctx)}"""
# #             return self._call_gemini(prompt)
# #
# #         # 2. Extract specific index (digits or text)
# #         idx = -1
# #
# #         # Mapping text to number
# #         text_nums = {
# #             "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
# #             "nhất": 1, "nhì": 2, "đầu tiên": 1, "cuối cùng": len(session.last_search_results)
# #         }
# #
# #         # Regex for text numbers
# #         text_pattern = r"(thứ|số|cuốn|quyển)\s*(" + "|".join(text_nums.keys()) + r")"
# #         match_text = re.search(text_pattern, q)
# #
# #         # Regex for digits (flexible: "cuốn 1", "số 1", "1.")
# #         digit_pattern = r"(?:thứ|số|cuốn|quyển|^)\s*(\d+)"
# #         match_digit = re.search(digit_pattern, q)
# #
# # <<<<<<< HEAD
# #     # ==================================================
# #     # 🧠 NHẬN DIỆN FOLLOW-UP QUESTION
# #     # ==================================================
# #     def is_followup_query(self, question: str) -> bool:
# #         """
# #         Ví dụ:
# #         - "Cuốn thứ thì sao?"
# #         - "Cuốn này ai viết?"
# #         - "Trong số các cuốn đó, cuốn nào dễ học nhất?"
# #         """
# #         if not self.last_docs:
# #             return False
# #
# #         q = question.lower()
# #         keywords = [
# #             "cuốn này",
# #             "cuốn đó",
# #             "cuốn thứ",
# #             "sách này",
# #             "sách đó",
# #             "trong số",
# #             "cuốn nào",
# #             "cái nào",
# #             "dễ học",
# #             "tốt nhất",
# #             "phù hợp",
# #             "nên chọn",
# #             "ở trên",
# #             "vừa rồi",
# #             "trong danh sách",
# #         ]
# #         return any(k in q for k in keywords)
# #
# #     def answer_followup(self, question: str) -> str:
# #         """
# #         Trả lời follow-up dựa trên danh sách sách lần trước.
# #         - Nếu có chỉ mục ("cuốn thứ 2") thì trả về sách tương ứng.
# #         - Nếu là câu chọn lọc ("cuốn nào dễ học nhất") thì dùng LLM tổng hợp trên danh sách hiện có.
# #         """
# #         if not self.last_docs:
# #             return "❌ Tôi chưa có danh sách sách để tham chiếu."
# #
# #         q = question.lower()
# #         match = re.search(r"thứ\s*(\d+)", q)
# #         if match:
# #             idx = int(match.group(1)) - 1
# #             if 0 <= idx < len(self.last_docs):
# #                 b = self.last_docs[idx]
# #                 snippet = self._shorten_text(b.get("richtext") or b.get("snippet"))
# #                 return (
# #                     f"📘 **{b['title']}**\n"
# #                     f"- Tác giả: {b['authors']}\n"
# #                     f"- Năm xuất bản: {b['publish_year']}\n\n"
# #                     f"{snippet}"
# #                 )
# #             return "❌ Không tìm thấy cuốn sách bạn yêu cầu."
# #
# #         books_context = self._books_to_context(self.last_docs)
# #         prompt = FOLLOWUP_PROMPT_TEMPLATE.format(
# #             history=self._history_to_text(),
# #             previous_books=books_context,
# #             question=question
# #         )
# #         try:
# #             response = self.client.models.generate_content(
# #                 model=GEMINI_MODEL,
# #                 contents=prompt,
# #                 config=types.GenerateContentConfig(
# #                     temperature=min(TEMPERATURE, 0.5),
# #                     max_output_tokens=MAX_OUTPUT_TOKENS
# #                 )
# #             )
# #             return response.text.strip() if response and response.text else "❌ Tôi chưa xác định được câu trả lời."
# #         except Exception as e:
# #             logger.error(f"Gemini follow-up error: {e}")
# #             return "❌ Không thể trả lời câu hỏi follow-up."
# # =======
# #         if match_text:
# #             key = match_text.group(2)
# #             idx = text_nums.get(key, 0) - 1
# #         elif match_digit:
# #             idx = int(match_digit.group(1)) - 1
# #
# #         # 3. Return info if index valid
# #         if 0 <= idx < len(session.last_search_results):
# #             b = session.last_search_results[idx]
# #             # Use LLM description if simple info return
# #             return (
# #                 f"📘 **{b['title']}**\n"
# #                 f"- Tác giả: {b['authors']}\n"
# #                 f"- Năm xuất bản: {b['publish_year']}\n"
# #                 f"- Mã sách: {b['identifier']}\n\n"
# #                 f"📝 **Nội dung:**\n{b.get('richtext','')[:1000]}..."
# #             )
# #
# #         # Fallback: Ask for clarification
# #         if session.last_search_results:
# #             return "Bạn muốn hỏi về cuốn sách số mấy trong danh sách trên? (Ví dụ: 'cuốn số 1', 'quyển đầu tiên', 'tất cả')"
# #
# #         # Should not happen if detected as Followup
# #         return "❌ Tôi không nhớ chúng ta đang nói về cuốn nào. Bạn hãy tìm kiếm lại nhé."
# # >>>>>>> origin/main
# #
# #     def needs_synthesis(self, question: str) -> bool:
# #         q = question.lower()
# #         return any(k in q for k in [
# #             "nên", "phù hợp", "gợi ý", "so sánh", "đánh giá",
# #             "phân tích", "tổng hợp", "giải thích", "vì sao", "như thế nào"
# #         ])
# #
# #     def _build_library_context(self) -> dict:
# #         return {
# #             "opening_hours": LIBRARY_INFO["opening_hours"],
# #             "library_rules": "\n".join(f"- {r}" for r in LIBRARY_INFO["library_rules"]),
# #             "borrow_policy": "\n".join(f"- {k}: {v}" for k, v in LIBRARY_INFO["borrow_policy"].items()),
# #             "penalty_policy": "\n".join(f"- {k}: {v}" for k, v in LIBRARY_INFO["penalty_policy"].items()),
# #         }
# #
# #     # ==================================================
# #     # MAIN GENERATE FUNCTION
# #     # ==================================================
# #     def generate_answer(self, question: str, session_id: str = "default") -> str:
# #         session = self.get_session(session_id)
# #         session.add_message("user", question)
# #
# #         intent = self.classify_intent(question, session)
# #         logger.info(f"Session: {session_id} | Intent: {intent} | Query: {question}")
# #
# #         answer = ""
# #         if intent == "GARBAGE":
# #             answer = "❌ Câu hỏi không hợp lệ hoặc quá ngắn."
# #         elif intent == "GREETING":
# #             answer = self.answer_greeting()
# #         elif intent == "FOLLOWUP":
# #             answer = self.answer_followup(question, session)
# #         else:
# #             if self.is_library_stats_query(question):
# #                 total = self.vector_db.get_collection_stats().get("count", 0)
# #                 answer = f"📚 Hiện tại thư viện có **{total} cuốn sách** trong hệ thống."
# #             elif self.is_library_info_query(question):
# #                 answer = self._generate_library_info_answer(question)
# #             else:
# #                 answer = self._perform_book_search(question, session)
# #
# #         session.add_message("model", answer)
# #         return answer
# #
# #     # ==================================================
# #     # SUB-HANDLERS
# #     # ==================================================
# #     def is_library_stats_query(self, q: str) -> bool:
# #         return any(k in q.lower() for k in ["bao nhiêu sách", "tổng số sách", "số lượng sách"])
# #
# #     def is_library_info_query(self, q: str) -> bool:
# #         return any(k in q.lower() for k in ["mở cửa", "quy định", "mượn sách", "trả sách", "phí phạt"])
# #
# # <<<<<<< HEAD
# #         # ==================================================
# #         # ️⃣ SMALLTALK / CHÀO HỎI (bỏ qua cache để tránh hit sách cũ)
# #         # ==================================================
# #         if self.is_smalltalk(question):
# #             answer = self.smalltalk_answer(question)
# #             self._add_history("user", question)
# #             self._add_history("assistant", answer)
# #             return answer
# #
# #         # ==================================================
# #         # ️⃣ QUERY MEMORY (CACHE CÂU HỎI CŨ)
# #         # ==================================================
# #         q_vec = self.embedder.embed_text(question, is_query=True)
# #         if q_vec:
# #             cached = self.vector_db.search_query_memory(
# #                 q_vec, threshold=QUERY_CACHE_THRESHOLD
# #             )
# #             # Skip cache nếu cache answer là danh sách sách nhưng query không liên quan sách
# # =======
# #     def _generate_library_info_answer(self, question: str) -> str:
# #         ctx = self._build_library_context()
# #         prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books="(Không áp dụng)", **ctx)}"""
# #         return self._call_gemini(prompt)
# #
# #     def _perform_book_search(self, question: str, session: ChatSession) -> str:
# #         q_vec = self.embedder.embed_text(question, is_query=True)
# #         if q_vec:
# #             cached = self.vector_db.search_query_memory(q_vec, threshold=QUERY_CACHE_THRESHOLD)
# # >>>>>>> origin/main
# #             if cached:
# #                 is_book_cache = "📚 Danh sách sách" in cached or "Danh sách sách liên quan" in cached
# #                 if is_book_cache and not self._is_book_related_query(question):
# #                     logger.info("⚠️ Query memory SKIP (cached books for non-book query)")
# #                 else:
# #                     logger.info("⚡ Query memory HIT")
# #                     answer = f"⚡ {cached}"
# #                     self._add_history("user", question)
# #                     self._add_history("assistant", answer)
# #                     return answer
# #
# #         raw_docs = self.search_engine.search(query=question, top_k=self.top_k * SEARCH_EXPAND_FACTOR)
# #         if not raw_docs: return self._gemini_fallback(question)
# #
# #         best_score = max(d.get("score", 0) for d in raw_docs)
# #         if best_score < SCORE_THRESHOLD: return self._gemini_fallback(question)
# #
# # <<<<<<< HEAD
# #             self.vector_db.add_query_memory(
# #                 question, q_vec, answer, qtype="stats"
# #             )
# #             self._add_history("user", question)
# #             self._add_history("assistant", answer)
# #             return answer
# #
# #         # ==================================================
# #         # ️⃣ NỘI QUY / GIỜ GIẤC
# #         # ==================================================
# #         if self.is_library_info_query(question):
# #             ctx = self._build_library_context()
# #             prompt = f"""{SYSTEM_PROMPT}
# #
# # Lịch sử hội thoại gần đây:
# # {self._history_to_text()}
# #
# # {USER_PROMPT_TEMPLATE.format(
# #     question=question,
# #     books="(Không áp dụng)",
# #     **ctx
# # )}
# # """
# #             try:
# #                 response = self.client.models.generate_content(
# #                     model=GEMINI_MODEL,
# #                     contents=prompt,
# #                     config=types.GenerateContentConfig(
# #                         temperature=TEMPERATURE,
# #                         max_output_tokens=MAX_OUTPUT_TOKENS
# #                     )
# #                 )
# #                 answer = response.text.strip() if response and response.text else "❌ Không th��� trả lời câu hỏi này."
# #             except Exception as e:
# #                 logger.error(f"Gemini API error: {e}")
# #                 answer = "❌ Không thể trả lời câu hỏi này."
# #
# #             self.vector_db.add_query_memory(
# #                 question, q_vec, answer, qtype="library_info"
# #             )
# #             self._add_history("user", question)
# #             self._add_history("assistant", answer)
# #             return answer
# #
# #         # ==================================================
# #         # ️⃣ FOLLOW-UP (KHÔNG CACHE)
# #         # ==================================================
# #         if self.is_followup_query(question):
# #             answer = self.answer_followup(question)
# #             self._add_history("user", question)
# #             self._add_history("assistant", answer)
# #             return answer
# #
# #         # ==================================================
# #         # ️⃣ BOOK RAG PIPELINE
# #         # ==================================================
# #         raw_docs = self.search_engine.search(
# #             query=question,
# #             top_k=self.top_k * SEARCH_EXPAND_FACTOR
# #         )
# #
# #         # Lọc theo score
# #         docs = self.apply_score_threshold(raw_docs)
# #
# #         if docs:
# #             # Lưu lại để dùng cho follow-up
# #             self.last_docs = docs[:self.top_k]
# #             self.last_books_text = "\n".join(
# #                 f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
# #                 for i, d in enumerate(self.last_docs, 1)
# #             )
# #
# #             # Build danh sách sách
# #             book_lines = [
# #                 f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
# #                 for i, d in enumerate(self.last_docs, 1)
# #             ]
# #
# #             books_text = "\n".join(book_lines)
# #
# #             # ==================================================
# #             # .️⃣ CHỈ LIST, KHÔNG TỔNG HỢP
# #             # ==================================================
# #             if not self.needs_synthesis(question):
# #                 answer = f"📚 Danh sách sách liên quan\n\n{books_text}"
# #
# #                 self.vector_db.add_query_memory(
# #                     question, q_vec, answer, qtype="rag_list"
# #                 )
# #                 self._add_history("user", question)
# #                 self._add_history("assistant", answer)
# #                 return answer
# #
# #             # ==================================================
# #             # .️⃣ CÓ GỌI LLM ĐỂ TỔNG HỢP
# #             # ==================================================
# #             ctx = self._build_library_context()
# #
# #             prompt = f"""{SYSTEM_PROMPT}
# #
# # Lịch sử hội thoại gần đây:
# # {self._history_to_text()}
# #
# # {USER_PROMPT_TEMPLATE.format(
# #     question=question,
# #     books=books_text,
# #     **ctx
# # )}
# # """
# #             try:
# #                 response = self.client.models.generate_content(
# #                     model=GEMINI_MODEL,
# #                     contents=prompt,
# #                     config=types.GenerateContentConfig(
# #                         temperature=TEMPERATURE,
# #                         max_output_tokens=MAX_OUTPUT_TOKENS
# #                     )
# #                 )
# #                 synthesis = response.text.strip() if response and response.text else "❌ Không thể tổng hợp thông tin."
# #             except Exception as e:
# #                 logger.error(f"Gemini API error: {e}")
# #                 synthesis = "❌ Không thể tổng hợp thông tin."
# #
# #             answer = f"""📚 Danh sách sách liên quan
# #
# # {books_text}
# #
# # 📝 Tổng hợp
# # {synthesis}
# # """
# #             self.vector_db.add_query_memory(
# #                 question, q_vec, answer, qtype="rag_synthesis"
# #             )
# #             self._add_history("user", question)
# #             self._add_history("assistant", answer)
# #             return answer
# #
# #         # ==================================================
# #         # ️⃣ FALLBACK: KHÔNG CÓ DATA → DÙNG LLM TỔNG QUÁT
# #         # ==================================================
# #         answer = self.general_llm_answer(question)
# #         self._add_history("user", question)
# #         self._add_history("assistant", answer)
# # =======
# #         docs = raw_docs[:self.top_k]
# #
# #         session.last_search_results = docs
# #         session.save()
# #
# #         book_lines = [
# #             f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
# #             for i, d in enumerate(docs, 1)
# #         ]
# #         books_text = "\n".join(book_lines)
# #
# #         if not self.needs_synthesis(question):
# #             answer = f"📚 Danh sách sách liên quan:\n\n{books_text}"
# #             if q_vec: self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_list")
# #             return answer
# #
# #         ctx = self._build_library_context()
# #         prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books=books_text, **ctx)}"""
# #
# #         synthesis = self._call_gemini(prompt)
# #         answer = f"📚 Danh sách sách liên quan:\n\n{books_text}\n\n📝 Tổng hợp:\n{synthesis}"
# #
# #         if q_vec: self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_synthesis")
# # >>>>>>> origin/main
# #         return answer
# #
# #     def _gemini_fallback(self, question: str) -> str:
# #         prompt = f"""Bạn là trợ lý thư viện AI. Thư viện KHÔNG có dữ liệu cho câu hỏi: "{question}". Yêu cầu: Nói rõ không có dữ liệu, KHÔNG bịa tên sách."""
# #         return self._call_gemini(prompt)
# #
# #     def _call_gemini(self, prompt: str) -> str:
# #         """Call Gemini via ModelManager (handles rotation & rate limits)"""
# #         try:
# #             # New call using ModelManager
# #             result = self.model_manager.generate_content(
# #                 prompt=prompt,
# #                 temperature=TEMPERATURE,
# #                 max_tokens=MAX_OUTPUT_TOKENS
# #             )
# #             return result if result else "❌ Xin lỗi, không có phản hồi."
# #         except Exception as e:
# #             logger.error(f"Gemini API error: {e}")
# #             return "❌ Hệ thống đang bận hoặc gặp sự cố kết nối."
# =======
# import os
# import re
# import json
# import logging
# from google import genai
# from google.genai import types
# from typing import List, Dict
#
# from src.search_engine import SearchEngine
# from src.rag.prompt import (
#     SYSTEM_PROMPT,
#     USER_PROMPT_TEMPLATE,
#     LIBRARY_INFO,
#     FOLLOWUP_PROMPT_TEMPLATE,
#     SMALLTALK_PROMPT_TEMPLATE,
#     GENERAL_QA_PROMPT_TEMPLATE
# )
# from config.rag_config import (
#     GEMINI_API_KEY,
#     GEMINI_MODEL,
#     DEFAULT_TOP_K,
#     SCORE_THRESHOLD,
#     MIN_QUERY_LENGTH,
#     TEMPERATURE,
#     MAX_OUTPUT_TOKENS,
#     QUERY_CACHE_THRESHOLD,
#     SEARCH_EXPAND_FACTOR
# )
#
#
# # Logger cho module RAG
# logger = logging.getLogger("RAGEngine")
#
#
# class RAGEngine:
#     """
#     ========================================================
#     🤖 RAGEngine
#     --------------------------------------------------------
#     Chức năng:
#     - Nhận câu hỏi người dùng
#     - Phân loại: thống kê / nội quy / follow-up / tìm sách / tổng hợp / fallback
#     - Search vector DB
#     - Build prompt cho Gemini
#     - Cache lại câu hỏi đã hỏi (Query Memory)
#     ========================================================
#     """
#
#     def __init__(self, top_k: int = DEFAULT_TOP_K):
#         # ===============================
#         # ️⃣ SEARCH ENGINE (Vector DB + Embedder)
#         # ===============================
#         self.search_engine = SearchEngine()
#         self.embedder = self.search_engine.embedder
#         self.vector_db = self.search_engine.vector_db
#         self.top_k = top_k
#
#         # Initialize Gemini client
#         self.client = genai.Client(api_key=GEMINI_API_KEY)
#         self.last_docs = []  # For follow-up queries
#         self.last_books_text = ""
#         self.history: list[dict] = []  # [{role: user/assistant, content: str}]
#
#     def _add_history(self, role: str, content: str, max_turns: int = 6):
#         # Lưu ngắn gọn lịch sử để LLM có ngữ cảnh follow-up
#         self.history.append({"role": role, "content": content})
#         if len(self.history) > max_turns * 2:
#             self.history = self.history[-max_turns * 2 :]
#
#     def _history_to_text(self) -> str:
#         if not self.history:
#             return "(chưa có lịch sử)"
#         lines = []
#         for h in self.history[-8:]:
#             prefix = "Người dùng" if h["role"] == "user" else "Trợ lý"
#             lines.append(f"{prefix}: {h['content']}")
#         return "\n".join(lines)
#
#     def _shorten_text(self, text: str | None, max_len: int = 480) -> str:
#         if not text:
#             return "(không có mô tả)"
#         text = text.strip()
#         return text[:max_len] + "…" if len(text) > max_len else text
#
#     def _books_to_context(self, docs: List[Dict]) -> str:
#         lines = []
#         for i, b in enumerate(docs, 1):
#             snippet = self._shorten_text(b.get("richtext") or b.get("snippet"))
#             lines.append(
#                 f"{i}. {b.get('title')} – {b.get('authors')} ({b.get('publish_year')})\n{snippet}"
#             )
#         return "\n\n".join(lines)
#
#     def is_smalltalk(self, question: str) -> bool:
#         """
#         Nhận diện câu hỏi smalltalk / chào hỏi.
#         Hỗ trợ cả tiếng Việt có dấu và không dấu.
#         """
#         q = question.lower().strip()
#
#         # Loại bỏ dấu câu
#         q = re.sub(r'[?.!,;:]', '', q)
#
#         smalltalk_keywords = [
#             # Chào hỏi có dấu
#             "xin chào", "chào bạn", "chào", "chào buổi sáng", "chào buổi tối",
#             # Chào hỏi không dấu
#             "xin chao", "chao ban", "chao", "chao buoi sang", "chao buoi toi",
#             # Tiếng Anh
#             "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
#             # Cảm ơn có dấu
#             "cảm ơn", "cám ơn", "cảm ơn bạn", "cám ơn bạn",
#             # Cảm ơn không dấu
#             "cam on", "cam on ban",
#             # Tiếng Anh
#             "thank", "thanks", "thank you", "tks", "ty",
#             # Tạm biệt có dấu
#             "tạm biệt", "hẹn gặp lại", "gặp lại sau",
#             # Tạm biệt không dấu
#             "tam biet", "hen gap lai", "gap lai sau",
#             # Tiếng Anh
#             "bye", "goodbye", "see you", "see ya",
#             # Hỏi thăm có dấu
#             "bạn là ai", "tên gì", "khỏe không", "bạn ổn không", "bạn có khỏe không",
#             # Hỏi thăm không dấu
#             "ban la ai", "ten gi", "khoe khong", "ban on khong", "ban co khoe khong",
#             # Hỏi thăm tiếng Anh
#             "how are you", "what's up", "who are you", "what is your name",
#             # Các câu đơn giản
#             "alo", "yo", "hii", "hiii", "helloo", "helo"
#         ]
#
#         # Kiểm tra exact match trước
#         if q in smalltalk_keywords:
#             return True
#
#         # Kiểm tra contains
#         return any(k in q for k in smalltalk_keywords)
#
#     def smalltalk_answer(self, question: str) -> str:
#         """
#         Dùng Gemini trả lời smalltalk một cách thông minh và tự nhiên.
#         """
#         prompt = SMALLTALK_PROMPT_TEMPLATE.format(
#             history=self._history_to_text(),
#             question=question
#         )
#
#         try:
#             response = self.client.models.generate_content(
#                 model=GEMINI_MODEL,
#                 contents=prompt,
#                 config=types.GenerateContentConfig(
#                     temperature=0.7,  # Cao hơn để trả lời tự nhiên hơn
#                     max_output_tokens=150  # Ngắn gọn
#                 )
#             )
#             return response.text.strip() if response and response.text else "👋 Chào bạn! Mình có thể giúp gì cho bạn?"
#         except Exception as e:
#             logger.error(f"Gemini smalltalk error: {e}")
#             # Fallback nếu API lỗi
#             return "👋 Chào bạn! Mình là trợ lý thư viện AI. Bạn cần tìm sách gì hôm nay?"
#
#     def general_llm_answer(self, question: str) -> str:
#         """
#         Dùng Gemini trả lời các câu hỏi tổng quát khi không tìm thấy sách phù hợp.
#         """
#         prompt = GENERAL_QA_PROMPT_TEMPLATE.format(
#             history=self._history_to_text(),
#             question=question
#         )
#
#         try:
#             response = self.client.models.generate_content(
#                 model=GEMINI_MODEL,
#                 contents=prompt,
#                 config=types.GenerateContentConfig(
#                     temperature=0.5,
#                     max_output_tokens=MAX_OUTPUT_TOKENS
#                 )
#             )
#             return response.text.strip() if response and response.text else "❌ Tôi chưa có câu trả lời phù hợp."
#         except Exception as e:
#             logger.error(f"Gemini general QA error: {e}")
#             return "❌ Không thể trả lời câu hỏi này lúc này. Vui lòng thử lại sau."
#
#     def get_suggested_questions(self) -> List[str]:
#         # Danh sách gợi ý mặc định cho giao diện chat
#         return [
#             "Thư viện mở cửa lúc mấy giờ?",
#             "Làm sao để gia hạn sách?",
#             "Có sách nào về trí tuệ nhân tạo không?",
#             "Phí phạt trả sách trễ là bao nhiêu?",
#         ]
#
#     def _is_book_related_query(self, question: str) -> bool:
#         """
#         Kiểm tra xem câu hỏi có liên quan đến việc tìm/hỏi về sách không.
#         Dùng để quyết định có nên dùng cache sách hay không.
#         """
#         q = question.lower()
#         q = re.sub(r'[?.!,;:]', '', q)
#
#         book_keywords = [
#             # Từ khóa sách tiếng Việt
#             "sách", "cuốn", "quyển", "tài liệu", "giáo trình", "truyện",
#             "tiểu thuyết", "tác phẩm", "ebook", "pdf",
#             # Từ khóa sách không dấu
#             "sach", "cuon", "quyen", "tai lieu", "giao trinh", "truyen",
#             "tieu thuyet", "tac pham",
#             # Từ khóa tìm kiếm
#             "tìm", "tìm kiếm", "gợi ý", "đề xuất", "cho tôi", "có không",
#             "tim", "tim kiem", "goi y", "de xuat", "cho toi", "co khong",
#             # Thể loại sách
#             "python", "java", "programming", "lập trình", "lap trinh",
#             "machine learning", "ai", "deep learning", "data science",
#             "toán", "văn", "lịch sử", "địa lý", "vật lý", "hóa học",
#             "toan", "van", "lich su", "dia ly", "vat ly", "hoa hoc",
#             # Tiếng Anh
#             "book", "novel", "textbook", "recommend", "find", "search"
#         ]
#
#         return any(k in q for k in book_keywords)
#
#     # ==================================================
#     # FILTER GARBAGE QUERIES
#     # ==================================================
#     def is_garbage_query(self, query: str) -> bool:
#         """
#         Lọc các câu hỏi rác:
#         - Rỗng
#         - Quá ngắn
#         - Toàn số
#         - Không chứa chữ cái
#         """
#         if not query or not query.strip():
#             return True
#
#         q = query.strip().lower()
#
#         if len(q) < MIN_QUERY_LENGTH:
#             return True
#         if q.isdigit():
#             return True
#
#         # Không có chữ cái (kể cả tiếng Việt)
#         if not re.search(r"[a-zA-ZÀ-ỹ]", q):
#             return True
#
#         return False
#
#     # ==================================================
#     # 📊 NHẬN DIỆN CÂU HỎI THỐNG KÊ
#     # ==================================================
#     def is_library_stats_query(self, question: str) -> bool:
#         """
#         Ví dụ:
#         - "Thư viện có bao nhiêu cuốn sách?"
#         - "Tổng số sách là bao nhiêu?"
#         """
#         q = question.lower()
#         return any(k in q for k in [
#             "bao nhiêu sách",
#             "bao nhiêu cuốn",
#             "tổng số sách",
#             "số lượng sách",
#             "thư viện có bao nhiêu"
#         ])
#
#     # ==================================================
#     # 🏛️ NHẬN DIỆN CÂU HỎI NỘI QUY / GIỜ GIẤC
#     # ==================================================
#     def is_library_info_query(self, question: str) -> bool:
#         """
#         Ví dụ:
#         - Mấy giờ mở cửa?
#         - Quy định mượn sách?
#         - Phí phạt thế nào?
#         """
#         q = question.lower()
#         return any(k in q for k in [
#             "mở cửa",
#             "đóng cửa",
#             "giờ mở",
#             "giờ đóng",
#             "giờ làm việc",
#             "nội quy",
#             "quy định",
#             "mượn sách",
#             "trả sách",
#             "gia hạn",
#             "phí phạt"
#         ])
#
#     # ==================================================
#     # 🧠 NHẬN DIỆN FOLLOW-UP QUESTION
#     # ==================================================
#     def is_followup_query(self, question: str) -> bool:
#         """
#         Ví dụ:
#         - "Cuốn thứ thì sao?"
#         - "Cuốn này ai viết?"
#         - "Trong số các cuốn đó, cuốn nào dễ học nhất?"
#         """
#         if not self.last_docs:
#             return False
#
#         q = question.lower()
#         keywords = [
#             "cuốn này",
#             "cuốn đó",
#             "cuốn thứ",
#             "sách này",
#             "sách đó",
#             "trong số",
#             "cuốn nào",
#             "cái nào",
#             "dễ học",
#             "tốt nhất",
#             "phù hợp",
#             "nên chọn",
#             "ở trên",
#             "vừa rồi",
#             "trong danh sách",
#         ]
#         return any(k in q for k in keywords)
#
#     def answer_followup(self, question: str) -> str:
#         """
#         Trả lời follow-up dựa trên danh sách sách lần trước.
#         - Nếu có chỉ mục ("cuốn thứ 2") thì trả về sách tương ứng.
#         - Nếu là câu chọn lọc ("cuốn nào dễ học nhất") thì dùng LLM tổng hợp trên danh sách hiện có.
#         """
#         if not self.last_docs:
#             return "❌ Tôi chưa có danh sách sách để tham chiếu."
#
#         q = question.lower()
#         match = re.search(r"thứ\s*(\d+)", q)
#         if match:
#             idx = int(match.group(1)) - 1
#             if 0 <= idx < len(self.last_docs):
#                 b = self.last_docs[idx]
#                 snippet = self._shorten_text(b.get("richtext") or b.get("snippet"))
#                 return (
#                     f"📘 **{b['title']}**\n"
#                     f"- Tác giả: {b['authors']}\n"
#                     f"- Năm xuất bản: {b['publish_year']}\n\n"
#                     f"{snippet}"
#                 )
#             return "❌ Không tìm thấy cuốn sách bạn yêu cầu."
#
#         books_context = self._books_to_context(self.last_docs)
#         prompt = FOLLOWUP_PROMPT_TEMPLATE.format(
#             history=self._history_to_text(),
#             previous_books=books_context,
#             question=question
#         )
#         try:
#             response = self.client.models.generate_content(
#                 model=GEMINI_MODEL,
#                 contents=prompt,
#                 config=types.GenerateContentConfig(
#                     temperature=min(TEMPERATURE, 0.5),
#                     max_output_tokens=MAX_OUTPUT_TOKENS
#                 )
#             )
#             return response.text.strip() if response and response.text else "❌ Tôi chưa xác định được câu trả lời."
#         except Exception as e:
#             logger.error(f"Gemini follow-up error: {e}")
#             return "❌ Không thể trả lời câu hỏi follow-up."
#
#     # ==================================================
#     # 🧠 CÓ CẦN GỌI LLM ĐỂ TỔNG HỢP KHÔNG?
#     # ==================================================
#     def needs_synthesis(self, question: str) -> bool:
#         """
#         Nếu chỉ hỏi:
#         - "Sách về AI" → chỉ list
#
#         Nếu hỏi:
#         - "Nên đọc sách nào?"
#         - "So sánh giúp tôi"
#         → cần LLM tổng hợp
#         """
#         q = question.lower()
#         return any(k in q for k in [
#             "nên",
#             "phù hợp",
#             "gợi ý",
#             "so sánh",
#             "đánh giá",
#             "phân tích",
#             "tổng hợp",
#             "giải thích",
#             "vì sao",
#             "như thế nào"
#         ])
#
#     # ==================================================
#     # 🎯 LỌC THEO SCORE
#     # ==================================================
#     def apply_score_threshold(self, docs):
#         """
#         Nếu document tốt nhất < threshold → coi như không có kết quả
#         """
#         if not docs:
#             return []
#
#         best = max(d.get("score", 0) for d in docs)
#         return docs if best >= SCORE_THRESHOLD else []
#
#     # ==================================================
#     # 🏛️ BUILD CONTEXT NỘI QUY THƯ VIỆN
#     # ==================================================
#     def _build_library_context(self) -> dict:
#         """
#         Convert LIBRARY_INFO thành text cho prompt
#         """
#         return {
#             "opening_hours": LIBRARY_INFO["opening_hours"],
#             "library_rules": "\n".join(f"- {r}" for r in LIBRARY_INFO["library_rules"]),
#             "borrow_policy": "\n".join(
#                 f"- {k}: {v}" for k, v in LIBRARY_INFO["borrow_policy"].items()
#             ),
#             "penalty_policy": "\n".join(
#                 f"- {k}: {v}" for k, v in LIBRARY_INFO["penalty_policy"].items()
#             ),
#         }
#
#     # ==================================================
#     # 🤖 FALLBACK KHI KHÔNG CÓ DATA
#     # ==================================================
#     def gemini_fallback(self, question: str) -> str:
#         """
#         Gọi Gemini trả lời chung chung nhưng:
#         - Phải nói rõ là thư viện không có dữ liệu
#         - Không được bịa sách
#         """
#         prompt = f"""
# Bạn là trợ lý thư viện AI.
#
# Thư viện KHÔNG có dữ liệu phù hợp cho câu hỏi:
# "{question}"
#
# Yêu cầu:
# - Nói rõ không có dữ liệu
# - KHÔNG bịa tên sách
# """
#         try:
#             response = self.client.models.generate_content(
#                 model=GEMINI_MODEL,
#                 contents=prompt,
#                 config=types.GenerateContentConfig(
#                     temperature=TEMPERATURE,
#                     max_output_tokens=MAX_OUTPUT_TOKENS
#                 )
#             )
#             return response.text.strip() if response and response.text else "❌ Xin lỗi, tôi không thể trả lời câu hỏi này."
#         except Exception as e:
#             logger.error(f"Gemini fallback error: {e}")
#             return "❌ Xin lỗi, thư viện không có thông tin phù hợp với câu hỏi của bạn."
#
#     # ==================================================
#     # GENERATE ANSWER
#     # ==================================================
#     def generate_answer(self, question: str) -> str:
#
#         # ==================================================
#         # ️⃣ CHẶN CÂU HỎI RÁC
#         # ==================================================
#         if self.is_garbage_query(question):
#             return "❌ Câu hỏi không hợp lệ hoặc quá ngắn."
#
#         # ==================================================
#         # ️⃣ SMALLTALK / CHÀO HỎI (bỏ qua cache để tránh hit sách cũ)
#         # ==================================================
#         if self.is_smalltalk(question):
#             answer = self.smalltalk_answer(question)
#             self._add_history("user", question)
#             self._add_history("assistant", answer)
#             return answer
#
#         # ==================================================
#         # ️⃣ QUERY MEMORY (CACHE CÂU HỎI CŨ)
#         # ==================================================
#         q_vec = self.embedder.embed_text(question, is_query=True)
#         if q_vec:
#             cached = self.vector_db.search_query_memory(
#                 q_vec, threshold=QUERY_CACHE_THRESHOLD
#             )
#             # Skip cache nếu cache answer là danh sách sách nhưng query không liên quan sách
#             if cached:
#                 is_book_cache = "📚 Danh sách sách" in cached or "Danh sách sách liên quan" in cached
#                 if is_book_cache and not self._is_book_related_query(question):
#                     logger.info("⚠️ Query memory SKIP (cached books for non-book query)")
#                 else:
#                     logger.info("⚡ Query memory HIT")
#                     answer = f"⚡ {cached}"
#                     self._add_history("user", question)
#                     self._add_history("assistant", answer)
#                     return answer
#
#         # ==================================================
#         # ️⃣ THỐNG KÊ
#         # ==================================================
#         if self.is_library_stats_query(question):
#             total = self.vector_db.get_collection_stats().get("count", 0)
#             answer = f"📚 Hiện tại thư viện có **{total} cuốn sách** trong hệ thống."
#
#             self.vector_db.add_query_memory(
#                 question, q_vec, answer, qtype="stats"
#             )
#             self._add_history("user", question)
#             self._add_history("assistant", answer)
#             return answer
#
#         # ==================================================
#         # ️⃣ NỘI QUY / GIỜ GIẤC
#         # ==================================================
#         if self.is_library_info_query(question):
#             ctx = self._build_library_context()
#             prompt = f"""{SYSTEM_PROMPT}
#
# Lịch sử hội thoại gần đây:
# {self._history_to_text()}
#
# {USER_PROMPT_TEMPLATE.format(
#     question=question,
#     books="(Không áp dụng)",
#     **ctx
# )}
# """
#             try:
#                 response = self.client.models.generate_content(
#                     model=GEMINI_MODEL,
#                     contents=prompt,
#                     config=types.GenerateContentConfig(
#                         temperature=TEMPERATURE,
#                         max_output_tokens=MAX_OUTPUT_TOKENS
#                     )
#                 )
#                 answer = response.text.strip() if response and response.text else "❌ Không th��� trả lời câu hỏi này."
#             except Exception as e:
#                 logger.error(f"Gemini API error: {e}")
#                 answer = "❌ Không thể trả lời câu hỏi này."
#
#             self.vector_db.add_query_memory(
#                 question, q_vec, answer, qtype="library_info"
#             )
#             self._add_history("user", question)
#             self._add_history("assistant", answer)
#             return answer
#
#         # ==================================================
#         # ️⃣ FOLLOW-UP (KHÔNG CACHE)
#         # ==================================================
#         if self.is_followup_query(question):
#             answer = self.answer_followup(question)
#             self._add_history("user", question)
#             self._add_history("assistant", answer)
#             return answer
#
#         # ==================================================
#         # ️⃣ BOOK RAG PIPELINE
#         # ==================================================
#         raw_docs = self.search_engine.search(
#             query=question,
#             top_k=self.top_k * SEARCH_EXPAND_FACTOR
#         )
#
#         # Lọc theo score
#         docs = self.apply_score_threshold(raw_docs)
#
#         if docs:
#             # Lưu lại để dùng cho follow-up
#             self.last_docs = docs[:self.top_k]
#             self.last_books_text = "\n".join(
#                 f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
#                 for i, d in enumerate(self.last_docs, 1)
#             )
#
#             # Build danh sách sách
#             book_lines = [
#                 f"{i}. {d['title']} – {d['authors']} ({d['publish_year']})"
#                 for i, d in enumerate(self.last_docs, 1)
#             ]
#
#             books_text = "\n".join(book_lines)
#
#             # ==================================================
#             # .️⃣ CHỈ LIST, KHÔNG TỔNG HỢP
#             # ==================================================
#             if not self.needs_synthesis(question):
#                 answer = f"📚 Danh sách sách liên quan\n\n{books_text}"
#
#                 self.vector_db.add_query_memory(
#                     question, q_vec, answer, qtype="rag_list"
#                 )
#                 self._add_history("user", question)
#                 self._add_history("assistant", answer)
#                 return answer
#
#             # ==================================================
#             # .️⃣ CÓ GỌI LLM ĐỂ TỔNG HỢP
#             # ==================================================
#             ctx = self._build_library_context()
#
#             prompt = f"""{SYSTEM_PROMPT}
#
# Lịch sử hội thoại gần đây:
# {self._history_to_text()}
#
# {USER_PROMPT_TEMPLATE.format(
#     question=question,
#     books=books_text,
#     **ctx
# )}
# """
#             try:
#                 response = self.client.models.generate_content(
#                     model=GEMINI_MODEL,
#                     contents=prompt,
#                     config=types.GenerateContentConfig(
#                         temperature=TEMPERATURE,
#                         max_output_tokens=MAX_OUTPUT_TOKENS
#                     )
#                 )
#                 synthesis = response.text.strip() if response and response.text else "❌ Không thể tổng hợp thông tin."
#             except Exception as e:
#                 logger.error(f"Gemini API error: {e}")
#                 synthesis = "❌ Không thể tổng hợp thông tin."
#
#             answer = f"""📚 Danh sách sách liên quan
#
# {books_text}
#
# 📝 Tổng hợp
# {synthesis}
# """
#             self.vector_db.add_query_memory(
#                 question, q_vec, answer, qtype="rag_synthesis"
#             )
#             self._add_history("user", question)
#             self._add_history("assistant", answer)
#             return answer
#
#         # ==================================================
#         # ️⃣ FALLBACK: KHÔNG CÓ DATA → DÙNG LLM TỔNG QUÁT
#         # ==================================================
#         answer = self.general_llm_answer(question)
#         self._add_history("user", question)
#         self._add_history("assistant", answer)
#         return answer
# >>>>>>> Long
