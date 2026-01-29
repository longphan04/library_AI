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
import unicodedata
from typing import List, Dict


def remove_diacritics(text: str) -> str:
    """
    Remove Vietnamese diacritics from text.
    Example: "xin chào" -> "xin chao"
    """
    # Normalize to NFD form (separates base char and diacritics)
    # Normalize to NFD form (separates base char and diacritics)
    nfkd_form = unicodedata.normalize('NFD', text)
    # Remove combining diacritical marks
    text_without_accent = ''.join(c for c in nfkd_form if not unicodedata.combining(c))
    # Manual replace for 'đ' and 'Đ' which are not decomposable in NFD
    return text_without_accent.replace('đ', 'd').replace('Đ', 'D')

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
# PROMPT TEMPLATES (THÊM TỪ HEAD)
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

Trả lời ngắn gọn (1-3 câu), thân thiện. KHÔNG dùng emoji.
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

Trả lời bằng tiếng Việt, thân thiện, chính xác.
KHÔNG dùng emoji/icon. KHÔNG dùng định dạng bôi đen (**text**).
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
5. Trả lời ngắn gọn, đi thẳng vào vấn đề.
6. KHÔNG dùng icon/emoji. KHÔNG dùng định dạng bôi đen (**text**).
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
    RAGEngine (Merged Version)
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
    # SMALLTALK DETECTION (THÊM TỪ HEAD)
    # ==================================================
    # Lý do thêm: Phiên bản HEAD có nhận diện smalltalk chi tiết hơn,
    # hỗ trợ cả tiếng Việt có dấu và không dấu, giúp bot phản hồi
    # chính xác hơn khi user chào hỏi

    def is_smalltalk(self, question: str) -> bool:
        """
        Nhan dien cau hoi smalltalk / chao hoi.
        Ho tro ca tieng Viet co dau va khong dau (normalize thanh khong dau).
        """
        # Normalize: lowercase, remove punctuation, remove diacritics
        q = question.lower().strip()
        q = re.sub(r'[?.!,;:]', '', q)
        q = remove_diacritics(q)  # Convert "xin chào" -> "xin chao"
        
        # FIX: Exclude book-related help requests like "giúp tôi tìm sách python"
        help_keywords = ["giup toi", "giup minh", "help", "help me", "ho tro"]
        book_context_keywords = ["sach", "cuon", "quyen", "tim", "co", "muon"]
        
        # Check if query contains help keyword (substring match)
        has_help = any(help_kw in q for help_kw in help_keywords)
        # Check if query contains book keyword
        has_book_context = any(book_kw in q for book_kw in book_context_keywords)
        
        # If it has BOTH help AND book context, it's a book query, NOT smalltalk
        if has_help and has_book_context:
            return False

        smalltalk_keywords = [
            # Chao hoi
            "xin chao", "chao ban", "chao", "chao buoi sang", "chao buoi toi",
            "chao buoi trua", "chao buoi chieu",
            # Tieng Anh
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
            # Cam on
            "cam on", "cam on ban", "cam on nhieu",
            # Tieng Anh
            "thank", "thanks", "thank you", "tks", "ty",
            # Tam biet
            "tam biet", "hen gap lai", "gap lai sau", "bye bye",
            # Tieng Anh
            "bye", "goodbye", "see you", "see ya",
            # Hoi tham
            "ban la ai", "ten gi", "khoe khong", "ban on khong", "ban co khoe khong",
            # Tieng Anh
            "how are you", "what's up", "who are you", "what is your name",
            # Cac cau don gian
            "alo", "yo", "hii", "hiii", "helloo", "helo",
            # Xin loi / OK
            "xin loi", "sorry", "ok", "okay", "duoc", "duoc roi", "dc", "dk",
            # Giup do (only if no book context)
            "giup toi", "giup minh", "help", "help me", "ho tro"
        ]

        if q in smalltalk_keywords:
            return True

        # Use simple word boundary check for all keywords to avoid false positives
        # E.g. "hi" should NOT match "chi tiet"
        q_words = set(q.split())
        for k in smalltalk_keywords:
            # If keyword is single word, check if it exists in word set
            if " " not in k:
                if k in q_words:
                    return True
            # If keyword matches exactly part of the phrase (simpler than regex)
            elif k in q:
                return True

        return False

    def answer_smalltalk(self, question: str, session: ChatSession) -> str:
        """
        Tra loi smalltalk. Uu tien tra loi san, chi goi AI khi can.
        """
        q = remove_diacritics(question.lower().strip())
        q = re.sub(r'[?.!,;:]', '', q)

        # Hardcoded responses - KHONG CAN GOI AI
        greetings = ["xin chao", "chao ban", "chao", "hello", "hi", "hey", "alo", "yo"]
        thanks = ["cam on", "cam on ban", "thanks", "thank you", "tks", "ty"]
        goodbyes = ["tam biet", "bye", "goodbye", "see you", "hen gap lai"]
        who_are_you = ["ban la ai", "ten gi", "who are you", "what is your name"]
        how_are_you = ["khoe khong", "ban on khong", "how are you", "what's up"]
        helps = ["giup toi", "giup minh", "help", "ho tro"]
        oks = ["ok", "okay", "duoc", "duoc roi", "dc", "dk"]

        q_words = set(q.split())

        def check_keywords(keywords):
            for k in keywords:
                if " " not in k: # Single word -> check word set
                    if k in q_words: return True
                elif k in q: # Multi word -> check substring
                    return True
            return False

        # Check and return hardcoded response
        if check_keywords(greetings):
            return "Xin chào! Tôi là trợ lý thư viện AI. Tôi có thể giúp bạn tìm sách, tra cứu thông tin thư viện. Bạn cần gì nào?"

        if check_keywords(thanks):
            return "Không có gì! Nếu bạn cần gì thêm, cứ hỏi nhé!"

        if check_keywords(goodbyes):
            return "Tạm biệt! Hẹn gặp lại bạn!"

        if check_keywords(who_are_you):
            return "Tôi là Trợ lý AI của Thư viện. Tôi có thể giúp bạn tìm sách, tra cứu giờ mở cửa, nội quy và các thông tin khác về thư viện."

        if check_keywords(how_are_you):
            return "Tôi vẫn khỏe! Cảm ơn bạn đã hỏi. Bạn cần tìm sách gì hôm nay?"

        if check_keywords(helps):
            return "Tôi có thể giúp bạn: Tìm sách theo chủ đề, tác giả hoặc thể loại; Tra cứu giờ mở cửa thư viện; Xem nội quy và quy định mượn sách. Bạn muốn làm gì?"

        if check_keywords(oks):
            return "Vâng! Nếu bạn cần gì thêm, cứ hỏi nhé!"

        # Fallback to AI for complex/unknown smalltalk
        try:
            prompt = SMALLTALK_PROMPT_TEMPLATE.format(
                history=session.get_history_text(),
                question=question
            )
            return self._call_gemini(prompt, temperature=0.7, max_tokens=150)
        except Exception:
            return "Xin chào! Tôi là trợ lý thư viện AI. Tôi có thể giúp gì cho bạn?"

    # ==================================================
    # BOOK RELATED CHECK (THÊM TỪ HEAD)
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
        q_normalized = remove_diacritics(q)  # Normalize for keyword matching

        # 1. Garbage check
        if len(q) < 2 or not re.search(r"[a-zA-Z\u00c0-\u1ef90-9]", q):
            return "GARBAGE"

        # 1b. Library stats check: uu tien cao
        if self.is_library_stats_query(query):
            return "STATS"

        # 2. Smalltalk check
        if self.is_smalltalk(query):
            return "SMALLTALK"

        # 3. Library info check
        if self.is_library_info_query(query):
            return "LIBRARY_INFO"
        
        # 3b. TITLE_SEARCH check (NEW - High Priority)
        # Detect explicit book title queries
        if self._is_title_search_query(query):
            return "TITLE_SEARCH"

        # 4. Follow-up check
        if session.last_search_results:
            followup_keywords = [
                "cuon nay", "cuon do", "cuon thu", "sach nay", "sach do",
                "chi tiet", "no noi ve", "tac gia la ai", "gia bao nhieu",
                "trong so", "cuon nao", "cai nao", "de hoc", "tot nhat",
                "phu hop", "nen chon", "o tren", "vua roi", "trong danh sach",
                "hay nhat", "hay hon", "tot hon", "noi ve gi", "ve cai gi",
                "cua ai", "ai viet", "nam nao", "xuat ban nam", "may trang",
                "nen doc", "doc truoc", "doc sau", "cuon dau", "cuon cuoi"
            ]
            if any(k in q_normalized for k in followup_keywords):
                return "FOLLOWUP"
            if re.search(r"(cuon|so|quyen)\s*\d+", q_normalized):
                return "FOLLOWUP"

        # 5. Default
        return "SEARCH"

    def is_library_stats_query(self, q: str) -> bool:
        ql = remove_diacritics(q.lower())
        # Regex for flexible matching:
        # 1. "bao nhieu" + anything + "sach/cuon/quyen/tac pham"
        # 2. "tong so" + "sach"
        # 3. "so luong" + "sach"
        patterns = [
            r"bao nhieu.*(?:sach|cuon|quyen|tac pham)",
            r"(?:tong so|so luong).*(?:sach|cuon|quyen|tac pham)",
            r"co.*bao nhieu", # "thu vien co bao nhieu"
            r"co.*tat ca"      # "co tat ca bao nhieu..."
        ]
        
        for p in patterns:
            if re.search(p, ql):
                return True
        return False
    
    def is_library_info_query(self, q: str) -> bool:
        """
        Detect library information queries (opening hours, rules, policies).
        """
        ql = remove_diacritics(q.lower())
        
        # Opening hours - check ALL possible combinations
        has_opening_words = any(word in ql for word in ["mo cua", "dong cua", "mo", "dong"])
        has_time_words = any(word in ql for word in ["gio", "luc", "may", "thoi gian"])
        
        if has_opening_words and has_time_words:
            return True
        
        if "gio" in ql and ("hoat dong" in ql or "lam viec" in ql):
            return True
        
        # Rules and policies
        if any(kw in ql for kw in ["noi quy", "quy dinh", "quy tac"]):
            return True
        
        # Borrowing/returning
        if ("muon sach" in ql or "muon" in ql) and ("the nao" in ql or "quy dinh" in ql):
            return True
        if ("tra sach" in ql or "tra" in ql) and ("the nao" in ql or "quy dinh" in ql):
            return True
        
        # Penalties
        if any(kw in ql for kw in ["phi phat", "phat", "penalty"]):
            return True
        
        return False

    def _is_title_search_query(self, query: str) -> bool:
        """
        Detect if query is explicitly searching for a specific book title.
        Examples: "tìm cuốn Sapiens", "có sách Clean Code không", "tìm sách Trò chuyện khoa học"
        NOTE: "tìm sách về toán" is NOT a title search (it's category search)
        """
        q_norm = remove_diacritics(query.lower())
        
        # Patterns indicating explicit title search
        # FIXED: "sach" alone is too broad; require more specific patterns
        title_indicators = [
            r"(?:tim|co|muon|kiem)\s+cuon\s+([a-z0-9\s]{3,})",  # "tìm cuốn [Title]" - cuốn is more specific
            r"(?:cuon|quyen)\s+(?:ten|tua|co ten)\s+(?:la\s+)?([a-z0-9\s]{3,})",  # "cuốn tên là [Title]"
        ]
        
        for pattern in title_indicators:
            match = re.search(pattern, q_norm)
            if match:
                potential_title = match.group(1).strip()
                
                # FIXED: Expanded category keywords list and use substring check
                category_keywords = [
                    "toan", "ly", "hoa", "van", "su", "dia", "sinh",
                    "kinh te", "tai chinh", "marketing", "lap trinh",
                    "python", "java", "ai", "machine learning",
                    "van hoc", "lich su", "khoa hoc", "tam ly", "triet hoc",
                    "kinh doanh", "quan tri", "ky nang", "ngoai ngu"
                ]
                
                # FIXED: Check if potential_title starts with "ve " (common false positive)
                if potential_title.startswith("ve "):
                    return False
                
                # FIXED: Use substring match instead of exact equality
                is_category = any(kw in potential_title or potential_title in kw for kw in category_keywords)
                
                # If captured text is NOT a category keyword, it's likely a title
                if len(potential_title) >= 3 and not is_category:
                    return True
        
        return False

    def _normalize_query(self, query: str) -> str:
        """
        Query preprocessing pipeline: remove noise, standardize synonyms.
        Improves classification and filter extraction accuracy.
        """
        q = query.strip().lower()
        
        # 1. Remove Vietnamese noise/filler words
        noise_words = ["ơi", "à", "ạ", "nhé", "nha", "đi", "cho tôi", "giúp tôi", "cho mình", "giúp mình"]
        for noise in noise_words:
            q = q.replace(noise, "")
        
        # 2. Standardize synonyms (book-related)
        synonym_map = {
            "quyển": "cuốn",
            "tác phẩm": "sách",
            "ebook": "sách",
        }
        for old, new in synonym_map.items():
            q = q.replace(old, new)
        
        # 3. Normalize spacing (remove extra spaces)
        q = re.sub(r'\s+', ' ', q).strip()
        
        return q

    def _normalize_book_query(self, question: str) -> str:
        """Chuan hoa mot so cau goi y de search trung chu de hon."""
        q = question.strip()
        ql = remove_diacritics(q.lower())

        # Neu user hoi kieu: "Sach Machine Learning hay nhat"
        if "machine learning" in ql and "sach" in ql:
            return "sach machine learning"

        # "Tim sach ve Python" hay "sach python"
        if "python" in ql and ("tim" in ql or "sach" in ql):
            return "sach python"

        return q

    # ==================================================
    # HANDLERS
    # ==================================================
    def answer_greeting(self) -> str:
        return "Xin chào! Tôi là trợ lý thư viện AI. Tôi có thể giúp gì cho bạn hôm nay? (Tìm sách, hỏi nội quy, v.v...)"

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
                f"{b['title']}\n"
                f"- Tác giả: {b['authors']}\n"
                f"- Năm xuất bản: {b['publish_year']}\n"
                f"- Mã sách: {b['identifier']}\n\n"
                f"Nội dung:\n{b.get('richtext','')[:1000]}..."
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

    def _extract_filters_from_text(self, query: str) -> dict:
        """
        AI Auto-Extraction: Tự động rút trích filter từ câu hỏi user.
        Dựa trên danh sách Categories/Authors có sẵn trong DB và Settings.
        Hỗ trợ nhận diện qua Regex và Keyword Matching.
        """
        extracted = {}
        q_norm = remove_diacritics(query.lower())
        
        # 1. Get metadata source
        available_filters = self.search_engine.get_filters()
        db_categories = available_filters.get("categories", [])
        db_authors = available_filters.get("authors", [])
        
        # Merge with hardcoded topics from Settings for better coverage
        from config.settings import settings
        all_categories = list(set(db_categories + settings.CRAWL_TOPICS))
        
        # 2. DEFINED MAPPINGS (Synonyms)
        # Map short/common terms to EXACT category names in DB
        # Based on final_categories.md: "Toán", "Kinh tế", "Văn học", "Máy tính", etc.
        category_map = {
            "python": "Máy tính", # Or "Lập trình" if exists? Let's check logic. Actually DB likely has "Máy tính" or "Công nghệ thông tin"
            "cntt": "Công nghệ thông tin",
            "it": "Công nghệ thông tin",
            "ai": "Trí tuệ và Dữ liệu",
            "tri tue nhan tao": "Trí tuệ và Dữ liệu",
            "machine learning": "Trí tuệ và Dữ liệu",
            "hoc may": "Trí tuệ và Dữ liệu",
            "data science": "Trí tuệ và Dữ liệu",
            "khoa hoc du lieu": "Trí tuệ và Dữ liệu",
            "toan": "Toán",
            "toan hoc": "Toán",
            "ly": "Vật lý",
            "vat ly": "Vật lý",
            "hoa": "Hóa học",
            "hoa hoc": "Hóa học",
            "van": "Văn học",
            "van hoc": "Văn học",
            "kinh te": "Kinh tế",
            "kinh te hoc": "Kinh tế",
            "marketing": "Marketing",
            "ky nang": "Kỹ năng",
            "tam ly": "Tâm lý",
            "tam ly hoc": "Tâm lý"
        }

        # 3. REGEX EXTRACTION (Explicit Intent)
        # Note: Input `q_norm` has NO diacritics. Patterns must accept non-diacritic keywords.
        
        # Capture "chủ đề X", "sách về X" -> "chu de X", "sach ve X"
        cat_patterns = [
            r"(?:ve|chu de|mon|linh vuc|loai|the loai|danh muc)\s+([\w\s]+)",
            r"sach\s+([\w\s]+)" 
        ]
        
        # Capture "tác giả Y", "của Y" -> "tac gia Y", "cua Y"
        auth_patterns = [
            r"(?:tac gia|boi|viet boi|cua|soan boi)\s+([\w\s]+)"
        ]

        # Capture "năm YYYY", "xuất bản YYYY" -> "nam", "xuat ban"
        year_patterns = [
            r"(?:nam|xuat ban|xb)\s+(\d{4})",
            r"(\d{4})" # Standalone year check
        ]

        # Capture Title explicitly: "cuốn X", "quyển X" -> "cuon X", "quyen X"
        # Note: "sach" is ambiguous (sach python -> category), so we avoid it for title unless "sách tên là"
        title_patterns = [
            r"(?:cuon|quyen|tac pham|tieu de|tua de)\s+(?:sach\s+)?(.+)",
            r"sach\s+(?:ten|tua|co ten|co tua)\s+(?:la\s+)?(.+)"
        ]

        # 3a. Try extracting Year
        db_years = available_filters.get("years", [])
        for pattern in year_patterns:
            match = re.search(pattern, q_norm)
            if match:
                y = match.group(1)
                # Validation: Must be in DB years or reasonable range (1900-2030)
                if y in db_years or (y.isdigit() and 1900 <= int(y) <= 2030):
                    extracted["publish_year"] = y
                    break

        # 3b. Try extracting Title (Prioritize explicit title indicators)
        for pattern in title_patterns:
            match = re.search(pattern, q_norm)
            if match:
                raw_title = match.group(1).strip()
                
                # --- FIX: Prevent false positive title extraction ---
                # Blacklist common category keywords that should NOT be titles
                category_keywords = [
                    "toan", "ly", "hoa", "van", "su", "dia", "sinh", 
                    "kinh te", "tai chinh", "marketing", "lap trinh", "cntt",
                    "python", "java", "ai", "machine learning", "data science",
                    "ky nang", "tam ly", "triet hoc", "van hoc", "khoa hoc"
                ]
                
                # Check if raw_title is a category-like keyword
                is_category_keyword = any(kw in raw_title for kw in category_keywords)
                
                # Also check if it matches "ve [topic]" pattern (common false positive)
                is_ve_pattern = raw_title.startswith("ve ") or " ve " in raw_title
                
                # Only accept as title if:
                # 1. Not too short (> 2 chars)
                # 2. Not a category keyword
                # 3. Not a "ve [topic]" pattern (unless very specific like "cuốn Trò chuyện...")
                if len(raw_title) > 2 and not is_category_keyword and not is_ve_pattern:
                    extracted["title"] = raw_title
                    break


        # 3c. Try extracting Author via Regex
        for pattern in auth_patterns:
            match = re.search(pattern, q_norm)
            if match:
                potential_auth = match.group(1).strip()
                # Check validity against DB authors (partial match)
                for auth in db_authors:
                    username_norm = remove_diacritics(auth.lower())
                    if potential_auth in username_norm or username_norm in potential_auth:
                        extracted["authors"] = auth
                        break
            if "authors" in extracted: break

        # 3c. Try extracting Category via Regex or Map
        # First check synonyms map
        for key, full_cat in category_map.items():
            # Fix: Use word boundary to avoid partial match (e.g. "hoa" in "khoa hoc")
            if re.search(r'\b' + re.escape(key) + r'\b', q_norm):
                extracted["category"] = full_cat
                break
        
        # If not found via map, try regex and fuzzy match with DB
        if "category" not in extracted:
            sorted_cats = sorted(all_categories, key=len, reverse=True)
            for cat in sorted_cats:
                cat_norm = remove_diacritics(cat.lower())
                # Direct match
                if cat_norm in q_norm:
                    extracted["category"] = cat 
                    break 

            # If still not found, try regex patterns for explicit category intent
            if "category" not in extracted:
                for pattern in cat_patterns:
                    match = re.search(pattern, q_norm)
                    if match:
                        potential_cat = match.group(1).strip()
                        # Fuzzy check against DB
                        for cat in sorted_cats:
                            cat_norm = remove_diacritics(cat.lower())
                            if cat_norm in potential_cat or potential_cat in cat_norm:
                                extracted["category"] = cat
                                break
                    if "category" in extracted: break

        if extracted:
            logger.info(f"Auto-extracted filters: {extracted}")
            
        return extracted

    def _enrich_query_context(self, query: str) -> str:
        """
        AI Semantic Steering: Bổ sung từ khóa tiếng Anh vào query
        để Vector Search hiểu rõ hơn ngữ cảnh (đặc biệt là Audience & Language).
        """
        q_norm = remove_diacritics(query.lower())
        enriched_query = query
        
        # 1. AUDIENCE STEERING (Beginner vs Advanced)
        if any(k in q_norm for k in ["co ban", "nhap mon", "nguoi moi", "bat dau", "so cap"]):
            enriched_query += " (beginner introduction tutorial)"
        elif any(k in q_norm for k in ["nang cao", "chuyen sau", "chuyen gia", "phan tich", "tong hop"]):
            enriched_query += " (advanced in-depth analysis)"
            
        # 2. LANGUAGE STEERING
        if any(k in q_norm for k in ["tiếng anh", "tieng anh", "english", "nuoc ngoai"]):
            enriched_query += " (English edition foreign language)"
            
        if enriched_query != query:
            logger.info(f"Query Enriched: '{query}' -> '{enriched_query}'")
            
        return enriched_query

    def generate_answer(self, question: str, session_id: str = "default", filters: dict = None) -> Dict:
        """
        Generate answer for a chat question.
        Handles Search vs Info vs Smalltalk vs Stats.
        """
        try:
            session = self.get_session(session_id)
            session.add_message("user", question)
            
            # --- FIX: Check Smalltalk/Library Info with ORIGINAL query ---
            # These intents depend on exact phrases like "xin chào" which get stripped by normalization
            if self.is_smalltalk(question):
                intent = "SMALLTALK"
            elif self.is_library_stats_query(question):
                intent = "STATS"
            elif self.is_library_info_query(question):
                intent = "LIBRARY_INFO"
            else:
                # For other intents, use normalized query for better matching
                normalized_question = self._normalize_query(question)
                intent = self.classify_intent(normalized_question, session)
            
            # --- FEATURE ADDED: Auto-extract filters if none provided ---
            extracted_filters = {}
            if intent == "SEARCH" and not filters:
                extracted_filters = self._extract_filters_from_text(question)
                if extracted_filters:
                    filters = extracted_filters
            # -----------------------------------------------------------

            logger.info(f"Session: {session_id} | Intent: {intent} | Query: {question} | Filters: {filters}")

            answer = ""
            sources = [] 

            if intent == "GARBAGE":
                answer = "Câu hỏi không hợp lệ hoặc quá ngắn."

            elif intent == "SMALLTALK":
                answer = self.answer_smalltalk(question, session)

            elif intent == "FOLLOWUP":
                answer = self.answer_followup(question, session)

            elif intent == "STATS":
                total = self.vector_db.get_collection_stats().get("count", 0)
                answer = f"Hiện tại thư viện có {total} cuốn sách trong hệ thống."

            elif intent == "LIBRARY_INFO":
                answer = self._generate_library_info_answer(question, session)
            
            elif intent == "TITLE_SEARCH":
                # NEW: Optimized path for explicit title queries
                # Extract title and perform strict title-only search
                extracted_filters = self._extract_filters_from_text(question)
                if "title" in extracted_filters:
                    # Override filters to ONLY use title (highest precision)
                    title_filter = {"title": extracted_filters["title"]}
                    answer, sources = self._perform_book_search(question, session, filters=title_filter)
                else:
                    # Fallback if title extraction failed (use normal SEARCH)
                    normalized_query = self._normalize_book_query(question)
                    answer, sources = self._perform_book_search(normalized_query, session, filters=filters)

            else:  # SEARCH
                normalized_query = self._normalize_book_query(question)
                answer, sources = self._perform_book_search(normalized_query, session, filters=filters)

            session.add_message("model", answer)

            return {
                "answer": answer,
                "intent": intent,
                "sources": sources
            }
        except Exception as e:
            logger.error(f"Critical error in generate_answer: {str(e)}")
            return {
                "answer": "Xin lỗi, hệ thống đang gặp sự cố kỹ thuật. Vui lòng thử lại sau.",
                "intent": "ERROR",
                "sources": []
            }

    # ==================================================
    # SUB-HANDLERS
    # ==================================================
    def is_library_info_query(self, q: str) -> bool:
        ql = remove_diacritics(q.lower())
        # Keywords for library info must be specific to RULES/POLICIES, not just actions
        # "muon sach" alone is ambiguous (could be search), so query must imply "how to" or "rules"
        keywords = [
            "gio mo cua", "thoi gian mo cua", "lich mo cua",
            "quy dinh", "noi quy", "luat thu vien",
            "phi phat", "tien phat",
            "cach muon", "thu tuc muon", "dieu kien muon", "luat muon", "huong dan muon",
            "cach tra", "thu tuc tra", "luat tra", "huong dan tra",
            "muon bao lau", "muon duoc may", "gia han"
        ]
        # Special check: "muon sach" only if NOT accompanied by specific book topics implies info request? 
        # Actually safer to just rely on "cach/quy dinh/..." for INFO. 
        # If user says "toi muon muon sach", let it fall to SEARCH or generic AI which clarifies.
        
        return any(k in ql for k in keywords)

    def _generate_library_info_answer(self, question: str, session: ChatSession) -> str:
        """
        Tra loi cau hoi ve thu vien. Uu tien tra loi san cho cau hoi pho bien.
        """
        ql = remove_diacritics(question.lower())

        # Hardcoded responses - KHONG CAN GOI AI
        if any(k in ql for k in ["gio mo cua", "mo cua", "may gio"]):
            return f"Thư viện mở cửa: {LIBRARY_INFO['opening_hours']}. Ngoài giờ này thư viện đóng cửa."

        # Check SPECIFIC policies first (Borrow/Return) before GENERAL rules
        if any(k in ql for k in ["muon sach", "muon", "borrow", "gia han"]):
            bp = LIBRARY_INFO['borrow_policy']
            return f"Quy định mượn sách:\n- {bp['fee']}\n- {bp['duration']}\n- {bp['renew']}"

        if any(k in ql for k in ["tra sach", "tra", "return"]):
            pp = LIBRARY_INFO['penalty_policy']
            return f"Quy định trả sách:\n- {pp['late_return']}\n- {pp['account_lock']}\n- {pp['lost_book']}"

        if any(k in ql for k in ["phi phat", "phat", "penalty"]):
            pp = LIBRARY_INFO['penalty_policy']
            return f"Quy định phí phạt:\n- {pp['late_return']}\n- {pp['account_lock']}\n- {pp['lost_book']}"

        # Only if no specific policy is matched, return general rules
        if any(k in ql for k in ["noi quy", "quy dinh", "luat"]):
            rules = "\n".join([f"- {r}" for r in LIBRARY_INFO['library_rules']])
            return f"Nội quy thư viện:\n{rules}"

        if any(k in ql for k in ["muon sach", "muon", "borrow"]):
            bp = LIBRARY_INFO['borrow_policy']
            return f"Quy định mượn sách:\n- {bp['fee']}\n- {bp['duration']}\n- {bp['renew']}"

        if any(k in ql for k in ["tra sach", "tra", "return"]):
            pp = LIBRARY_INFO['penalty_policy']
            return f"Quy định trả sách:\n- {pp['late_return']}\n- {pp['account_lock']}\n- {pp['lost_book']}"

        if any(k in ql for k in ["phi phat", "phat", "penalty"]):
            pp = LIBRARY_INFO['penalty_policy']
            return f"Quy định phí phạt:\n- {pp['late_return']}\n- {pp['account_lock']}\n- {pp['lost_book']}"

        # Fallback to AI for complex library questions
        try:
            ctx = self._build_library_context()
            prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books="(Khong ap dung)", **ctx)}"""
            return self._call_gemini(prompt)
        except Exception:
            return f"Thư viện mở cửa: {LIBRARY_INFO['opening_hours']}. Nếu cần thông tin cụ thể, vui lòng hỏi lại."

    def _perform_book_search(self, question: str, session: ChatSession, filters: dict = None) -> tuple:
        """
        Perform book search and return (answer, sources).
        Returns: (answer: str, sources: List[Dict])
        """
        # --- FEATURE ADDED: ENRICH QUERY CONTEXT ---
        # "sách python cho người mới" -> "... (beginner introduction)"
        search_query = self._enrich_query_context(question)
        # -------------------------------------------
        
        q_vec = self.embedder.embed_text(search_query, is_query=True)
        
        # --- FEATURE ADDED: Smart Cache Key Generation ---
        # Generate cache key from normalized query + filter hash
        # This allows "sách python" and "tìm cuốn sách về Python" to hit same cache
        cache_key_base = remove_diacritics(search_query.lower()).strip()
        if filters:
            # Include filters in cache key for unique filter combinations
            filter_str = "_".join(f"{k}:{v}" for k, v in sorted(filters.items()))
            cache_key = f"{cache_key_base}_{filter_str}"
        else:
            cache_key = cache_key_base
        # --------------------------------------------------

        # THÊM: Smart cache skip (từ HEAD)
        # Skip cache nếu có filters (để đảm bảo kết quả chính xác)
        if q_vec and not filters:
            cached = self.vector_db.search_query_memory(q_vec, threshold=QUERY_CACHE_THRESHOLD)
            if cached:
                # Skip cache nếu cache là sách nhưng query không liên quan sách
                is_book_cache = "Danh sách sách" in cached
                if is_book_cache and not self._is_book_related_query(question):
                    logger.info("Query memory SKIP (cached books for non-book query)")
                else:
                    logger.info("Query memory HIT")
                    # Cached response: return answer but no sources
                    return f"(Cache) {cached}", []

        # Search với filters nếu được cung cấp
        raw_docs = self.search_engine.search(query=search_query, filters=filters, top_k=self.top_k * SEARCH_EXPAND_FACTOR)
        
        # --- FEATURE ADDED: RELAXED SEARCH FALLBACK ---
        # If filtered search fails (e.g. strict category mismatch), retry without filters
        # relying purely on semantic vector match.
        if not raw_docs and filters:
            logger.info("Search with filters yielded 0 results. Retrying with RELAXED search (no filters)...")
            raw_docs = self.search_engine.search(query=search_query, filters=None, top_k=self.top_k * SEARCH_EXPAND_FACTOR)
            
        if not raw_docs:
            return self._gemini_fallback(question, session), []

        # --- FEATURE ADDED: SORTING LOGIC (Newest/Oldest) ---
        q_norm = remove_diacritics(question.lower())
        if any(k in q_norm for k in ["moi nhat", "gan day", "nam nay", "latest", "newest"]):
            # Sort by publish_year desc (handling valid years)
            raw_docs.sort(key=lambda x: str(x.get('publish_year', '0')).isdigit() and int(x.get('publish_year', '0')) or 0, reverse=True)
            logger.info("Results sorted by NEWEST")
        # ----------------------------------------------------

        best_score = max(d.get("score", 0) for d in raw_docs)
        if best_score < SCORE_THRESHOLD:
            return self._gemini_fallback(question, session), []

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
            answer = f"Danh sách sách liên quan:\n\n{books_text}"
            if q_vec:
                self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_list")
            return answer, docs

        ctx = self._build_library_context()
        prompt = f"""{SYSTEM_PROMPT}\n{USER_PROMPT_TEMPLATE.format(question=question, books=books_text, **ctx)}"""

        synthesis = self._call_gemini(prompt)
        answer = f"Danh sách sách liên quan:\n\n{books_text}\n\nTổng hợp:\n{synthesis}"

        if q_vec:
            self.vector_db.add_query_memory(question, q_vec, answer, qtype="rag_synthesis")
        return answer, docs

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
            return result if result else "Xin lỗi, không có phản hồi."
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "Hệ thống đang bận hoặc gặp sự cố kết nối."

    # ==================================================
    # SUGGESTED QUESTIONS (THÊM TỪ HEAD)
    # ==================================================
    def get_suggested_questions(self) -> List[str]:
        """Danh sách gợi ý mặc định cho giao diện chat"""
        return [
            "Thư viện mở cửa lúc mấy giờ?",
            "Làm sao để gia hạn sách?",
            "Có sách nào về trí tuệ nhân tạo không?",
            "Phí phạt trả sách trễ là bao nhiêu?",
        ]