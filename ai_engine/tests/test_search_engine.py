import sys
import os
import pytest
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.search_engine import SearchEngine
from src.embedder import Embedder
from src.vector_db import VectorDB
from config.settings import settings


class TestSearchEngine:
    """Test suite for SearchEngine"""
    
    @pytest.fixture(scope="class")
    def search_engine(self):
        """Create SearchEngine instance for tests"""
        return SearchEngine()
    
    def test_init(self, search_engine):
        """Test SearchEngine initialization"""
        assert search_engine is not None
        assert search_engine.embedder is not None
        assert search_engine.vector_db is not None
        assert search_engine._filters_cache is None
        print("[PASS] SearchEngine initialized successfully")
    
    def test_search_basic(self, search_engine):
        """Test basic search without filters"""
        results = search_engine.search("Python programming", top_k=5)
        
        assert isinstance(results, list)
        assert len(results) <= 5
        
        if results:
            # Check result structure
            book = results[0]
            assert "id" in book
            assert "title" in book
            assert "authors" in book
            assert "score" in book
            assert "snippet" in book
            
            # Score should be between 0 and 1
            assert 0 <= book["score"] <= 1
            
            print(f"[PASS] Search returned {len(results)} results")
            print(f"  Top result: {book['title']} (score: {book['score']})")
    
    def test_search_with_category_filter(self, search_engine):
        """Test search with category filter"""
        # Get available categories first
        filters_data = search_engine.get_filters()
        
        if filters_data["categories"]:
            category = filters_data["categories"][0]
            
            results = search_engine.search(
                query="programming",
                filters={"category": category},
                top_k=3
            )
            
            assert isinstance(results, list)
            
            # All results should match the category
            for book in results:
                assert book["category"] == category
            
            print(f"[PASS] Category filter works: {len(results)} books in '{category}'")
    
    def test_search_with_year_filter(self, search_engine):
        """Test search with year filter"""
        filters_data = search_engine.get_filters()
        
        if filters_data["years"]:
            year = filters_data["years"][0]
            
            results = search_engine.search(
                query="artificial intelligence",
                filters={"published_year": year},
                top_k=3
            )
            
            assert isinstance(results, list)
            
            # All results should match the year
            for book in results:
                assert book["published_year"] == year
            
            print(f"[PASS] Year filter works: {len(results)} books from {year}")
    
    def test_search_with_multiple_filters(self, search_engine):
        """Test search with multiple filters"""
        results = search_engine.search(
            query="science",
            filters={
                "title": "Python"
            },
            top_k=5
        )
        
        assert isinstance(results, list)
        print(f"[PASS] Multiple filters: {len(results)} results")
    
    def test_search_empty_query(self, search_engine):
        """Test search with empty query"""
        results = search_engine.search("", top_k=5)
        assert results == []
        print("[PASS] Empty query handled correctly")
    
    def test_recommend(self, search_engine):
        """Test recommendation system"""
        # First get a book ID from search
        search_results = search_engine.search("Python", top_k=1)
        
        if search_results:
            book_id = search_results[0]["id"]
            
            recommendations = search_engine.recommend(book_id, top_k=3)
            
            assert isinstance(recommendations, list)
            assert len(recommendations) <= 3
            
            # Original book should not be in recommendations
            for rec in recommendations:
                assert rec["id"] != book_id
                assert "score" in rec
                assert 0 <= rec["score"] <= 1
            
            print(f"[PASS] Recommendations work: {len(recommendations)} similar books")
    
    def test_recommend_invalid_id(self, search_engine):
        """Test recommendation with invalid book ID"""
        recommendations = search_engine.recommend("INVALID_ID_12345", top_k=5)
        assert recommendations == []
        print("[PASS] Invalid book ID handled correctly")
    
    def test_get_book(self, search_engine):
        """Test getting book by ID"""
        # Get a valid book ID
        search_results = search_engine.search("machine learning", top_k=1)
        
        if search_results:
            book_id = search_results[0]["id"]
            
            book = search_engine.get_book(book_id)
            
            assert book is not None
            assert book["id"] == book_id
            assert "title" in book
            assert "authors" in book
            assert "content" in book
            assert len(book["content"]) > 0
            
            print(f"[PASS] Get book works: {book['title']}")
    
    def test_get_book_not_found(self, search_engine):
        """Test getting non-existent book"""
        book = search_engine.get_book("NONEXISTENT_ID")
        assert book is None
        print("[PASS] Non-existent book returns None")
    
    def test_get_filters(self, search_engine):
        """Test getting available filters"""
        filters = search_engine.get_filters()
        
        assert isinstance(filters, dict)
        assert "categories" in filters
        assert "years" in filters
        assert "authors" in filters
        
        assert isinstance(filters["categories"], list)
        assert isinstance(filters["years"], list)
        assert isinstance(filters["authors"], list)
        
        print(f"[PASS] Filters retrieved:")
        print(f"  - {len(filters['categories'])} categories")
        print(f"  - {len(filters['years'])} years")
        print(f"  - {len(filters['authors'])} authors")
    
    def test_filters_cache(self, search_engine):
        """Test that filters are cached"""
        # First call
        filters1 = search_engine.get_filters()
        
        # Second call (should use cache)
        filters2 = search_engine.get_filters()
        
        assert filters1 == filters2
        
        # Invalidate cache
        search_engine.invalidate_cache()
        assert search_engine._filters_cache is None
        
        print("[PASS] Filters caching works correctly")
    
    def test_build_where_clause(self, search_engine):
        """Test where clause building"""
        # Single filter
        where = search_engine._build_where_clause({"category": "Programming"})
        assert where == {"category": {"$eq": "Programming"}}
        
        # Multiple filters
        where = search_engine._build_where_clause({
            "category": "Programming",
            "published_year": "2023"
        })
        assert "$and" in where
        assert len(where["$and"]) == 2
        
        # No filters
        where = search_engine._build_where_clause({})
        assert where is None
        
        print("[PASS] Where clause building works")


if __name__ == "__main__":
    print("========================================")
    print("Running Search Engine Tests")
    print("========================================\n")
    
    # Generate log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(settings.LOG_DIR, f"test_search_engine_{timestamp}.txt")
    
    # Create log file header
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("SEARCH ENGINE TEST RESULTS\n")
        f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
    
    # Run pytest with output redirected to log file
    with open(log_file, 'a', encoding='utf-8') as f:
        import subprocess
        import sys
        
        # Run pytest and capture output
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', __file__, '-v', '-s', '--tb=short'],
            capture_output=True,
            text=True
        )
        
        # Write output to log
        f.write(proc.stdout)
        if proc.stderr:
            f.write("\nSTDERR:\n")
            f.write(proc.stderr)
        
        # Write summary
        f.write("\n" + "="*60 + "\n")
        if proc.returncode == 0:
            f.write("STATUS: ALL TESTS PASSED\n")
        else:
            f.write(f"STATUS: TESTS FAILED (exit code: {proc.returncode})\n")
        f.write("="*60 + "\n")
    
    # Also run pytest normally for terminal output
    result = pytest.main([__file__, "-v", "-s", "--tb=short"])
    
    print(f"\nTest results saved to: {log_file}")
