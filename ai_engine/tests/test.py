def test_search_computers_author_john_debug(self, search_engine):
    """DEBUG test: search query='computers' filter authors='John'"""

    query = "computers"
    filters = {"authors": "John"}

    print("\n" + "=" * 80)
    print("[DEBUG] TEST: search(query='computers', filters={'authors': 'John'})")

    # 1. In filters hiện có
    filters_data = search_engine.get_filters()
    print(f"[DEBUG] Available authors count: {len(filters_data['authors'])}")
    print(f"[DEBUG] First 10 authors: {filters_data['authors'][:10]}")

    # 2. Build where clause
    where = search_engine._build_where_clause(filters)
    print(f"[DEBUG] Built where clause: {where}")

    # 3. Run search
    results = search_engine.search(
        query=query,
        filters=filters,
        top_k=20   # tăng lên để xem có bị limit không
    )

    print(f"[DEBUG] Search returned {len(results)} results")

    assert isinstance(results, list)

    # 4. Dump full results
    for i, book in enumerate(results):
        print("-" * 60)
        print(f"[DEBUG] Result #{i+1}")
        print(f"  ID: {book['id']}")
        print(f"  Title: {book['title']}")
        print(f"  Authors: {book['authors']}")
        print(f"  Category: {book['category']}")
        print(f"  Year: {book['published_year']}")
        print(f"  Score: {book['score']}")
        print(f"  Snippet: {book['snippet'][:100]}")

        # Check author condition
        assert "John" in book["authors"]

    print("\n[PASS] DEBUG search computers + author=John finished")
