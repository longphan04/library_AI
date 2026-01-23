import argparse
import sys

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
            "download-images",
            "export-be",
            "api"
        ],
        help="crawl | process | index | chat | download-images | export-be | api"
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

    elif args.command == "download-images":
        print(">>> DOWNLOADING IMAGES")
        from src.download_images import download_images
        download_images()
    
    elif args.command == "export-be":
        print(">>> EXPORTING FOR BACKEND")
        from src.export_for_be import export_for_be
        export_for_be()

    elif args.command == "chat":
        chat_main()

    elif args.command == "api":
        print(">>> STARTING API SERVER on http://0.0.0.0:9999")
        print(">>> Use Ctrl+C to stop")
        from src.api.app import run
        run(host="0.0.0.0", port=9999, debug=False)


if __name__ == "__main__":
    main()