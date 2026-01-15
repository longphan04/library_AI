import chromadb
from chromadb.config import Settings as ChromaSettings
import logging
import os
import time
from config.settings import settings

logger = logging.getLogger("VectorDB")


class VectorDB:
    def __init__(self):
        os.makedirs(settings.VECTOR_DB_DIR, exist_ok=True)
        self.db_path = settings.VECTOR_DB_DIR

        logger.info(f"Initializing ChromaDB at {self.db_path}")

        try:
            self.client = chromadb.PersistentClient(path=self.db_path)

            # =========================
            # 📚 COLLECTION: BOOKS
            # =========================
            self.collection = self.client.get_or_create_collection(
                name="library_knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )

            # =========================
            # ⚡ COLLECTION: QUERY MEMORY
            # =========================
            self.query_collection = self.client.get_or_create_collection(
                name="query_memory",
                metadata={"hnsw:space": "cosine"}
            )

            logger.info(
                f"Collections ready. "
                f"Books: {self.collection.count()} | "
                f"Query cache: {self.query_collection.count()}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise e

    # ==================================================
    # 📚 BOOK COLLECTION (GIỮ NGUYÊN)
    # ==================================================
    def upsert_texts(self, ids, vectors, metadatas, documents=None):
        if not ids or not vectors:
            return False
        try:
            self.collection.upsert(
                ids=ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=documents
            )
            logger.info(f"Upserted {len(ids)} book items.")
            return True
        except Exception as e:
            logger.error(f"Error upserting books: {e}")
            return False

    def query_vectors(self, query_vector, n_results=5, where_filter=None):
        try:
            return self.collection.query(
                query_embeddings=[query_vector],
                n_results=n_results,
                where=where_filter
            )
        except Exception as e:
            logger.error(f"Error querying books: {e}")
            return None

    def get_collection_stats(self):
        return {"count": self.collection.count()}

    # ==================================================
    # ⚡ QUERY MEMORY (NEW)
    # ==================================================
    def search_query_memory(self, query_vector, threshold=0.95):
        """
        Tìm câu hỏi tương tự trong query_memory.
        """
        try:
            results = self.query_collection.query(
                query_embeddings=[query_vector],
                n_results=1
            )

            if not results["ids"][0]:
                return None

            distance = results["distances"][0][0]
            similarity = 1 - distance

            if similarity >= threshold:
                logger.info(f"Query cache HIT (sim={similarity:.3f})")
                return results["documents"][0][0]

            return None

        except Exception as e:
            logger.error(f"Error searching query memory: {e}")
            return None

    def add_query_memory(self, query: str, vector: list, answer: str, qtype: str):
        """
        Lưu câu hỏi + trả lời vào query_memory.
        """
        try:
            qid = f"q_{hash(query)}"
            self.query_collection.upsert(
                ids=[qid],
                embeddings=[vector],
                documents=[answer],
                metadatas=[{
                    "question": query,
                    "type": qtype,
                    "created_at": time.time()
                }]
            )
            logger.info(f"Saved query memory: {qid}")
        except Exception as e:
            logger.error(f"Error saving query memory: {e}")

    # ==================================================
    # GIỮ NGUYÊN CÁC HÀM CŨ
    # ==================================================
    def get_by_id(self, book_id: str):
        try:
            result = self.collection.get(
                ids=[book_id],
                include=["embeddings", "documents", "metadatas"]
            )
            if not result['ids']:
                return None
            return {
                "id": result['ids'][0],
                "embedding": result['embeddings'][0],
                "document": result['documents'][0],
                "metadata": result['metadatas'][0]
            }
        except Exception:
            return None

    def get_all_metadata(self):
        try:
            result = self.collection.get(include=["metadatas"])
            return result.get('metadatas', [])
        except Exception:
            return []
