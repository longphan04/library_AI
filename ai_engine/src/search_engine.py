import logging
from typing import List, Dict, Optional
from src.embedder import Embedder
from src.vector_db import VectorDB

logger = logging.getLogger("SearchEngine")


class SearchEngine:
    """
    Search Engine cho thư viện sách.
    Hỗ trợ:
    - Vector search (semantic search)
    - Hybrid search (vector + metadata filters)
    - Recommendation (similar books)
    """

    def __init__(self):
        self.embedder = Embedder()
        self.vector_db = VectorDB()
        self._filters_cache = None  # Cache cho filters
        logger.info("SearchEngine initialized")

    def search(
        self,
        query: str,
        filters: Optional[Dict] = None,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Tìm kiếm sách theo ngữ nghĩa với optional filters.

        Args:
            query: Câu hỏi tìm kiếm ("Sách Python cho người mới")
            filters: Dict filters, ví dụ:
                {
                    "title": "Python",          # Tìm trong tiêu đề
                    "authors": "Mark Lutz",     # Tìm tác giả
                    "category": "Programming",  # Thể loại
                    "published_year": "2023"    # Năm xuất bản
                }
            top_k: Số kết quả trả về

        Returns:
            List[Dict]: Danh sách sách với score
        """
        if not query or not query.strip():
            logger.warning("Empty query received")
            return []

        # 1. Embed query
        logger.info(f"Searching for: '{query}' with filters: {filters}")
        query_vector = self.embedder.embed_text(query, is_query=True)

        if not query_vector:
            logger.error("Failed to embed query")
            return []

        # 2. Build ChromaDB where clause
        where_filter = self._build_where_clause(filters) if filters else None

        # 3. Query vector DB
        results = self.vector_db.query_vectors(
            query_vector=query_vector,
            n_results=top_k,
            where_filter=where_filter
        )

        # 4. Format results
        return self._format_search_results(results)

    def recommend(self, book_id: str, top_k: int = 5) -> List[Dict]:
        """
        Gợi ý sách tương tự dựa trên book_id.

        Args:
            book_id: ID của sách hiện tại
            top_k: Số sách gợi ý

        Returns:
            List[Dict]: Danh sách sách tương tự
        """
        logger.info(f"Getting recommendations for book: {book_id}")

        # 1. Get current book's vector
        book_data = self.vector_db.get_by_id(book_id)

        if not book_data:
            logger.warning(f"Book {book_id} not found for recommendation")
            return []

        book_vector = book_data['embedding']

        # 2. Query nearest neighbors (lấy thêm 1 để exclude chính nó)
        results = self.vector_db.query_vectors(
            query_vector=book_vector,
            n_results=top_k + 1
        )

        # 3. Format & filter out original book
        recommendations = []
        if results and results.get('ids'):
            for i, rec_id in enumerate(results['ids'][0]):
                if rec_id == book_id:  # Skip chính nó
                    continue
                if len(recommendations) >= top_k:
                    break

                meta = results['metadatas'][0][i]
                recommendations.append({
                    "id": rec_id,
                    "title": meta.get("title", "Unknown"),
                    "authors": meta.get("authors", "Unknown"),
                    "category": meta.get("category", ""),
                    "published_year": meta.get("published_year", ""),
                    "score": round(1 - results['distances'][0][i], 4)
                })

        logger.info(f"Found {len(recommendations)} recommendations")
        return recommendations

    def get_book(self, book_id: str) -> Optional[Dict]:
        """
        Lấy thông tin chi tiết của một cuốn sách.

        Args:
            book_id: ID của sách

        Returns:
            Dict hoặc None nếu không tìm thấy
        """
        book_data = self.vector_db.get_by_id(book_id)

        if not book_data:
            logger.warning(f"Book {book_id} not found")
            return None

        metadata = book_data['metadata']
        return {
            "id": book_id,
            "title": metadata.get("title", "Unknown"),
            "authors": metadata.get("authors", "Unknown"),
            "category": metadata.get("category", ""),
            "published_year": metadata.get("published_year", ""),
            "content": book_data['document']
        }

    def get_filters(self) -> Dict:
        """
        Lấy danh sách các bộ lọc có sẵn.
        Bao gồm: categories, years, authors (top authors).

        Returns:
            Dict: {"categories": [...], "years": [...], "authors": [...]}
        """
        # Return cached nếu có
        if self._filters_cache:
            logger.info("Returning cached filters")
            return self._filters_cache

        logger.info("Building filters from metadata...")

        # Get all metadata
        all_metadata = self.vector_db.get_all_metadata()

        if not all_metadata:
            logger.warning("No metadata found for filters")
            return {"categories": [], "years": [], "authors": []}

        # Extract unique values
        categories = set()
        years = set()
        authors_set = set()

        for meta in all_metadata:
            if meta.get("category"):
                categories.add(meta["category"])
            if meta.get("published_year"):
                years.add(meta["published_year"])
            if meta.get("authors"):
                # Split multiple authors
                author_list = meta["authors"].split(",")
                for author in author_list:
                    authors_set.add(author.strip())

        # Build and cache result
        self._filters_cache = {
            "categories": sorted(list(categories)),
            "years": sorted(list(years), reverse=True),  # Newest first
            "authors": sorted(list(authors_set))[:100]  # Top 100 authors
        }

        logger.info(f"Filters built: {len(categories)} categories, "
                   f"{len(years)} years, {len(authors_set)} authors")

        return self._filters_cache

    def invalidate_cache(self):
        """Xóa cache filters khi có sách mới được thêm."""
        self._filters_cache = None
        logger.info("Filters cache invalidated")

    def _build_where_clause(self, filters: Dict) -> Dict:
        """
        Chuyển filters dict thành ChromaDB where clause.

        Hỗ trợ filters:
        - title: partial match
        - authors: partial match
        - category: exact match
        - published_year: exact match

        Args:
            filters: User-provided filters

        Returns:
            ChromaDB where clause
        """
        where_conditions = []

        # Category filter (exact match)
        if filters.get("category"):
            where_conditions.append({
                "category": {"$eq": filters["category"]}
            })

        # Year filter (exact match)
        if filters.get("published_year"):
            where_conditions.append({
                "published_year": {"$eq": filters["published_year"]}
            })

        # Title filter (contains)
        if filters.get("title"):
            where_conditions.append({
                "title": {"$contains": filters["title"]}
            })

        # Authors filter (contains)
        if filters.get("authors"):
            where_conditions.append({
                "authors": {"$contains": filters["authors"]}
            })

        # Combine conditions
        if len(where_conditions) == 0:
            return None
        elif len(where_conditions) == 1:
            return where_conditions[0]
        else:
            return {"$and": where_conditions}

    def _format_search_results(self, results) -> List[Dict]:
        """
        Format ChromaDB results thành output chuẩn.

        Args:
            results: ChromaDB query results

        Returns:
            List[Dict]: Formatted book list
        """
        books = []

        if not results or not results.get('ids'):
            return books

        for i, book_id in enumerate(results['ids'][0]):
            meta = results['metadatas'][0][i]
            document = results['documents'][0][i]
            distance = results['distances'][0][i]

            # Create snippet (first 200 chars)
            snippet = document[:200] + "..." if len(document) > 200 else document

            books.append({
                "id": book_id,
                "title": meta.get("title", "Unknown"),
                "authors": meta.get("authors", "Unknown"),
                "category": meta.get("category", ""),
                "published_year": meta.get("published_year", ""),
                "score": round(1 - distance, 4),  # Convert distance to similarity
                "snippet": snippet
            })

        return books
