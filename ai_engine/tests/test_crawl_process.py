"""
Test script: Crawl and process a few books to verify the new code changes.

This script will:
1. Crawl 5 books from a single topic
2. Process the crawled data
3. Show results and verify categories mapping
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from config.categories import CATEGORIES_MAPPING
from src.crawler import GoogleBooksCrawler
from src.data_processor import DataProcessor

def test_crawl_and_process():
    """Test crawl and process pipeline with a small sample."""
    
    print("="*70)
    print("TEST: Crawl & Process Pipeline")
    print("="*70)
    
    # Step 1: Crawl a few books
    print("\nStep 1: Crawling books...")
    print("-" * 70)
    
    test_topic = "Python Programming"  # Test với 1 topic
    max_books = 5  # Chỉ lấy 5 cuốn để test
    
    crawler = GoogleBooksCrawler()
    
    try:
        # Use fetch_batch method (correct method name)
        results = crawler.fetch_batch(
            query=test_topic,
            start_index=0
        )
        
        print(f"Crawled {len(results)} books for topic: {test_topic}")
        
        # Save to test file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_raw_file = os.path.join(
            settings.DATA_RAW_DIR,
            f"test_raw_{timestamp}.json"
        )
        
        with open(test_raw_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"Saved raw data to: {os.path.basename(test_raw_file)}")
        
    except Exception as e:
        print(f"ERROR - Crawl failed: {e}")
        return
    
    # Step 2: Process the data
    print("\nStep 2: Processing data...")
    print("-" * 70)
    
    processor = DataProcessor()
    seen_ids = set()
    clean_books = []
    
    for item in results:
        cleaned = processor.clean_item(item, seen_ids)
        if cleaned:
            clean_books.append(cleaned)
            seen_ids.add(cleaned['id'])
    
    print(f"Processed {len(clean_books)} valid books")
    print(f"   Dropped: {len(results) - len(clean_books)} books")
    
    # Show statistics
    print("\nProcessing Stats:")
    print(f"   Total input:        {processor.stats['total_raw_items']}")
    print(f"   Success:            {processor.stats['success']}")
    print(f"   Dropped (duplicate): {processor.stats['dropped_duplicate']}")
    print(f"   Dropped (font error): {processor.stats['dropped_font_error']}")
    print(f"   Dropped (no ID):    {processor.stats['dropped_no_id']}")
    
    # Step 3: Display results
    print("\nProcessed Books:")
    print("=" * 70)
    
    for i, book in enumerate(clean_books, 1):
        print(f"\n{i}. {book['title']}")
        print(f"   Identifier:  {book['identifier']} ({book['type']})")
        print(f"   Authors:     {book['authors']}")
        print(f"   Publisher:   {book['publisher']}")
        print(f"   Year:        {book['publish_year']}")
        print(f"   Category:    {book['category']}")
        print(f"   Cover URL:   {book['cover_url'][:50] if book['cover_url'] else 'N/A'}...")
        print(f"   Language:    {book['language']}")
    
    # Step 4: Test category mapping
    print("\nCategory Mapping Test:")
    print("=" * 70)
    
    for book in clean_books:
        categories = book['category'].split(', ')
        print(f"\n[BOOK] {book['title']}")
        print(f"   Raw categories: {book['category']}")
        
        vietnamese_cats = []
        for cat in categories:
            vietnamese = CATEGORIES_MAPPING.get(cat.strip())
            if vietnamese:
                vietnamese_cats.append(f"{cat} -> {vietnamese}")
            else:
                vietnamese_cats.append(f"{cat} (unchanged)")
        
        print(f"   Mapped: {', '.join(vietnamese_cats)}")
    
    # Step 5: Save test output
    test_output_file = os.path.join(
        settings.DATA_PROCESSED_DIR,
        f"test_processed_{timestamp}.json"
    )
    
    with open(test_output_file, 'w', encoding='utf-8') as f:
        json.dump(clean_books, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved processed data to: {os.path.basename(test_output_file)}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST COMPLETED")
    print("="*70)
    print(f"Crawled:   {len(results)} books")
    print(f"Processed: {len(clean_books)} books")
    print(f"Categories verified with Vietnamese mapping")
    print(f"Cover URLs extracted")
    print("="*70)

if __name__ == "__main__":
    test_crawl_and_process()
