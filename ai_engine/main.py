import argparse
from src.crawler import GoogleBooksCrawler
from src.data_processor import run_processor

def main():
    parser = argparse.ArgumentParser(description="AI Engine")
    parser.add_argument("command", choices=["crawl", "process"], 
                        help="crawl: Tải raw data | process: Làm sạch và lưu JSON/CSV")
    
    args = parser.parse_args()

    if args.command == "crawl":
        crawler = GoogleBooksCrawler()
        crawler.run()
        
    elif args.command == "process":
        run_processor()

if __name__ == "__main__":
    main()