import pytest

# =====================================================
# MOCKS
# =====================================================

class FakeLLM:
    """
    Mock cho Gemini / LLM
    Trả lần lượt các response đã định nghĩa trước
    """
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def generate_content(self, *args, **kwargs):
        class Resp:
            def __init__(self, text):
                self.text = text

        text = self.responses[self.calls]
        self.calls += 1
        return Resp(text)


class FakeSearchEngine:
    """
    Mock SearchEngine
    """
    def __init__(self, results):
        self.results = results
        self.last_top_k = None
        self.called = False

    def search(self, query, top_k=5, filters=None):
        self.called = True
        self.last_top_k = top_k
        return self.results[:top_k]


# =====================================================
# FIXTURES
# =====================================================

@pytest.fixture
def fake_books():
    return [
        {
            "id": "1",
            "title": "Book A",
            "authors": "Author A",
            "published_year": "2020",
            "category": "AI",
            "score": 0.95
        },
        {
            "id": "2",
            "title": "Book B",
            "authors": "Author B",
            "published_year": "2021",
            "category": "AI",
            "score": 0.90
        },
        {
            "id": "3",
            "title": "Book C",
            "authors": "Author C",
            "published_year": "2022",
            "category": "AI",
            "score": 0.85
        },
    ]


# =====================================================
# IMPORT SAU KHI MOCK
# =====================================================

from src.rag.rag_engine import RAGEngine
from src.rag.prompt import USER_PROMPT_TEMPLATE, LIBRARY_INFO


# =====================================================
# TEST PROMPT FORMAT (BẮT KeyError)
# =====================================================

def test_prompt_format_no_keyerror():
    ctx = {
        "question": "test",
        "books": "none",
        "opening_hours": LIBRARY_INFO["opening_hours"],
        "library_rules": "",
        "borrow_policy": "",
        "penalty_policy": ""
    }

    USER_PROMPT_TEMPLATE.format(**ctx)


# =====================================================
# TEST LIBRARY INFO
# =====================================================

def test_library_opening_hours_defined():
    assert "opening_hours" in LIBRARY_INFO
    assert "08:00" in LIBRARY_INFO["opening_hours"]
    assert "17:00" in LIBRARY_INFO["opening_hours"]


# =====================================================
# TEST GARBAGE QUERY
# =====================================================

def test_garbage_queries_blocked():
    rag = RAGEngine()

    bad_queries = [
        "",
        "   ",
        "123456",
        "?????",
        "aaaaaa",
        "1111",
        "!!!",
    ]

    for q in bad_queries:
        assert rag.is_garbage_query(q) is True


def test_valid_query_not_blocked():
    rag = RAGEngine()
    assert rag.is_garbage_query("Cho tôi sách AI") is False


# =====================================================
# TEST INTENT CLASSIFICATION
# =====================================================

def test_intent_book_with_number(monkeypatch):
    rag = RAGEngine()
    rag.model = FakeLLM([
        '{"is_book_query": true, "number_of_books": 3}'
    ])

    intent = rag.classify_question("Cho tôi 3 cuốn sách AI")
    assert intent["is_book_query"] is True
    assert intent["number_of_books"] == 3


def test_intent_non_book(monkeypatch):
    rag = RAGEngine()
    rag.model = FakeLLM([
        '{"is_book_query": false, "number_of_books": null}'
    ])

    intent = rag.classify_question("Thư viện mở cửa lúc mấy giờ")
    assert intent["is_book_query"] is False


# =====================================================
# TEST SCORE THRESHOLD
# =====================================================

def test_score_threshold_blocks_low_score():
    rag = RAGEngine()

    low_score_docs = [
        {"score": 0.6},
        {"score": 0.7},
    ]

    assert rag.apply_score_threshold(low_score_docs) == []


def test_score_threshold_allows_high_score():
    rag = RAGEngine()

    high_score_docs = [
        {"score": 0.85},
        {"score": 0.9},
    ]

    assert rag.apply_score_threshold(high_score_docs) == high_score_docs


# =====================================================
# TEST SỐ LƯỢNG SÁCH
# =====================================================

def test_exact_number_of_books(fake_books):
    rag = RAGEngine()
    rag.model = FakeLLM([
        '{"is_book_query": true, "number_of_books": 2}',
        "OK"
    ])
    rag.search_engine = FakeSearchEngine(fake_books)

    answer = rag.generate_answer("Cho tôi 2 cuốn sách AI")

    assert "1." in answer
    assert "2." in answer
    assert "3." not in answer
    assert rag.search_engine.last_top_k == 2


def test_default_top_k_when_no_number(fake_books):
    rag = RAGEngine(top_k=5)
    rag.model = FakeLLM([
        '{"is_book_query": true, "number_of_books": null}',
        "OK"
    ])
    rag.search_engine = FakeSearchEngine(fake_books)

    rag.generate_answer("Cho tôi các sách AI")
    assert rag.search_engine.last_top_k == 5


# =====================================================
# TEST KHÔNG SEARCH KHI HỎI HÀNH CHÍNH
# =====================================================

def test_non_book_question_does_not_call_search(fake_books):
    rag = RAGEngine()
    rag.model = FakeLLM([
        '{"is_book_query": false, "number_of_books": null}',
        "Thư viện mở cửa từ Thứ 2 – Thứ 6"
    ])
    rag.search_engine = FakeSearchEngine(fake_books)

    answer = rag.generate_answer("Thư viện mấy giờ mở cửa")

    assert "08:00" in answer
    assert rag.search_engine.called is False


# =====================================================
# TEST QUERY RÁC KHÔNG GỌI LLM / SEARCH
# =====================================================

def test_garbage_query_short_circuit(fake_books):
    rag = RAGEngine()
    rag.search_engine = FakeSearchEngine(fake_books)

    answer = rag.generate_answer("123456")

    assert "❌" in answer
    assert rag.search_engine.called is False
