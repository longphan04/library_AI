import logging
import re
from typing import Optional, List

from src.database import get_db

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
            isbn = processed_data.get("identifier")
            title = processed_data.get("title")
            description = processed_data.get("description", "")
            
            # Parse year
            year_str = processed_data.get("published_year", "N/A")
            publish_year = int(year_str) if year_str.isdigit() else None
            
            # Language mapping
            lang_code = processed_data.get("language", "en")
            language = self._map_language(lang_code)
            
            # Cover URL
            cover_url = processed_data.get("thumbnail")
            
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
            
            # Check if book already exists (by ISBN)
            if isbn:
                self.cursor.execute(
                    "SELECT book_id FROM books WHERE isbn = %s",
                    (isbn,)
                )
                existing = self.cursor.fetchone()
                if existing:
                    logger.info(f"Book already exists: {title} (ISBN: {isbn})")
                    self.stats["books_skipped"] += 1
                    return existing['book_id']
            
            # Insert book
            self.cursor.execute("""
                INSERT INTO books (
                    isbn, title, description, publish_year,
                    language, cover_url, publisher_id, shelf_id,
                    status, total_copies, available_copies
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                isbn,
                title,
                description if description else None,  # Full description
                publish_year,
                language,
                cover_url,
                publisher_id,
                shelf_id,
                'ACTIVE',
                0,  # No physical copies yet
                0
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
        Normalize category names.
        Examples:
            "Computers / Programming" → "Programming"
            "Fiction & Literature" → "Fiction"
        """
        normalized = []
        for cat in categories_raw:
            if not cat or cat == "N/A":
                continue
            
            # Split by / and take last part
            parts = cat.split('/')
            last_part = parts[-1].strip()
            
            # Remove " & Literature" suffix
            last_part = re.sub(r'\s*&\s*(Literature|Fiction)$', '', last_part)
            
            normalized.append(last_part)
        
        return list(set(normalized)) if normalized else ["General"]
    
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
        """Assign shelf based on category"""
        # Category → Shelf mapping
        category_to_shelf = {
            "Programming": "1A-01",
            "Computers": "1A-01",
            "AI": "1A-02",
            "Artificial Intelligence": "1A-02",
            "Data Science": "1A-03",
            "Machine Learning": "1A-03",
            "History": "1B-01",
            "Novel": "1C-01",
            "Fiction": "1C-02",
            "Science": "1D-01"
        }
        
        for cat in categories:
            if cat in category_to_shelf:
                shelf_code = category_to_shelf[cat]
                return self._get_shelf_id(shelf_code)
        
        # Default shelf
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
