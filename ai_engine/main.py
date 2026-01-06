import argparse
import logging
from src.crawler import GoogleBooksCrawler
from src.data_processor import run_processor
from src.indexer import Indexer

# Setup simple logger for main
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Main")

def main():
    parser = argparse.ArgumentParser(description="AI Engine CLI")
    parser.add_argument("command", choices=["crawl", "process", "index"], 
                        help="crawl: Fetch data | process: Clean data | index: Vectorize data")
    
    args = parser.parse_args()

    if args.command == "crawl":
        print(">>> RUNNING CRAWLER")
        crawler = GoogleBooksCrawler()
        crawler.run()
        
    elif args.command == "process":
        print(">>> RUNNING PROCESSOR")
        run_processor()
        
    elif args.command == "index":
        print(">>> RUNNING INDEXER")
        indexer = Indexer()
        indexer.run_indexing()

if __name__ == "__main__":
    main()
