import argparse

from src.crawler import GoogleBooksCrawler
from src.data_processor import run_processor
from src.indexer import Indexer

def main():
    parser = argparse.ArgumentParser(description="AI Engine")
    parser.add_argument("command", choices=["crawl", "process", "index"], 
                        help="crawl: Tải raw data | process: Làm sạch và lưu JSON/CSV | index: Vector hóa và lưu vào DB")
    
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

if __name__ == "__main__":
    main()