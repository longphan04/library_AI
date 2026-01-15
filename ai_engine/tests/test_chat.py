import sys
import os
import pytest

# Add project root (ai_engine) to PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.rag_engine import RAGEngine



class TestChatRAG:
    """Integration tests for RAG Chat"""

    @pytest.fixture(scope="class")
    def rag(self):
        """Create RAGEngine instance"""
        return RAGEngine(top_k=3)

    def test_rag_init(self, rag):
        """Test RAGEngine initialization"""
        assert rag is not None
        assert rag.search_engine is not None
        assert rag.top_k == 3
        print("[PASS] RAGEngine initialized")

    def test_rag_retrieve(self, rag):
        """Test document retrieval"""
        docs = rag.retrieve("Python programming")

        assert isinstance(docs, list)
        assert len(docs) <= 3

        if docs:
            doc = docs[0]
            assert "title" in doc
            assert "authors" in doc
            assert "snippet" in doc
            print(f"[PASS] Retrieved {len(docs)} documents")

    def test_build_context(self, rag):
        """Test context building"""
        docs = rag.retrieve("Machine learning")

        context = rag.build_context(docs)

        assert isinstance(context, str)
        assert "TÀI LIỆU" in context or context == ""
        print("[PASS] Context built")

    def test_generate_answer(self, rag):
        """Test full RAG answer generation"""
        answer = rag.generate_answer("Cho tôi sách về trí tuệ nhân tạo")

        assert isinstance(answer, str)
        assert len(answer) > 0
        print("[PASS] RAG answer generated")
        print("Answer preview:", answer[:200])

    def test_generate_answer_empty(self, rag):
        """Test empty question"""
        answer = rag.generate_answer("")

        assert "không tìm thấy" in answer.lower()
        print("[PASS] Empty question handled correctly")
