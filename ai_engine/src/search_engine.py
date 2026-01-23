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
                    "title": "Python",          # Tìm trong tiêu đề (partial match)
                    "authors": "Mark Lutz",     # Tìm tác giả (partial match)
                    "category": "Programming",  # Thể loại (exact match)
                    "publish_year": "2023"      # Năm xuất bản (exact match)
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

        # 2. Tách filters thành ChromaDB filters và Python filters
        chromadb_filters, python_filters = self._split_filters(filters) if filters else ({}, {})

        # 3. Build ChromaDB where clause (chỉ dùng exact match filters)
        where_filter = self._build_where_clause(chromadb_filters) if chromadb_filters else None

        # 4. Query vector DB với top_k cao hơn nếu có python filters
        # Use a larger candidate pool when we have python-level filters
        # so there is a higher chance matching metadata appears in the candidate set.
        # Keep a reasonable cap to avoid huge queries.
        if python_filters:
            query_limit = min(max(top_k * 10, top_k * 3), 1000)
        else:
            query_limit = top_k
        results = self.vector_db.query_vectors(
            query_vector=query_vector,
            n_results=query_limit,
            where_filter=where_filter
        )

        # 5. Format results
        formatted = self._format_search_results(results)

        # 6. Apply Python filters (partial match cho title/authors)
        if python_filters:
            formatted = self._apply_python_filters(formatted, python_filters)

            # 6b) If python filters yielded nothing, try a broader candidate set as a fallback
            # This helps when the author/title exists in the DB but was not within the
            # initial semantic-nearest neighbors window.
            if not formatted:
                logger.info("Python filters returned no results; trying broader candidate window for fallback")
                broad_limit = min(max(top_k * 100, 500), 2000)
                try:
                    broad_results = self.vector_db.query_vectors(
                        query_vector=query_vector,
                        n_results=broad_limit,
                        where_filter=where_filter,
                    )
                    broad_formatted = self._format_search_results(broad_results)
                    formatted = self._apply_python_filters(broad_formatted, python_filters)
                except Exception:
                    logger.exception("Fallback broad query failed")

        # 7. Giới hạn kết quả về top_k
        return formatted[:top_k]

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
                    "identifier": meta.get("identifier", ""),
                    "title": meta.get("title", "Unknown"),
                    "authors": meta.get("authors", "Unknown"),
                    "category": meta.get("category", ""),
                    "publish_year": meta.get("publish_year", ""),
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
            "identifier": metadata.get("identifier", ""),
            "title": metadata.get("title", "Unknown"),
            "authors": metadata.get("authors", "Unknown"),
            "category": metadata.get("category", ""),
            "publish_year": metadata.get("publish_year", ""),
            "richtext": book_data['document']
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
            if meta.get("publish_year"):
                years.add(meta["publish_year"])
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

    def _split_filters(self, filters: Dict) -> tuple:
        """
        Tách filters thành ChromaDB filters (exact match) và Python filters (partial match).

        Args:
            filters: User-provided filters

        Returns:
            (chromadb_filters, python_filters) tuple
        """
        chromadb_filters = {}
        python_filters = {}

        # Category và year dùng ChromaDB (exact match)
        if filters.get("category"):
            chromadb_filters["category"] = filters["category"]
        if filters.get("publish_year"):
            chromadb_filters["publish_year"] = filters["publish_year"]

        # Title và authors dùng Python (partial match)
        if filters.get("title"):
            python_filters["title"] = filters["title"].lower()
        if filters.get("authors"):
            python_filters["authors"] = filters["authors"].lower()

        return chromadb_filters, python_filters

    def _apply_python_filters(self, results: List[Dict], python_filters: Dict) -> List[Dict]:
        """
        Apply partial match filters trong Python.

        Args:
            results: Formatted search results
            python_filters: Dict with title/authors filters

        Returns:
            Filtered results
        """
        filtered = []

        for book in results:
            match = True

            # Check title filter (partial match, case-insensitive)
            if "title" in python_filters:
                book_title = book.get("title", "").lower()
                if python_filters["title"] not in book_title:
                    match = False

            # Check authors filter (partial match, case-insensitive)
            if "authors" in python_filters and match:
                book_authors = book.get("authors", "").lower()
                if python_filters["authors"] not in book_authors:
                    match = False

            if match:
                filtered.append(book)

        logger.info(f"Python filters reduced {len(results)} to {len(filtered)} results")
        return filtered

    def _build_where_clause(self, filters: Dict) -> Dict:
        """
        Chuyển filters dict thành ChromaDB where clause.

        Hỗ trợ filters:
        - title: exact match (ChromaDB không hỗ trợ $contains nên dùng $eq)
        - authors: exact match
        - category: exact match
        - publish_year: exact match

        Args:
            filters: User-provided filters

        Returns:
            ChromaDB where clause hoặc None nếu không có filters

        Note: ChromaDB chỉ hỗ trợ: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
        Không hỗ trợ $contains nên ta phải dùng $eq cho exact match
        """
        where_conditions = []

        # Category filter (exact match)
        if filters.get("category"):
            where_conditions.append({
                "category": {"$eq": filters["category"]}
            })

        # Year filter (exact match)
        if filters.get("publish_year"):
            where_conditions.append({
                "publish_year": {"$eq": filters["publish_year"]}
            })

        # Title filter (exact match - ChromaDB limitation)
        # Note: Để tìm partial match, cần query sau đó filter trong Python
        if filters.get("title"):
            where_conditions.append({
                "title": {"$eq": filters["title"]}
            })

        # Authors filter (exact match - ChromaDB limitation)
        if filters.get("authors"):
            where_conditions.append({
                "authors": {"$eq": filters["authors"]}
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
            document = results['documents'][0][i]  # Rich text đầy đủ
            distance = results['distances'][0][i]

            books.append({
                "identifier": meta.get("isbn", ""),  # Unified field name
                "title": meta.get("title", "Unknown"),
                "authors": meta.get("authors", "Unknown"),
                "category": meta.get("category", ""),
                "publish_year": meta.get("publish_year", ""),
                "score": round(1 - distance, 4),  # Convert distance to similarity
                "richtext": document  # Full rich text document
            })

        return books
