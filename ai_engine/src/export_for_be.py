"""
Export processed books to BE-friendly format.

Output format matches migration.sql schema:
- identifier (VARCHAR 20)
- title (VARCHAR 255)
- cover_image format: "books/filename.jpg"
- Vietnamese categories
"""

import os
import sys
import json
import glob
import re

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

def slugify_filename(title):
    """Convert title to safe filename (without external slugify dependency)"""
    # Convert to lowercase
    slug = title.lower()
    # Replace Vietnamese characters
    replacements = {
        'á': 'a', 'à': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'đ': 'd',
        'é': 'e', 'è': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'í': 'i', 'ì': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ó': 'o', 'ò': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ú': 'u', 'ù': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ý': 'y', 'ỳ': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    }
    for vietnamese, ascii_char in replacements.items():
        slug = slug.replace(vietnamese, ascii_char)
    
    # Remove special characters, keep only alphanumeric and spaces
    slug = re.sub(r'[^a-z0-9\s]', '', slug)
    # Replace spaces with underscores
    slug = re.sub(r'\s+', '_', slug)
    # Remove multiple underscores
    slug = re.sub(r'_+', '_', slug)
    # Strip underscores from edges
    slug = slug.strip('_')
    
    # Limit length and add extension
    return slug[:50] + '.jpg'

def validate_book(book):
    """
    Validate and clean book data.
    Returns None if invalid, cleaned book if valid.
    
    Drop if:
    - Missing identifier or title
    - identifier > 20 chars
    - title > 255 chars (truncate)
    """
    # Required fields
    if not book.get('identifier') or not book.get('title'):
        return None
    
    # Length validation
    if len(book['identifier']) > 20:
        return None
    
    # Truncate title if too long
    title = book['title']
    if len(title) > 255:
        title = title[:252] + '...'
    
    # Clean book
    return {
        **book,
        'title': title
    }

# Category name to ID mapping
# Must match EXACTLY with migration.sql category names (lines 643-670)
CATEGORY_MAP = {
    'Công nghệ thông tin': '1',
    'Máy tính': '2',
    'Trí tuệ và Dữ liệu': '3',
    'Kỹ thuật': '4',
    'Toán': '5',
    'Vật lý': '6',
    'Hóa học': '7',
    'Sinh học': '8',
    'Môi trường': '9',
    'Kinh tế': '10',
    'Kinh doanh': '11',
    'Tài chính': '12',
    'Marketing': '13',
    'Khởi nghiệp': '14',
    'Tâm lý': '15',
    'Xã hội': '16',
    'Lịch sử': '17',
    'Giáo dục': '18',
    'Ngoại ngữ': '19',
    'Kỹ năng': '20',
    'Văn học': '21',
    'Khác': '22'
}

def map_category_to_id(category_name):
    """Map category name to ID, return '22' (Khác) if not found"""
    return CATEGORY_MAP.get(category_name.strip(), '22')

def export_for_be():
    """Export books in BE-ready format"""
    print("="*60)
    print("EXPORT FOR BACKEND")
    print("="*60)
    
    # Load all processed books
    pattern = os.path.join(settings.DATA_PROCESSED_DIR, "clean_books_*.json")
    files = glob.glob(pattern)
    
    if not files:
        print("No processed files found!")
        return
    
    all_books = []
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            all_books.extend(json.load(f))
    
    print(f"\nLoaded {len(all_books)} processed books")
    
    # Convert to BE format
    be_books = []
    dropped = 0
    
    for book in all_books:
        # Validate
        validated = validate_book(book)
        if not validated:
            dropped += 1
            continue
        
        # Convert format
        be_book = {
            "identifier": validated['identifier'],
            "title": validated['title'],
            "description": validated.get('description', ''),
            "publish_year": int(validated['publish_year']) if validated['publish_year'].isdigit() else None,
            "language": validated.get('language', 'en'),
            "cover_url": f"book/{validated['identifier']}.jpg" if validated.get('cover_url') else "",  # Empty if no image
            "publisher": validated.get('publisher', 'Unknown'),
            "categories": [map_category_to_id(c.strip()) for c in validated.get('category', 'Khác').split(',')],
            "authors": [a.strip() for a in validated.get('authors', 'Unknown').split(',')],
            "shelf_code": "1A-01"  # Default, BE will reassign
        }
        be_books.append(be_book)
    
    # Save export
    output_dir = os.path.join(settings.BASE_DIR, "data", "export")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "books_for_be.json")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(be_books, f, ensure_ascii=False, indent=2)
    
    # Also export as CSV for BE
    csv_output_path = os.path.join(output_dir, "books_for_be.csv")
    
    import csv
    if be_books:
        with open(csv_output_path, 'w', encoding='utf-8', newline='') as f:
            # CSV headers
            fieldnames = ['identifier', 'title', 'description', 'publish_year', 
                         'language', 'cover_url', 'publisher', 'categories', 
                         'authors', 'shelf_code']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write rows
            for book in be_books:
                # Convert list fields to comma-separated strings for CSV
                csv_row = {
                    **book,
                    'categories': '; '.join(book['categories']),  # Join with semicolon
                    'authors': '; '.join(book['authors'])
                }
                writer.writerow(csv_row)
    
    # Summary
    print(f"\n{'='*60}")
    print("EXPORT COMPLETE")
    print(f"{'='*60}")
    print(f"Total books:     {len(all_books)}")
    print(f"Valid exported:  {len(be_books)}")
    print(f"Dropped invalid: {dropped}")
    print(f"\nJSON: {output_path}")
    print(f"CSV:  {csv_output_path}")
    print(f"{'='*60}\n")
    
    # Show sample
    if be_books:
        print("Sample book:")
        print(json.dumps(be_books[0], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    export_for_be()
