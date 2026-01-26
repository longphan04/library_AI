import argparse
import sys
import os

from config.logging_config import setup_logging

# Determine command from args
command = sys.argv[1] if len(sys.argv) > 1 else "ai_engine"
setup_logging(command, log_to_file=True)

# NOW import modules after logging is configured
from src.crawler import GoogleBooksCrawler
from src.data_processor import run_processor
from src.indexer import Indexer
from src.rag.chat import main as chat_main


def main():
    parser = argparse.ArgumentParser(description="AI Engine")
    parser.add_argument(
        "command",
        choices=[
            "crawl",
            "process",
            "index",
            "chat",
            "sync-to-mysql",
            "api"
        ],
        help="crawl | process | index | chat | sync-to-mysql | api"
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

    elif args.command == "sync-to-mysql":
        print(">>> SYNCING TO MYSQL")
        from src.mysql.sync_data import sync_to_mysql
        sync_to_mysql()

    elif args.command == "chat":
        chat_main()


    elif args.command == "api":

        # Force production-like mode

        os.environ.setdefault("FLASK_ENV", "production")

        os.environ.setdefault("FLASK_DEBUG", "false")

        port = int(os.environ.get("PORT", 10000))

        print(f">>> STARTING API SERVER on http://0.0.0.0:{port}")

        from src.api.app import run

        run(

            host="0.0.0.0",

            port=port,

            debug=False

        )


if __name__ == "__main__":
    main()
