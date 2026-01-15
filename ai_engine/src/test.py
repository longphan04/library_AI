"""
Manual Test File for SearchEngine
Có PRE-FILTER + SCORE THRESHOLD
KHÔNG sửa SearchEngine
"""

import re
from src.search_engine import SearchEngine

MIN_SCORE = 0.83


def is_valid_query(query: str) -> bool:
    """
    PRE-FILTER: chặn query vô nghĩa
    """
    if not query or not query.strip():
        return False

    q = query.strip()

    # chỉ số
    if q.isdigit():
        return False

    # chỉ ký tự đặc biệt
    if re.fullmatch(r"[^\w\s]+", q):
        return False

    # chuỗi vô nghĩa lặp ký tự
    if re.fullmatch(r"(.)\1{4,}", q):
        return False

    return True


def print_results(title, results):
    print("\n" + "=" * 80)
    print(f"🔍 TEST: {title}")
    print("=" * 80)

    if not results:
        print("❌ Không có kết quả phù hợp")
        return

    max_score = results[0]["score"]
    if max_score < MIN_SCORE:
        print("❌ Không có kết quả phù hợp (score thấp)")
        return

    for i, book in enumerate(results, start=1):
        print(
            f"{i}. {book['title']} | {book['authors']} | "
            f"{book['category']} | {book['published_year']} | "
            f"score={book['score']}"
        )


def safe_search(search_engine, query, **kwargs):
    if not is_valid_query(query):
        print_results(f"{query}", [])
        return

    results = search_engine.search(query=query, **kwargs)
    print_results(query, results)


def main():
    search_engine = SearchEngine()

    # =========================================================
    # 1️⃣ SEMANTIC SEARCH
    # =========================================================
    queries_basic = [
        "sách tài chính",
        "đầu tư chứng khoán",
        "lập trình python",
        "trí tuệ nhân tạo",
        "machine learning cho người mới",
        "kinh tế học vĩ mô",
        "blockchain là gì",
        "khoa học dữ liệu",
        "tâm lý học hành vi",
        "quản trị kinh doanh"
    ]

    for q in queries_basic:
        safe_search(search_engine, q, top_k=5)

    # =========================================================
    # 2️⃣ FILTER HỢP LỆ
    # =========================================================
    filter_tests = [
        ("AI + 2023", "artificial intelligence", {"category": "AI", "published_year": "2023"}),
        ("ARCHITECTURE", "software architecture", {"category": "ARCHITECTURE"}),
        ("Agriculture", "nông nghiệp", {"category": "Agriculture"}),
        ("Year 2024", "data science", {"published_year": "2024"}),
        ("Year N/A", "history", {"published_year": "N/A"}),
    ]

    for title, query, filters in filter_tests:
        print(f"\n🔎 FILTER TEST: {title}")
        safe_search(search_engine, query, filters=filters, top_k=5)

    # =========================================================
    # 3️⃣ NATURAL LANGUAGE
    # =========================================================
    long_questions = [
        "Tôi muốn tìm sách về đầu tư dài hạn cho người mới bắt đầu",
        "Có những cuốn sách nào nói về trí tuệ nhân tạo và machine learning?",
        "Sách nào giúp hiểu rõ về thị trường tài chính tiền tệ?",
        "Tôi muốn học python để làm data science",
        "Những cuốn sách kinh điển về kinh tế học là gì?"
    ]

    for q in long_questions:
        safe_search(search_engine, q, top_k=5)

    # =========================================================
    # 4️⃣ RECOMMENDATION
    # =========================================================
    print("\n" + "=" * 80)
    print("🤝 TEST: Recommendation")
    print("=" * 80)

    seed = search_engine.search("python", top_k=1)
    if seed and seed[0]["score"] >= MIN_SCORE:
        book_id = seed[0]["id"]
        recs = search_engine.recommend(book_id, top_k=5)
        for i, r in enumerate(recs, 1):
            print(f"{i}. {r['title']} | score={r['score']}")
    else:
        print("❌ Không tìm được sách gốc phù hợp")

    # =========================================================
    # 5️⃣ EDGE CASES (PHẢI RA ❌)
    # =========================================================
    edge_cases = [
        "",
        "   ",
        "asdasdasdasd",
        "?????",
        "123456789"
    ]

    for q in edge_cases:
        safe_search(search_engine, q, top_k=5)


if __name__ == "__main__":
    main()
