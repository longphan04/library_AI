import logging
import os

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings

logger = logging.getLogger("VectorDB")

class VectorDB:
    def __init__(self):
        # Đảm bảo thư mục tồn tại
        os.makedirs(settings.VECTOR_DB_DIR, exist_ok=True)
        self.db_path = settings.VECTOR_DB_DIR
        self.collection_name = "library_knowledge_base"
        
        logger.info(f"Initializing ChromaDB at {self.db_path}")
        try:
            self.client = chromadb.PersistentClient(path=self.db_path)
            
            # Khởi tạo hoặc lấy collection
            # Metadata "hnsw:space": "cosine" bắt buộc theo guide
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name, 
                metadata={"hnsw:space": "cosine"} 
            )
            logger.info(f"Collection {self.collection_name} ready. Count: {self.collection.count()}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise e

    def upsert_texts(self, ids, vectors, metadatas, documents=None):
        """
        Lưu hoặc cập nhật vectors vào DB.
        """
        if not ids or not vectors:
            return False
            
        try:
            self.collection.upsert(
                ids=ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=documents 
            )
            logger.info(f"Upserted {len(ids)} items.")
            return True
        except Exception as e:
            logger.error(f"Error upserting to ChromaDB: {e}")
            return False

    def query_vectors(self, query_vector, n_results=5, where_filter=None):
        """
        Truy vấn vector gần nhất.
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=n_results,
                where=where_filter
            )
            return results
        except Exception as e:
            logger.error(f"Error querying ChromaDB: {e}")
            return None

    def get_collection_stats(self):
        return {"count": self.collection.count()}
    
    def get_by_id(self, book_id: str):
        """
        Lấy document + embedding theo ID.
        
        Returns:
            dict: {"id", "embedding", "document", "metadata"} hoặc None
        """
        try:
            result = self.collection.get(
                ids=[book_id],
                include=["embeddings", "documents", "metadatas"]
            )
            
            if not result['ids']:
                logger.warning(f"Book ID {book_id} not found")
                return None
                
            return {
                "id": result['ids'][0],
                "embedding": result['embeddings'][0],
                "document": result['documents'][0],
                "metadata": result['metadatas'][0]
            }
        except Exception as e:
            logger.error(f"Error getting book {book_id}: {e}")
            return None
    
    def get_all_metadata(self):
        """
        Lấy tất cả metadata để extract unique filters.
        
        Returns:
            list: Danh sách metadata dicts
        """
        try:
            result = self.collection.get(
                include=["metadatas"]
            )
            return result.get('metadatas', [])
        except Exception as e:
            logger.error(f"Error getting all metadata: {e}")
            return []
