import argparse
from src.crawler import GoogleBooksCrawler
from src.data_processor import run_processor
from src.indexer import Indexer
from src.rag.chat import main as chat_main


def main():
    parser = argparse.ArgumentParser(description="AI Engine")
    parser.add_argument(
        "command",
        choices=["crawl", "process", "index", "chat"],
        help="crawl | process | index | chat"
    )

    args = parser.parse_args()

    if args.command == "crawl":
        crawler = GoogleBooksCrawler()
        crawler.run()

    elif args.command == "process":
        run_processor()

    elif args.command == "index":
        indexer = Indexer()
        indexer.run_indexing()

    elif args.command == "chat":
        chat_main()

# test
if __name__ == "__main__":
    main()
