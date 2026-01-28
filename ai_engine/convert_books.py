"""
Convert book1.json and book2.json to Google Books API raw format
"""
import json
from datetime import datetime

def convert_to_raw_format(books, source_file):
    """Convert custom book format to Google Books API format"""
    raw_books = []
    
    for book in books:
        # Split category_ids and get first category name
        category_ids = book.get('category_ids', '').split(',')
        # Map category IDs to names (based on migration.sql)
        category_map = {
            '1': 'Công nghệ thông tin',
            '2': 'Máy tính',
            '3': 'Trí tuệ và Dữ liệu',
            '4': 'Kỹ thuật',
            '5': 'Toán',
            '6': 'Vật lý',
            '7': 'Hóa học',
            '8': 'Sinh học',
            '9': 'Môi trường',
            '10': 'Kinh tế',
            '11': 'Kinh doanh',
            '12': 'Tài chính',
            '13': 'Marketing',
            '14': 'Khởi nghiệp',
            '15': 'Tâm lý',
            '16': 'Xã hội',
            '17': 'Lịch sử',
            '18': 'Giáo dục',
            '19': 'Ngoại ngữ',
            '20': 'Kỹ năng',
            '21': 'Văn học',
            '22': 'Khác'
        }
        
        categories = [category_map.get(cid.strip(), 'Khác') for cid in category_ids if cid.strip()]
        
        # Split authors
        authors = [a.strip() for a in book.get('author_ids', '').split(',') if a.strip()]
        
        # Convert to Google Books API format
        raw_book = {
            'id': book.get('identifier', ''),
            'volumeInfo': {
                'title': book.get('title', ''),
                'authors': authors,
                'publisher': book.get('publisher_id', 'Unknown'),
                'publishedDate': str(book.get('publish_year', '2024')),
                'description': book.get('description', ''),
                'industryIdentifiers': [
                    {
                        'type': 'ISBN_13',
                        'identifier': book.get('identifier', '')
                    }
                ],
                'categories': categories,
                'imageLinks': {
                    'thumbnail': book.get('cover_url', '')
                },
                'language': 'vi' if 'Tiếng Việt' in book.get('language', '') else 'en'
            }
        }
        
        raw_books.append(raw_book)
    
    return raw_books

def main():
    # Read book1.json
    print("Reading book1.json...")
    with open('book1.json', 'r', encoding='utf-8') as f:
        books1 = json.load(f)
    
    # Read book2.json
    print("Reading book2.json...")
    with open('book2.json', 'r', encoding='utf-8') as f:
        books2 = json.load(f)
    
    # Convert to raw format
    print("Converting book1.json to raw format...")
    raw_books1 = convert_to_raw_format(books1, 'book1')
    
    print("Converting book2.json to raw format...")
    raw_books2 = convert_to_raw_format(books2, 'book2')
    
    # Save to data/raw/
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    output1 = f'data/raw/raw_imported_books1_{timestamp}_50.json'
    output2 = f'data/raw/raw_imported_books2_{timestamp}_50.json'
    
    print(f"Saving {len(raw_books1)} books to {output1}...")
    with open(output1, 'w', encoding='utf-8') as f:
        json.dump(raw_books1, f, ensure_ascii=False, indent=2)
    
    print(f"Saving {len(raw_books2)} books to {output2}...")
    with open(output2, 'w', encoding='utf-8') as f:
        json.dump(raw_books2, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"CONVERSION COMPLETE")
    print(f"{'='*60}")
    print(f"Converted {len(raw_books1)} books from book1.json")
    print(f"Converted {len(raw_books2)} books from book2.json")
    print(f"Total: {len(raw_books1) + len(raw_books2)} books")
    print(f"{'='*60}")
    print(f"\nYou can now run: python main.py process")

if __name__ == '__main__':
    main()
