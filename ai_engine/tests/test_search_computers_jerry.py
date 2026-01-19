import sys
import os
import pytest
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.search_engine import SearchEngine


class TestSearchComputersJerry:
    """Test suite for searching 'computers' with author filter 'Jerry'"""

    @pytest.fixture(scope="class")
    def search_engine(self):
        """Create SearchEngine instance for tests"""
        return SearchEngine()

    def test_search_computers_with_jerry_filter(self, search_engine):
        """Test search with query 'computers' and filter authors='Jerry'"""
        print("\n" + "="*60)
        print("Testing Search: query='computers', filter={'authors': 'Jerry'}")
        print("="*60)

        # Execute search
        results = search_engine.search(
            query="computers",
            filters={"authors": "Jerry"},
            top_k=10
        )

        # Assertions
        assert isinstance(results, list), "Results should be a list"
        print(f"\n✓ Found {len(results)} results")

        # Display results
        if results:
            print("\n📚 Search Results:")
            print("-" * 60)
            for i, book in enumerate(results, 1):
                print(f"\n{i}. {book['title']}")
                print(f"   Authors: {book['authors']}")
                print(f"   Category: {book.get('category', 'N/A')}")
                print(f"   Year: {book.get('published_year', 'N/A')}")
                print(f"   Score: {book['score']:.4f}")
                print(f"   ID: {book['id']}")
                print(f"   Snippet: {book['snippet'][:100]}...")

                # Verify structure
                assert "id" in book, "Book should have an ID"
                assert "title" in book, "Book should have a title"
                assert "authors" in book, "Book should have authors"
                assert "score" in book, "Book should have a score"
                assert "snippet" in book, "Book should have a snippet"

                # Verify score range
                assert 0 <= book["score"] <= 1, f"Score should be between 0 and 1, got {book['score']}"

                # Verify Jerry is in authors (case-insensitive check)
                assert "Jerry" in book["authors"] or "jerry" in book["authors"].lower(), \
                    f"Author filter not working: Expected 'Jerry' in authors, got '{book['authors']}'"

            print("\n" + "="*60)
            print(f"✓ All {len(results)} results passed validation")
            print("="*60)
        else:
            print("\n⚠ No results found for this query and filter combination")
            print("  This could mean:")
            print("  - No books by author 'Jerry' match 'computers'")
            print("  - The database might be empty or not initialized")

    def test_search_computers_without_filter(self, search_engine):
        """Test search with query 'computers' WITHOUT filter for comparison"""
        print("\n" + "="*60)
        print("Testing Search: query='computers' (no filter)")
        print("="*60)

        # Execute search without filter
        results = search_engine.search(
            query="computers",
            top_k=10
        )

        assert isinstance(results, list), "Results should be a list"
        print(f"\n✓ Found {len(results)} results (without filter)")

        if results:
            print("\n📚 Sample Results (Top 3):")
            print("-" * 60)
            for i, book in enumerate(results[:3], 1):
                print(f"\n{i}. {book['title']}")
                print(f"   Authors: {book['authors']}")
                print(f"   Score: {book['score']:.4f}")

    def test_search_empty_query(self, search_engine):
        """Test that empty query returns empty results"""
        results = search_engine.search(
            query="",
            filters={"authors": "Jerry"}
        )

        assert results == [], "Empty query should return empty list"
        print("\n✓ Empty query handling works correctly")

    def test_search_with_additional_filters(self, search_engine):
        """Test search with multiple filters including Jerry"""
        print("\n" + "="*60)
        print("Testing Search with Multiple Filters")
        print("="*60)

        # Test with author + category
        results = search_engine.search(
            query="computers",
            filters={
                "authors": "Jerry",
                "category": "Computers"  # Adjust category if needed
            },
            top_k=5
        )

        print(f"\n✓ With authors='Jerry' + category='Computers': {len(results)} results")

        # Test with author + year (example)
        results2 = search_engine.search(
            query="computers",
            filters={
                "authors": "Jerry",
                "published_year": "2023"  # Adjust year if needed
            },
            top_k=5
        )

        print(f"✓ With authors='Jerry' + year='2023': {len(results2)} results")


def main():
    """Run tests manually without pytest"""
    print("\n" + "="*70)
    print(" Manual Test Execution: Search Computers with Author Jerry")
    print("="*70)

    search_engine = SearchEngine()

    # Test 1: Main search
    print("\n[Test 1] Search: query='computers', filter={'authors': 'Jerry'}")
    print("-" * 70)
    results = search_engine.search(
        query="computers",
        filters={"authors": "Jerry"},
        top_k=10
    )

    print(f"\nResults: {len(results)} books found")
    if results:
        for i, book in enumerate(results, 1):
            print(f"\n{i}. {book['title']}")
            print(f"   Authors: {book['authors']}")
            print(f"   Category: {book.get('category', 'N/A')}")
            print(f"   Year: {book.get('published_year', 'N/A')}")
            print(f"   Score: {book['score']:.4f}")
    else:
        print("\n⚠ No results found. Trying without filter...")

        # Fallback: Search without filter
        results_no_filter = search_engine.search(query="computers", top_k=5)
        print(f"\nWithout filter: {len(results_no_filter)} books found")
        if results_no_filter:
            print("\nTop results:")
            for i, book in enumerate(results_no_filter[:3], 1):
                print(f"{i}. {book['title']} by {book['authors']}")

    print("\n" + "="*70)
    print(" Test Completed")
    print("="*70)


if __name__ == "__main__":
    # Run tests manually
    main()

