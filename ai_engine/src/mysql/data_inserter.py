import logging
import re
from typing import Optional, List

from src.database import get_db
from config.categories import CATEGORIES_MAPPING  # Import categories mapping

# Get logger (will use centralized config)
logger = logging.getLogger("DataInserter")


class DataInserter:
    """
    Insert processed book data into MySQL database.
    Handles publishers, categories, authors, and N-N relationships.
    """
    
    def __init__(self):
        self.conn = get_db()
        self.cursor = self.conn.cursor(dictionary=True)
        
        # Caches to avoid duplicate queries
        self._publisher_cache = {}
        self._category_cache = {}
        self._author_cache = {}
        self._shelf_cache = {}
        
        # Stats
        self.stats = {
            "books_inserted": 0,
            "books_skipped": 0,
            "publishers_created": 0,
            "categories_created": 0,
            "authors_created": 0
        }
    
    def insert_book(self, processed_data: dict) -> Optional[int]:
        """
        Insert a single book from DataProcessor output.
        
        Args:
            processed_data: Output from DataProcessor.clean_item()
            
        Returns:
            book_id if successful, None otherwise
        """
        try:
            # Extract data
            api_id = processed_data.get("id")
            identifier = processed_data.get("identifier")
            title = processed_data.get("title")
            description = processed_data.get("description", "")
            
            # Parse year - FIX: use publish_year
            year_str = processed_data.get("publish_year", "N/A")
            publish_year = int(year_str) if year_str.isdigit() else None
            
            # Language mapping
            lang_code = processed_data.get("language", "en")
            language = self._map_language(lang_code)
            
            # Cover URL - Support both field names
            cover_url = processed_data.get("cover_url") or processed_data.get("thumbnail")
            
            # Publisher
            publisher_name = processed_data.get("publisher", "Unknown")
            publisher_id = self._get_or_create_publisher(publisher_name)
            
            # Category
            category_raw = processed_data.get("category", "General")
            categories = self._normalize_categories([category_raw])
            
            # Authors
            authors_str = processed_data.get("authors", "Unknown")
            authors = self._parse_authors(authors_str)
            
            # Assign shelf
            shelf_id = self._assign_shelf(categories)
            
            # Check if book already exists (by identifier)
            if identifier:
                self.cursor.execute(
                    "SELECT book_id FROM books WHERE identifier = %s",
                    (identifier,)
                )
                existing = self.cursor.fetchone()
                if existing:
                    logger.info(f"Book already exists: {title} (identifier: {identifier})")
                    self.stats["books_skipped"] += 1
                    return existing['book_id']
            
            # Insert book
            self.cursor.execute("""
                INSERT INTO books (
                    identifier, title, description, publish_year,
                    language, cover_url, publisher_id, shelf_id,
                    status, total_copies, available_copies, total_borrow_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                identifier,
                title,
                description if description else None,  # Full description
                publish_year,
                language,
                cover_url,
                publisher_id,
                shelf_id,
                'ACTIVE',
                0,  # total_copies - No physical copies yet
                0,  # available_copies
                0   # total_borrow_count
            ))
            
            book_id = self.cursor.lastrowid
            
            # Link categories
            for category in categories:
                category_id = self._get_or_create_category(category)
                self._link_book_category(book_id, category_id)
            
            # Link authors
            for author in authors:
                author_id = self._get_or_create_author(author)
                self._link_book_author(book_id, author_id)
            
            self.conn.commit()
            self.stats["books_inserted"] += 1
            logger.info(f"Inserted: {title} (book_id={book_id})")
            
            return book_id
            
        except Exception as e:
            logger.error(f"Failed to insert book '{title}': {e}")
            self.conn.rollback()
            self.stats["books_skipped"] += 1
            return None
    
    def _map_language(self, lang_code: str) -> str:
        """Map language code to full name"""
        mapping = {
            'en': 'English',
            'vi': 'Vietnamese'
        }
        return mapping.get(lang_code, lang_code.upper() if lang_code else 'Unknown')
    
    def _normalize_categories(self, categories_raw: List[str]) -> List[str]:
        """
        Normalize category names and convert to Vietnamese.
        Examples:
            "Computers / Programming" → "Lập trình"
            "Fiction & Literature" → "Tiểu thuyết"
            "Technology" → "Công nghệ"
        """
        normalized = []
        for cat in categories_raw:
            if not cat or cat == "N/A":
                continue
            
            # Split by , and process each category
            parts = cat.split(',')
            for part in parts:
                part = part.strip()
                
                # Map to Vietnamese if exists in mapping
                vietnamese = CATEGORIES_MAPPING.get(part)
                if vietnamese:
                    normalized.append(vietnamese)
                else:
                    # Fallback: use normalized English name
                    normalized.append(part)
        
        return list(set(normalized)) if normalized else ["Tổng hợp"]
    
    def _parse_authors(self, authors_str: str) -> List[str]:
        """Parse authors string to list"""
        if not authors_str or authors_str == "Unknown":
            return ["Unknown"]
        
        # Split by comma
        authors = [a.strip() for a in authors_str.split(',')]
        return [a for a in authors if a]  # Filter empty
    
    def _get_or_create_publisher(self, name: str) -> Optional[int]:
        """Get publisher_id, create if not exists"""
        if not name or name == "Unknown":
            return None
        
        # Normalize name
        name = self._normalize_publisher(name)
        
        if name in self._publisher_cache:
            return self._publisher_cache[name]
        
        # Check exists
        self.cursor.execute(
            "SELECT publisher_id FROM publishers WHERE name = %s",
            (name,)
        )
        result = self.cursor.fetchone()
        
        if result:
            publisher_id = result['publisher_id']
        else:
            # Insert new
            self.cursor.execute(
                "INSERT INTO publishers (name) VALUES (%s)",
                (name,)
            )
            publisher_id = self.cursor.lastrowid
            self.stats["publishers_created"] += 1
            logger.debug(f"Created publisher: {name}")
        
        self._publisher_cache[name] = publisher_id
        return publisher_id
    
    def _normalize_publisher(self, name: str) -> str:
        """Normalize publisher name"""
        # Remove ", Inc.", " Ltd.", etc
        cleaned = re.sub(r',?\s*(Inc\.|Ltd\.|LLC|Corporation)\.?$', '', name, flags=re.IGNORECASE)
        return cleaned.strip()
    
    def _get_or_create_category(self, name: str) -> int:
        """Get category_id, create if not exists"""
        if name in self._category_cache:
            return self._category_cache[name]
        
        self.cursor.execute(
            "SELECT category_id FROM categories WHERE name = %s",
            (name,)
        )
        result = self.cursor.fetchone()
        
        if result:
            category_id = result['category_id']
        else:
            self.cursor.execute(
                "INSERT INTO categories (name) VALUES (%s)",
                (name,)
            )
            category_id = self.cursor.lastrowid
            self.stats["categories_created"] += 1
            logger.debug(f"Created category: {name}")
        
        self._category_cache[name] = category_id
        return category_id
    
    def _get_or_create_author(self, name: str) -> int:
        """Get author_id, create if not exists"""
        if name in self._author_cache:
            return self._author_cache[name]
        
        self.cursor.execute(
            "SELECT author_id FROM authors WHERE name = %s",
            (name,)
        )
        result = self.cursor.fetchone()
        
        if result:
            author_id = result['author_id']
        else:
            self.cursor.execute(
                "INSERT INTO authors (name) VALUES (%s)",
                (name,)
            )
            author_id = self.cursor.lastrowid
            self.stats["authors_created"] += 1
            logger.debug(f"Created author: {name}")
        
        self._author_cache[name] = author_id
        return author_id
    
    def _assign_shelf(self, categories: List[str]) -> int:
        """Assign shelf based on Vietnamese category names (aligned with migration.sql)"""
        # Category → Shelf mapping (20 categories from migration.sql)
        category_to_shelf = {
            # Technology & Programming (Day 1A)
            "Công nghệ thông tin": "1A-01",
            "Khoa học máy tính": "1A-01",
            "Lập trình": "1A-01",
            "Trí tuệ nhân tạo": "1A-02",
            "Khoa học dữ liệu": "1A-03",
            "Mạng máy tính": "1A-04",
            "An toàn thông tin": "1A-05",
            
            # Science & Math (Day 1D)
            "Toán học": "1D-01",
            "Vật lý": "1D-02",
            "Hóa học": "1D-03",
            "Sinh học": "1D-04",
            
            # Business & Economics (Day 1B)
            "Kinh tế": "1B-01",
            "Quản trị kinh doanh": "1B-02",
            "Marketing": "1B-03",
            "Tài chính - Ngân hàng": "1B-04",
            
            # Skills & Psychology (Day 1B)
            "Kỹ năng mềm": "1B-05",
            "Tâm lý học": "1B-05",
            
            # Humanities (Day 1C)
            "Văn học": "1C-01",
            "Lịch sử": "1C-02",
            "Ngoại ngữ": "1C-03"
        }
        
        for cat in categories:
            if cat in category_to_shelf:
                shelf_code = category_to_shelf[cat]
                return self._get_shelf_id(shelf_code)
        
        # Default shelf if no match (Tech shelf)
        return self._get_shelf_id("1A-01")
    
    def _get_shelf_id(self, code: str) -> int:
        """Get shelf_id by code"""
        if code in self._shelf_cache:
            return self._shelf_cache[code]
        
        self.cursor.execute(
            "SELECT shelf_id FROM shelves WHERE code = %s",
            (code,)
        )
        result = self.cursor.fetchone()
        
        if result:
            shelf_id = result['shelf_id']
            self._shelf_cache[code] = shelf_id
            return shelf_id
        
        # Fallback to first shelf
        return 1
    
    def _link_book_category(self, book_id: int, category_id: int):
        """Link book to category (N-N)"""
        try:
            self.cursor.execute("""
                INSERT IGNORE INTO book_categories (book_id, category_id)
                VALUES (%s, %s)
            """, (book_id, category_id))
        except Exception as e:
            logger.error(f"Failed to link category: {e}")
    
    def _link_book_author(self, book_id: int, author_id: int):
        """Link book to author (N-N)"""
        try:
            self.cursor.execute("""
                INSERT IGNORE INTO book_authors (book_id, author_id)
                VALUES (%s, %s)
            """, (book_id, author_id))
        except Exception as e:
            logger.error(f"Failed to link author: {e}")
    
    def print_stats(self):
        """Print insertion statistics"""
        print("\n" + "="*60)
        print("DATA INSERTION STATISTICS")
        print("="*60)
        print(f"Books inserted:      {self.stats['books_inserted']}")
        print(f"Books skipped:       {self.stats['books_skipped']}")
        print(f"Publishers created:  {self.stats['publishers_created']}")
        print(f"Categories created:  {self.stats['categories_created']}")
        print(f"Authors created:     {self.stats['authors_created']}")
        print("="*60 + "\n")
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
        self.conn.close()
