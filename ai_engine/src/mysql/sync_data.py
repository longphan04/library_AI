"""
Sync processed book data from JSON to MySQL database.
"""

import glob
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import settings
from config.logging_config import get_logger

# Get logger (config done in main.py)
logger = get_logger("SyncMySQL")

# Import after logging setup
from src.mysql.data_inserter import DataInserter


def sync_to_mysql():
    """
    Read processed JSON files and insert to MySQL database.
    """
    # Find processed JSON files (correct pattern)
    pattern = os.path.join(settings.DATA_PROCESSED_DIR, "clean_books_*.json")
    json_files = glob.glob(pattern)
    
    if not json_files:
        logger.warning(f"No processed files found in {settings.DATA_PROCESSED_DIR}")
        logger.info("Run 'python main.py process' first")
        return
    
    logger.info(f"Found {len(json_files)} processed file(s)")
    
    # Initialize inserter
    inserter = DataInserter()
    total_books = 0
    
    try:
        for json_file in json_files:
            logger.info(f"Processing: {os.path.basename(json_file)}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                books = json.load(f)
            
            logger.info(f"  Found {len(books)} books")
            
            for book in books:
                inserter.insert_book(book)
                total_books += 1
                
                if total_books % 50 == 0:
                    logger.info(f"  Progress: {total_books} books...")
        
        # Print stats
        inserter.print_stats()
        logger.info(f"Total: {total_books} books processed")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    
    finally:
        inserter.close()


if __name__ == "__main__":
    sync_to_mysql()
