import argparse
import sys

# CRITICAL: Setup logging FIRST, before importing any other modules
from config.logging_config import setup_logging

# Determine command from args
command = sys.argv[1] if len(sys.argv) > 1 else "ai_engine"
setup_logging(command, log_to_file=True)

# NOW import modules after logging is configured
from src.crawler import GoogleBooksCrawler
from src.data_processor import run_processor
from src.indexer import Indexer

def main():
    parser = argparse.ArgumentParser(description="AI Engine")
    parser.add_argument("command", choices=[
        "crawl", 
        "process", 
        "index",
        "sync-to-mysql"
    ], 
        help="crawl: Tải raw data | process: Làm sạch | index: Vector hóa | sync-to-mysql: Đồng bộ MySQL"
    )
    
    args = parser.parse_args()

    if args.command == "crawl":
        crawler = GoogleBooksCrawler()
        crawler.run()
        
    elif args.command == "process":
        run_processor()
        
    elif args.command == "index":
        print(">>> RUNNING INDEXER")
        indexer = Indexer()
        indexer.run_indexing()
    
    elif args.command == "sync-to-mysql":
        print(">>> SYNCING TO MYSQL")
        from src.mysql.sync_data import sync_to_mysql
        sync_to_mysql()

if __name__ == "__main__":
    main()