#!/usr/bin/env python3
"""
Unit tests for SearchEngine module with focus on filtering functionality.

Tests cover:
- Basic search without filters
- Search with single filter (category, year, author, title)
- Search with multiple filters
- Filter validation
- Edge cases and error handling
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.search_engine import SearchEngine


class TestSearchEngineFilters(unittest.TestCase):
    """Test cases for SearchEngine filtering functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock dependencies
        self.mock_embedder = Mock()
        self.mock_vector_db = Mock()

        # Create SearchEngine instance with mocked dependencies
        with patch('src.search_engine.Embedder', return_value=self.mock_embedder), \
             patch('src.search_engine.VectorDB', return_value=self.mock_vector_db):
            self.search_engine = SearchEngine()

    def tearDown(self):
        """Clean up after each test method."""
        self.search_engine = None

    def _mock_query_results(self, count: int = 3) -> Dict:
        """Helper to create mock query results."""
        return {
            'ids': [[f'book_{i}' for i in range(count)]],
            'distances': [[0.1 * i for i in range(count)]],
            'metadatas': [[
                {
                    'title': f'Python Programming Book {i}',
                    'authors': f'Author {i}, Co-Author {i}',
                    'category': 'Programming' if i % 2 == 0 else 'Science',
                    'published_year': str(2020 + i)
                } for i in range(count)
            ]],
            'documents': [[f'This is the content of book {i}. ' * 20 for i in range(count)]]
        }

    def test_search_without_filters(self):
        """Test basic search without any filters."""
        print("\n=== Test: Search without filters ===")

        # Arrange
        query = "Python programming"
        mock_vector = [0.1] * 384
        self.mock_embedder.embed_text.return_value = mock_vector
        self.mock_vector_db.query_vectors.return_value = self._mock_query_results()

        # Act
        results = self.search_engine.search(query=query, top_k=10)

        # Assert
        self.assertEqual(len(results), 3)
        print(f"✓ Found {len(results)} results")
        for i, result in enumerate(results):
            print(f"  {i+1}. {result['title']} - Score: {result['score']}")

        self.mock_embedder.embed_text.assert_called_once_with(query, is_query=True)
        self.mock_vector_db.query_vectors.assert_called_once_with(
            query_vector=mock_vector,
            n_results=10,
            where_filter=None
        )
        print("✓ All assertions passed")

    def test_search_with_category_filter(self):
        """Test search with category filter."""
        print("\n=== Test: Search with category filter ===")

        # Arrange
        query = "programming books"
        filters = {"category": "Programming"}
        mock_vector = [0.1] * 384
        self.mock_embedder.embed_text.return_value = mock_vector
        self.mock_vector_db.query_vectors.return_value = self._mock_query_results()

        # Act
        results = self.search_engine.search(query=query, filters=filters, top_k=5)

        # Assert
        expected_where = {"category": {"$eq": "Programming"}}
        print(f"✓ Filter applied: {filters}")
        print(f"✓ Where clause: {expected_where}")
        print(f"✓ Found {len(results)} results")

        self.mock_vector_db.query_vectors.assert_called_once()
        call_args = self.mock_vector_db.query_vectors.call_args
        self.assertEqual(call_args[1]['where_filter'], expected_where)
        self.assertEqual(call_args[1]['n_results'], 5)
        print("✓ All assertions passed")

    def test_search_with_year_filter(self):
        """Test search with published year filter."""
        print("\n=== Test: Search with year filter ===")

        # Arrange
        query = "latest books"
        filters = {"published_year": "2023"}
        mock_vector = [0.1] * 384
        self.mock_embedder.embed_text.return_value = mock_vector
        self.mock_vector_db.query_vectors.return_value = self._mock_query_results()

        # Act
        results = self.search_engine.search(query=query, filters=filters)

        # Assert
        expected_where = {"published_year": {"$eq": "2023"}}
        print(f"✓ Filter applied: {filters}")
        print(f"✓ Where clause: {expected_where}")
        call_args = self.mock_vector_db.query_vectors.call_args
        self.assertEqual(call_args[1]['where_filter'], expected_where)
        print("✓ All assertions passed")

    def test_search_with_author_filter(self):
        """Test search with author filter."""
        print("\n=== Test: Search with author filter ===")

        # Arrange
        query = "books"
        filters = {"authors": "Mark Lutz"}
        mock_vector = [0.1] * 384
        self.mock_embedder.embed_text.return_value = mock_vector
        self.mock_vector_db.query_vectors.return_value = self._mock_query_results()

        # Act
        results = self.search_engine.search(query=query, filters=filters)

        # Assert
        expected_where = {"authors": {"$contains": "Mark Lutz"}}
        print(f"✓ Filter applied: {filters}")
        print(f"✓ Where clause: {expected_where}")
        call_args = self.mock_vector_db.query_vectors.call_args
        self.assertEqual(call_args[1]['where_filter'], expected_where)
        print("✓ All assertions passed")

    def test_search_with_title_filter(self):
        """Test search with title filter."""
        print("\n=== Test: Search with title filter ===")

        # Arrange
        query = "programming"
        filters = {"title": "Python"}
        mock_vector = [0.1] * 384
        self.mock_embedder.embed_text.return_value = mock_vector
        self.mock_vector_db.query_vectors.return_value = self._mock_query_results()

        # Act
        results = self.search_engine.search(query=query, filters=filters)

        # Assert
        expected_where = {"title": {"$contains": "Python"}}
        print(f"✓ Filter applied: {filters}")
        print(f"✓ Where clause: {expected_where}")
        call_args = self.mock_vector_db.query_vectors.call_args
        self.assertEqual(call_args[1]['where_filter'], expected_where)
        print("✓ All assertions passed")

    def test_search_with_multiple_filters(self):
        """Test search with multiple filters combined."""
        print("\n=== Test: Search with multiple filters ===")

        # Arrange
        query = "advanced programming"
        filters = {
            "category": "Programming",
            "published_year": "2023",
            "authors": "Mark"
        }
        mock_vector = [0.1] * 384
        self.mock_embedder.embed_text.return_value = mock_vector
        self.mock_vector_db.query_vectors.return_value = self._mock_query_results()

        # Act
        results = self.search_engine.search(query=query, filters=filters)

        # Assert
        expected_where = {
            "$and": [
                {"category": {"$eq": "Programming"}},
                {"published_year": {"$eq": "2023"}},
                {"authors": {"$contains": "Mark"}}
            ]
        }
        print(f"✓ Filters applied: {filters}")
        print(f"✓ Where clause: {expected_where}")
        call_args = self.mock_vector_db.query_vectors.call_args
        self.assertEqual(call_args[1]['where_filter'], expected_where)
        print("✓ All assertions passed")

    def test_search_empty_query(self):
        """Test search with empty query returns empty list."""
        print("\n=== Test: Search with empty query ===")

        # Arrange
        query = ""

        # Act
        results = self.search_engine.search(query=query)

        # Assert
        self.assertEqual(results, [])
        print("✓ Empty query returns empty results")
        self.mock_embedder.embed_text.assert_not_called()
        print("✓ Embedder not called")

    def test_search_whitespace_query(self):
        """Test search with whitespace-only query."""
        print("\n=== Test: Search with whitespace query ===")

        # Arrange
        query = "   "

        # Act
        results = self.search_engine.search(query=query)

        # Assert
        self.assertEqual(results, [])
        print("✓ Whitespace query returns empty results")

    def test_search_embedding_failure(self):
        """Test search handles embedding failure gracefully."""
        print("\n=== Test: Search with embedding failure ===")

        # Arrange
        query = "test query"
        self.mock_embedder.embed_text.return_value = None

        # Act
        results = self.search_engine.search(query=query)

        # Assert
        self.assertEqual(results, [])
        print("✓ Embedding failure handled gracefully")
        self.mock_vector_db.query_vectors.assert_not_called()
        print("✓ Vector DB not called")

    def test_get_filters(self):
        """Test get_filters returns available filter options."""
        print("\n=== Test: Get filters ===")

        # Arrange
        mock_metadata = [
            {
                'category': 'Programming',
                'published_year': '2023',
                'authors': 'Author A, Author B'
            },
            {
                'category': 'Science',
                'published_year': '2022',
                'authors': 'Author C'
            },
            {
                'category': 'Programming',
                'published_year': '2023',
                'authors': 'Author A'
            }
        ]
        self.mock_vector_db.get_all_metadata.return_value = mock_metadata

        # Act
        filters = self.search_engine.get_filters()

        # Assert
        self.assertIn('categories', filters)
        self.assertIn('years', filters)
        self.assertIn('authors', filters)
        print(f"✓ Categories: {filters['categories']}")
        print(f"✓ Years: {filters['years']}")
        print(f"✓ Authors: {filters['authors']}")
        self.assertEqual(sorted(filters['categories']), ['Programming', 'Science'])
        self.assertEqual(filters['years'], ['2023', '2022'])
        self.assertIn('Author A', filters['authors'])
        self.assertIn('Author B', filters['authors'])
        self.assertIn('Author C', filters['authors'])
        print("✓ All assertions passed")

    def test_get_filters_caching(self):
        """Test that get_filters uses cache on subsequent calls."""
        print("\n=== Test: Filter caching ===")

        # Arrange
        mock_metadata = [{'category': 'Test', 'published_year': '2023', 'authors': 'Test Author'}]
        self.mock_vector_db.get_all_metadata.return_value = mock_metadata

        # Act
        filters1 = self.search_engine.get_filters()
        filters2 = self.search_engine.get_filters()

        # Assert
        self.assertEqual(filters1, filters2)
        print("✓ Cached filters match")
        self.mock_vector_db.get_all_metadata.assert_called_once()
        print("✓ Metadata loaded only once (cache working)")

    def test_invalidate_cache(self):
        """Test cache invalidation."""
        print("\n=== Test: Cache invalidation ===")

        # Arrange
        mock_metadata = [{'category': 'Test', 'published_year': '2023', 'authors': 'Test Author'}]
        self.mock_vector_db.get_all_metadata.return_value = mock_metadata
        self.search_engine.get_filters()  # Build cache
        print("✓ Cache built")

        # Act
        self.search_engine.invalidate_cache()
        print("✓ Cache invalidated")
        self.search_engine.get_filters()  # Should rebuild

        # Assert
        self.assertEqual(self.mock_vector_db.get_all_metadata.call_count, 2)
        print("✓ Metadata reloaded after invalidation")

    def test_build_where_clause_single_filter(self):
        """Test _build_where_clause with single filter."""
        print("\n=== Test: Build where clause (single filter) ===")

        # Arrange
        filters = {"category": "Programming"}

        # Act
        where_clause = self.search_engine._build_where_clause(filters)

        # Assert
        self.assertEqual(where_clause, {"category": {"$eq": "Programming"}})
        print(f"✓ Where clause: {where_clause}")

    def test_build_where_clause_multiple_filters(self):
        """Test _build_where_clause with multiple filters."""
        print("\n=== Test: Build where clause (multiple filters) ===")

        # Arrange
        filters = {
            "category": "Programming",
            "title": "Python",
            "authors": "Lutz",
            "published_year": "2023"
        }

        # Act
        where_clause = self.search_engine._build_where_clause(filters)

        # Assert
        self.assertIn("$and", where_clause)
        self.assertEqual(len(where_clause["$and"]), 4)
        print(f"✓ Where clause with {len(where_clause['$and'])} conditions")
        print(f"  {where_clause}")

    def test_format_search_results(self):
        """Test _format_search_results formats correctly."""
        print("\n=== Test: Format search results ===")

        # Arrange
        mock_results = self._mock_query_results(2)

        # Act
        formatted = self.search_engine._format_search_results(mock_results)

        # Assert
        self.assertEqual(len(formatted), 2)
        print(f"✓ Formatted {len(formatted)} results")
        self.assertIn('id', formatted[0])
        self.assertIn('title', formatted[0])
        self.assertIn('score', formatted[0])
        self.assertIn('snippet', formatted[0])
        print(f"✓ Result format: {list(formatted[0].keys())}")

    def test_format_search_results_empty(self):
        """Test _format_search_results with empty results."""
        print("\n=== Test: Format empty results ===")

        # Arrange
        mock_results = {'ids': []}

        # Act
        formatted = self.search_engine._format_search_results(mock_results)

        # Assert
        self.assertEqual(formatted, [])
        print("✓ Empty results handled correctly")


def run_tests_with_summary():
    """Run all tests and print summary."""
    print("=" * 70)
    print("SEARCH ENGINE FILTER TESTS")
    print("=" * 70)

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSearchEngineFilters)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✓ ALL TESTS PASSED!")
    else:
        print("\n✗ SOME TESTS FAILED")

    print("=" * 70)

    return result


if __name__ == '__main__':
    run_tests_with_summary()

