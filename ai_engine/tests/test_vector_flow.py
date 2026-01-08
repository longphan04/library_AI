import sys
import os
import pytest
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.embedder import Embedder
from src.vector_db import VectorDB
from config.settings import settings


class TestVectorFlow:
    """Test suite for Embedder + VectorDB integration"""
    
    @pytest.fixture(scope="class")
    def embedder(self):
        """Create Embedder instance for tests"""
        return Embedder()
    
    @pytest.fixture(scope="class")
    def vector_db(self):
        """Create VectorDB instance for tests"""
        return VectorDB()
    
    def test_embedder_init(self, embedder):
        """Test Embedder initialization"""
        assert embedder is not None
        assert embedder.model is not None
        print("[PASS] Embedder initialized")
    
    def test_vector_db_init(self, vector_db):
        """Test VectorDB initialization"""
        assert vector_db is not None
        assert vector_db.collection is not None
        stats = vector_db.get_collection_stats()
        print(f"[PASS] VectorDB initialized (count: {stats['count']})")
    
    def test_embed_passage(self, embedder):
        """Test embedding a passage"""
        text = "Python is a powerful programming language."
        vector = embedder.embed_text(text, is_query=False)
        
        assert vector is not None
        assert len(vector) == 768
        assert isinstance(vector, list)
        print(f"[PASS] Passage embedded (dim: {len(vector)})")
    
    def test_embed_query(self, embedder):
        """Test embedding a query"""
        query = "programming language"
        vector = embedder.embed_text(query, is_query=True)
        
        assert vector is not None
        assert len(vector) == 768
        print("[PASS] Query embedded")
    
    def test_embed_batch(self, embedder):
        """Test batch embedding"""
        texts = [
            "Python programming",
            "Machine learning",
            "Data science"
        ]
        vectors = embedder.embed_batch(texts, is_query=False)
        
        assert len(vectors) == 3
        assert all(len(v) == 768 for v in vectors)
        print(f"[PASS] Batch embedded ({len(vectors)} items)")
    
    def test_upsert_and_query(self, embedder, vector_db):
        """Test full flow: embed -> upsert -> query"""
        # 1. Prepare test data
        book_id = "pytest_test_book_001"
        text = "Python is excellent for data science and machine learning."
        meta = {
            "title": "Test Python Book",
            "category": "Programming",
            "authors": "Test Author",
            "published_year": "2024"
        }
        
        # 2. Embed
        vector = embedder.embed_text(text, is_query=False)
        assert vector is not None
        
        # 3. Upsert
        success = vector_db.upsert_texts(
            ids=[book_id],
            vectors=[vector],
            metadatas=[meta],
            documents=[text]
        )
        assert success is True
        print("[PASS] Upserted to DB")
        
        # 4. Query
        query_text = "Python machine learning"
        query_vec = embedder.embed_text(query_text, is_query=True)
        
        results = vector_db.query_vectors(query_vec, n_results=5)
        
        # 5. Verify results
        assert results is not None
        assert 'ids' in results
        assert len(results['ids'][0]) > 0
        
        # Check if our test book is in results
        found_ids = results['ids'][0]
        if book_id in found_ids:
            idx = found_ids.index(book_id)
            distance = results['distances'][0][idx]
            similarity = 1 - distance
            print(f"[PASS] Query found test book (similarity: {similarity:.4f})")
        else:
            print("[INFO] Test book not in top results (expected)")
    
    def test_get_by_id(self, embedder, vector_db):
        """Test getting book by ID"""
        # First upsert a test book
        book_id = "pytest_get_test_001"
        text = "Artificial Intelligence fundamentals"
        meta = {"title": "AI Book", "category": "AI"}
        
        vector = embedder.embed_text(text, is_query=False)
        vector_db.upsert_texts(
            ids=[book_id],
            vectors=[vector],
            metadatas=[meta],
            documents=[text]
        )
        
        # Now get it
        result = vector_db.get_by_id(book_id)
        
        assert result is not None
        assert result['id'] == book_id
        assert result['metadata']['title'] == "AI Book"
        assert result['document'] == text
        assert len(result['embedding']) == 768
        print(f"[PASS] Get by ID works: '{result['metadata']['title']}'")
    
    def test_get_by_invalid_id(self, vector_db):
        """Test getting non-existent book"""
        result = vector_db.get_by_id("INVALID_ID_DOES_NOT_EXIST")
        assert result is None
        print("[PASS] Invalid ID returns None")
    
    def test_get_all_metadata(self, vector_db):
        """Test getting all metadata"""
        all_meta = vector_db.get_all_metadata()
        
        assert isinstance(all_meta, list)
        assert len(all_meta) > 0
        print(f"[PASS] Retrieved {len(all_meta)} metadata records")
    
    def test_query_with_filter(self, embedder, vector_db):
        """Test query with metadata filter"""
        query_text = "programming"
        query_vec = embedder.embed_text(query_text, is_query=True)
        
        # Query with category filter
        results = vector_db.query_vectors(
            query_vec,
            n_results=3,
            where_filter={"category": {"$eq": "Programming"}}
        )
        
        assert results is not None
        if results['ids'][0]:
            # Verify all results match filter
            for meta in results['metadatas'][0]:
                assert meta.get('category') == 'Programming'
            print(f"[PASS] Filtered query returned {len(results['ids'][0])} results")


if __name__ == "__main__":
    print("="*60)
    print("Running Vector Flow Tests")
    print("="*60)
    
    # Generate log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(settings.LOG_DIR, f"test_vector_flow_{timestamp}.txt")
    
    # Create log file header
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("VECTOR FLOW TEST RESULTS\n")
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
