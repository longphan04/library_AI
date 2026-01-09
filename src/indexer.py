import os
import glob
import logging
import re
from src.embedder import Embedder
from src.vector_db import VectorDB
from config.settings import settings

logger = logging.getLogger("Indexer")

class Indexer:
    def __init__(self):
        self.embedder = Embedder()
        self.vector_db = VectorDB()

    def parse_rich_text(self, content):
        """
        Extract metadata from the structured rich text format.
        Format from data_processor.py:
        Tiêu đề: ...
        Mã định danh: ...
        Tác giả: ...
        Thể loại: ...
        Năm xuất bản: ...
        Tóm tắt nội dung: ...
        """
        meta = {}
        lines = content.split('\n')
        
        # Default values
        id_val = "unknown"
        title = "Unknown"
        authors = "Unknown"
        category = "General"
        year = "N/A"
        
        for line in lines:
            if line.startswith("Tiêu đề: "):
                title = line.replace("Tiêu đề: ", "").strip()
            elif line.startswith("Mã định danh: "):
                # Format: 978-3-16-148410-0 (ISBN_13)
                raw_id = line.replace("Mã định danh: ", "").strip()
                # Extract just the ID part before the parenthesis if needed, 
                # but currently data_processor puts "ID (TYPE)".
                # We usually want the ID as key.
                parts = raw_id.split(' (')
                if parts:
                    id_val = parts[0].strip()
            elif line.startswith("Tác giả: "):
                authors = line.replace("Tác giả: ", "").strip()
            elif line.startswith("Thể loại: "):
                category = line.replace("Thể loại: ", "").strip()
            elif line.startswith("Năm xuất bản: "):
                year = line.replace("Năm xuất bản: ", "").strip()
                
        meta = {
            "title": title,
            "authors": authors,
            "category": category,
            "published_year": year # Consistent with schema
        }
        return id_val, meta

    def run_indexing(self):
        logger.info(">>> STARTING INDEXING (RICH TEXT ONLY MODE)...")
        
        rich_text_files = glob.glob(os.path.join(settings.DATA_RICH_TEXT_DIR, "*.txt"))
        if not rich_text_files:
            logger.warning("No rich text files found in data/rich_text/. Please run 'process' first.")
            return

        logger.info(f"Found {len(rich_text_files)} rich text files.")
        
        batch_ids = []
        batch_texts = []
        batch_metadatas = []
        count = 0
        error_count = 0

        for txt_path in rich_text_files:
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if not content.strip():
                    error_count += 1
                    continue

                # Parse Metadata from content
                book_id, meta = self.parse_rich_text(content)
                
                # If ID is unknown, maybe try filename?
                if book_id == "unknown":
                    # filename: id.txt
                    basename = os.path.basename(txt_path)
                    book_id = os.path.splitext(basename)[0]
                
                # Prepare Batch
                batch_ids.append(book_id)
                batch_texts.append(content)
                batch_metadatas.append(meta)
                
                # Execute Batch
                if len(batch_ids) >= settings.BATCH_SIZE:
                    self._process_batch(batch_ids, batch_texts, batch_metadatas)
                    count += len(batch_ids)
                    logger.info(f"Indexed {count} books...")
                    batch_ids = []
                    batch_texts = []
                    batch_metadatas = []
                    
            except Exception as e:
                logger.error(f"Error processing file {txt_path}: {e}")
                error_count += 1

        # Final batch
        if batch_ids:
            self._process_batch(batch_ids, batch_texts, batch_metadatas)
            count += len(batch_ids)
        
        logger.info(f"Indexing Completed. Indexed: {count}. Errors: {error_count}.")

    def _process_batch(self, ids, texts, metadatas):
        embeddings = self.embedder.embed_batch(texts, is_query=False)
        if embeddings:
            self.vector_db.upsert_texts(ids=ids, vectors=embeddings, metadatas=metadatas, documents=texts)
        else:
            logger.error("Failed to generate embeddings for batch.")
