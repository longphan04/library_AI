"""
Book Description Generator
Nhiệm vụ: Nhận dữ liệu từ staff (title, authors, category),
tìm sách trên Google Books API, và tạo mô tả chi tiết tối đa 1000 ký tự.
"""

import os
import logging
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from multiple possible locations
env_paths = [
    Path(__file__).parent.parent.parent / '.env',  # Root của project
    Path(__file__).parent.parent / '.env',  # ai_engine folder
    Path.cwd() / '.env',  # Current directory
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()  # Try default locations

# Configure logging
logger = logging.getLogger("BookDescriptionGenerator")


class BookDescriptionGenerator:
    """Generate detailed book descriptions using Google Books API and Gemini AI."""

    def __init__(self):
        """Initialize the description generator."""
        # Get API keys
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not self.google_api_key:
            raise ValueError(
                "Google API Key chưa được cấu hình. "
                "Vui lòng thêm GOOGLE_API_KEY vào file .env"
            )

        self.base_url = "https://www.googleapis.com/books/v1/volumes"

        # Initialize Gemini AI if available
        self.gemini_model = None
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-pro')
                logger.info("Gemini AI configured successfully")
            except Exception as e:
                logger.warning(f"Gemini AI not available: {str(e)}")

        logger.info("BookDescriptionGenerator initialized")

    def search_google_books(self, title: str, authors: str, category: str) -> Optional[Dict[str, Any]]:
        """
        Tìm kiếm sách trên Google Books API.

        Args:
            title: Tên sách
            authors: Tác giả
            category: Thể loại

        Returns:
            Dictionary chứa thông tin sách hoặc None nếu không tìm thấy
        """
        try:
            # Thử nhiều chiến lược tìm kiếm khác nhau
            search_strategies = []

            # Strategy 1: Full query with all fields
            if title and authors and category:
                search_strategies.append(f'intitle:"{title}" inauthor:"{authors}" subject:"{category}"')

            # Strategy 2: Title + Author only
            if title and authors:
                search_strategies.append(f'intitle:"{title}" inauthor:"{authors}"')

            # Strategy 3: Title only (broad search)
            if title:
                search_strategies.append(f'"{title}"')

            # Strategy 4: Simple title without quotes
            if title:
                search_strategies.append(title)

            for query in search_strategies:
                logger.info(f"Searching Google Books with query: {query}")

                params = {
                    "q": query,
                    "maxResults": 5,
                    "key": self.google_api_key,
                    "printType": "books",
                    "orderBy": "relevance"
                }

                response = requests.get(self.base_url, params=params, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    if items:
                        # Tìm sách phù hợp nhất
                        best_match = None
                        for book in items:
                            volume_info = book.get("volumeInfo", {})
                            book_title = volume_info.get("title", "").lower()
                            book_authors = [a.lower() for a in volume_info.get("authors", [])]

                            # Kiểm tra độ phù hợp
                            title_match = title.lower() in book_title or book_title in title.lower()
                            author_match = any(authors.lower() in a or a in authors.lower() for a in book_authors) if authors else True

                            if title_match or (not best_match):
                                best_match = book
                                if title_match and author_match:
                                    break  # Perfect match

                        if best_match:
                            book = best_match
                            volume_info = book.get("volumeInfo", {})
                            book_id = book.get("id")

                            result = {
                                "id": book_id,
                                "title": volume_info.get("title"),
                                "authors": volume_info.get("authors", []),
                                "publisher": volume_info.get("publisher"),
                                "publishedDate": volume_info.get("publishedDate"),
                                "description": volume_info.get("description", ""),
                                "categories": volume_info.get("categories", []),
                                "pageCount": volume_info.get("pageCount"),
                                "language": volume_info.get("language"),
                                "previewLink": volume_info.get("previewLink"),
                                "infoLink": volume_info.get("infoLink"),
                                "imageLinks": volume_info.get("imageLinks", {}),
                                "preview_text": ""  # Sẽ được fill sau
                            }

                            logger.info(f"Found book: {result['title']} by {result['authors']}")

                            # Lấy preview text từ book_id
                            if book_id:
                                preview_text = self._fetch_book_preview(book_id)
                                result["preview_text"] = preview_text

                            return result

                    logger.warning(f"No books found for query: {query}")

                elif response.status_code == 429:
                    logger.error("API quota exceeded (429)")
                    break  # Stop trying more strategies
                elif response.status_code == 403:
                    logger.error("API permission error (403)")
                    break
                else:
                    logger.error(f"API error {response.status_code}: {response.text[:200]}")

            # Không tìm thấy với tất cả strategies
            logger.warning(f"Book not found with any search strategy for: {title}")
            return None

        except Exception as e:
            logger.error(f"Error searching Google Books: {str(e)}")
            return None

    def _fetch_book_preview(self, book_id: str) -> str:
        """
        Lấy preview text/snippet từ Google Books API để đọc nội dung sách.

        Args:
            book_id: Google Books volume ID

        Returns:
            Preview text của sách (có thể rỗng nếu không có preview)
        """
        try:
            logger.info(f"Fetching preview text for book ID: {book_id}")

            # Gọi API lấy chi tiết sách kèm theo searchInfo (snippet)
            url = f"{self.base_url}/{book_id}"
            params = {"key": self.google_api_key}

            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                volume_info = data.get("volumeInfo", {})
                search_info = data.get("searchInfo", {})

                # Lấy các nguồn text
                preview_texts = []

                # 1. TextSnippet từ searchInfo
                text_snippet = search_info.get("textSnippet", "")
                if text_snippet:
                    preview_texts.append(text_snippet)

                # 2. Description (thường dài hơn snippet)
                description = volume_info.get("description", "")
                if description:
                    preview_texts.append(description)

                # 3. Subtitle
                subtitle = volume_info.get("subtitle", "")
                if subtitle:
                    preview_texts.append(f"Subtitle: {subtitle}")

                # 4. Table of Contents (nếu có)
                # Một số sách có thông tin này trong industryIdentifiers hoặc các trường khác

                combined_text = "\n\n".join(preview_texts)

                if combined_text:
                    logger.info(f"Fetched preview text: {len(combined_text)} characters")
                    return combined_text[:5000]  # Giới hạn 5000 ký tự để không quá tải
                else:
                    logger.warning(f"No preview text available for book ID: {book_id}")
                    return ""
            else:
                logger.error(f"Failed to fetch book preview: {response.status_code}")
                return ""

        except Exception as e:
            logger.error(f"Error fetching book preview: {str(e)}")
            return ""

    def generate_detailed_description(self,
                                      book_data: Dict[str, Any],
                                      input_title: str,
                                      input_authors: str,
                                      input_category: str,
                                      max_length: int = 1000) -> str:
        """
        Tạo mô tả chi tiết cho sách sử dụng Gemini AI hoặc template.

        Args:
            book_data: Dữ liệu sách từ Google Books
            input_title: Tên sách từ input
            input_authors: Tác giả từ input
            input_category: Thể loại từ input
            max_length: Độ dài tối thiểu (mặc định 2000 ký tự)

        Returns:
            Mô tả chi tiết của sách
        """
        try:
            if self.gemini_model:
                # Sử dụng Gemini AI để tạo mô tả
                logger.info("Generating description with Gemini AI...")

                if book_data:
                    # Có dữ liệu từ Google Books
                    title = book_data.get('title', input_title)
                    authors = ', '.join(book_data.get('authors', [input_authors]))
                    categories = ', '.join(book_data.get('categories', [input_category]))
                    existing_desc = book_data.get('description', '')
                    preview_text = book_data.get('preview_text', '')
                    publisher = book_data.get('publisher', 'không rõ')
                    published_date = book_data.get('publishedDate', 'không rõ')
                else:
                    # Không có dữ liệu từ Google Books, dùng input
                    title = input_title
                    authors = input_authors
                    categories = input_category
                    existing_desc = ''
                    preview_text = ''
                    publisher = 'không rõ'
                    published_date = 'không rõ'

                # Ưu tiên: preview_text (nội dung thực) > existing_desc (metadata)
                if preview_text:
                    # Có nội dung thực tế từ sách - ĐÂY LÀ TRƯỜNG HỢP TỐT NHẤT
                    logger.info(f"Using preview text ({len(preview_text)} chars) to generate description")
                    prompt = f"""
Bạn là chuyên gia phân tích sách. Bạn đã đọc một phần nội dung của cuốn sách dưới đây.
Hãy viết MÔ TẢ CHI TIẾT VÀ ĐẦY ĐỦ bằng TIẾNG VIỆT dựa trên NỘI DUNG THỰC TẾ bạn đã đọc.

**THÔNG TIN SÁCH:**
- Tên: {title}
- Tác giả: {authors}
- Thể loại: {categories}
- Xuất bản: {publisher} ({published_date})

**NỘI DUNG SÁCH ĐÃ ĐỌC:**
{preview_text}

**YÊU CẦU BẮT BUỘC:**
1. **NGÔN NGỮ:** Viết HOÀN TOÀN bằng TIẾNG VIỆT
2. **BÁM SÁT NỘI DUNG:** Phân tích và tóm tắt từ nội dung thực tế đã đọc
3. **ĐỘ DÀI:** TỐI THIỂU 500 ký tự, tối đa {max_length} ký tự
4. **NỘI DUNG CẦN VIẾT (CHI TIẾT):**
   - Giới thiệu tổng quan về sách và tác giả
   - Chủ đề chính và phụ mà sách đề cập (dựa vào nội dung đã đọc)
   - Cách tiếp cận/phương pháp độc đáo của tác giả
   - Kiến thức/kỹ năng cụ thể mà sách cung cấp cho người đọc
   - Cấu trúc và tổ chức nội dung của sách
   - Điểm nổi bật, đóng góp quan trọng của sách
   - Giá trị thực tế và ứng dụng của kiến thức trong sách
   - Đối tượng độc giả phù hợp và lý do nên đọc
   
5. **PHONG CÁCH:**
   - Viết CHI TIẾT, đầy đủ thông tin
   - Viết dựa trên PHÂN TÍCH SÂUMÔN, không chung chung
   - Nêu CỤ THỂ những gì sách trình bày với VÍ DỤ
   - Tập trung vào GIÁ TRỊ THỰC TẾ và ĐIỂM ĐẶC BIỆT
   - Sử dụng câu văn dài, đoạn văn phong phú

6. **ĐỊNH DẠNG:**
   - Không dùng heading, không dùng markdown, không dùng dấu đầu dòng
   - Viết thành nhiều đoạn văn liền mạch, chi tiết
   - Bắt đầu: "Cuốn sách..."
   - Mỗi đoạn phát triển một ý chính

Hãy viết MÔ TẢ CHI TIẾT BẰNG TIẾNG VIỆT (TỐI THIỂU 500 KÝ TỰ) dựa trên nội dung đã đọc:
"""
                elif existing_desc:
                    # Có mô tả gốc từ Google Books nhưng không có preview text
                    logger.info(f"Using existing description ({len(existing_desc)} chars)")
                    prompt = f"""
Bạn là chuyên gia phân tích sách. Hãy DỊCH VÀ MỞ RỘNG mô tả gốc dưới đây sang TIẾNG VIỆT một cách CHI TIẾT.

**THÔNG TIN SÁCH:**
- Tên: {title}
- Tác giả: {authors}
- Thể loại: {categories}
- Xuất bản: {publisher} ({published_date})

**MÔ TẢ GỐC (Tiếng Anh):**
{existing_desc}

**YÊU CẦU BẮT BUỘC:**
1. **NGÔN NGỮ:** Viết HOÀN TOÀN bằng TIẾNG VIỆT, không để từ tiếng Anh
2. **BÁM SÁT NỘI DUNG:** Dịch và MỞ RỘNG từ mô tả gốc, thêm chi tiết hợp lý
3. **ĐỘ DÀI:** TỐI THIỂU 500 ký tự, tối đa {max_length} ký tự
4. **NỘI DUNG CẦN VIẾT (CHI TIẾT):**
   - Giới thiệu về tác giả và bối cảnh viết sách
   - Dịch và giải thích các khái niệm/kỹ thuật cụ thể trong sách
   - Nêu rõ sách dạy/trình bày điều gì một cách chi tiết
   - Cấu trúc và nội dung chính của sách
   - Giá trị và ý nghĩa của sách trong lĩnh vực
   - Đối tượng độc giả phù hợp và lý do nên đọc

5. **PHONG CÁCH:**
   - Viết CHI TIẾT, đầy đủ, phong phú
   - Mở rộng các ý trong mô tả gốc
   - Giải thích rõ ràng, dễ hiểu
   - Sử dụng câu văn dài, đoạn văn phát triển tốt

6. **ĐỊNH DẠNG:**
   - Không dùng heading, không dùng markdown, không dùng dấu đầu dòng
   - Viết thành nhiều đoạn văn liền mạch
   - Bắt đầu bằng: "Cuốn sách..."

Hãy viết MÔ TẢ CHI TIẾT BẰNG TIẾNG VIỆT (TỐI THIỂU 500 KÝ TỰ) dựa trên mô tả gốc:
"""
                else:
                    # KHÔNG có mô tả gốc - tạo mô tả dựa trên title, authors, category
                    prompt = f"""
Bạn là chuyên gia phân tích sách. Hãy viết MÔ TẢ CHI TIẾT bằng TIẾNG VIỆT cho cuốn sách dựa trên thông tin có sẵn.

**THÔNG TIN SÁCH:**
- Tên: {title}
- Tác giả: {authors}
- Thể loại: {categories}
- Xuất bản: {published_date}

**YÊU CẦU BẮT BUỘC:**
1. **NGÔN NGỮ:** Viết HOÀN TOÀN bằng TIẾNG VIỆT
2. **ĐỘ DÀI:** TỐI THIỂU 500 ký tự, tối đa {max_length} ký tự
3. **NỘI DUNG CẦN VIẾT (CHI TIẾT):**
   - Giới thiệu về tác giả và uy tín của họ trong lĩnh vực
   - Dựa vào tên sách và tác giả, suy luận và mô tả chi tiết nội dung có thể có
   - Nêu cụ thể các chủ đề chính mà sách có thể đề cập
   - Phân tích giá trị, ý nghĩa và đóng góp của sách
   - Kiến thức hoặc thông tin mà người đọc có thể thu được
   - Đối tượng độc giả phù hợp và lý do nên đọc sách này
   
4. **PHONG CÁCH:**
   - Viết CHI TIẾT, phong phú, đầy đủ thông tin
   - Viết tự nhiên nhưng KHÔNG chung chung
   - Tập trung vào thể loại "{categories}" và mở rộng nội dung
   - Nếu là nhân vật lịch sử: viết chi tiết về cuộc đời, sự nghiệp, đóng góp
   - Nếu là sách chuyên môn: viết về kiến thức, phương pháp, kỹ năng cụ thể
   - Nếu là văn học: viết về chủ đề, nhân vật, ý nghĩa tác phẩm
   - Sử dụng câu văn dài, đoạn văn phát triển tốt

5. **ĐỊNH DẠNG:**
   - Không dùng heading, không dùng markdown, không dùng dấu đầu dòng
   - Viết thành nhiều đoạn văn liền mạch, mỗi đoạn phát triển một ý
   - Bắt đầu: "Cuốn sách..." hoặc "Tác phẩm..."

VÍ DỤ MÔ TẢ DÀI (sách về nhân vật):
"Cuốn sách kể về cuộc đời và sự nghiệp lẫy lừng của [Tên], một nhân vật có vai trò then chốt trong lịch sử Việt Nam. Tác giả {authors}, với kinh nghiệm nghiên cứu sâu rộng trong lĩnh vực lịch sử, đã trình bày một cách sinh động và chi tiết về những sự kiện quan trọng, những quyết định lịch sử và những đóng góp to lớn mà [Tên] đã để lại cho dân tộc. Sách không chỉ tập trung vào các sự kiện chính trị mà còn đi sâu vào cuộc sống cá nhân, tư tưởng và di sản tinh thần của nhân vật. Đây là tài liệu quý giá cho những ai quan tâm đến lịch sử, văn hóa và các giá trị truyền thống Việt Nam."

Hãy viết MÔ TẢ CHI TIẾT (TỐI THIỂU 500 KÝ TỰ) cho cuốn sách "{title}":
"""

                try:
                    response = self.gemini_model.generate_content(prompt)
                    description = response.text.strip()

                    # Kiểm tra độ dài tối thiểu
                    if len(description) < 500:
                        logger.warning(f"Description too short ({len(description)} chars), regenerating...")
                        # Thử lại với prompt yêu cầu rõ ràng hơn
                        retry_prompt = prompt + "\n\n**LƯU Ý QUAN TRỌNG:** Mô tả phải có TỐI THIỂU 500 ký tự. Hãy viết CHI TIẾT hơn, mở rộng các ý, thêm thông tin và phân tích sâu."
                        retry_response = self.gemini_model.generate_content(retry_prompt)
                        description = retry_response.text.strip()

                        # Nếu vẫn quá ngắn, thêm nội dung bổ sung
                        if len(description) < 500:
                            logger.info(f"Description still short ({len(description)} chars), will use fallback")

                    # Giới hạn độ dài tối đa
                    if len(description) > max_length:
                        logger.info(f"Description too long ({len(description)} chars), truncating...")
                        description = description[:max_length].rsplit(' ', 1)[0] + "..."

                    logger.info(f"Generated description: {len(description)} characters")
                    return description

                except Exception as e:
                    logger.error(f"Failed to generate description with Gemini AI: {str(e)}")
                    # Fall back to template-based description

            # Template-based description (fallback)
            logger.info("Generating description using template...")
            return self._generate_template_description(
                book_data, input_title, input_authors, input_category, max_length
            )

        except Exception as e:
            logger.error(f"Error generating description: {str(e)}")
            raise Exception(f"Không thể tạo mô tả: {str(e)}")

    def _generate_template_description(self,
                                       book_data: Optional[Dict[str, Any]],
                                       title: str,
                                       authors: str,
                                       category: str,
                                       max_length: int = 1000) -> str:
        """
        Tạo mô tả sử dụng template khi không có Gemini AI.
        """
        if book_data:
            book_title = book_data.get('title', title)
            book_authors = ', '.join(book_data.get('authors', [authors]))
            book_categories = ', '.join(book_data.get('categories', [category]))
            existing_desc = book_data.get('description', '')
            page_count = book_data.get('pageCount', 'không rõ')
            publisher = book_data.get('publisher', 'không rõ')
            published_date = book_data.get('publishedDate', 'không rõ')
        else:
            book_title = title
            book_authors = authors
            book_categories = category
            existing_desc = ''
            page_count = 'không rõ'
            publisher = 'không rõ'
            published_date = 'không rõ'

        # Template ưu tiên nội dung gốc từ Google Books
        if existing_desc:
            # Nếu có mô tả gốc (thường bằng tiếng Anh), sử dụng nó
            # Lấy tối đa 800 ký tự từ mô tả gốc
            desc_content = existing_desc[:800]

            description = f"""Cuốn sách "{book_title}" của {book_authors} thuộc lĩnh vực {book_categories}.

{desc_content}

Xuất bản bởi {publisher} vào năm {published_date}, cuốn sách này là một tài liệu tham khảo quan trọng trong lĩnh vực {book_categories}. Với {page_count} trang nội dung phong phú, tác phẩm cung cấp những kiến thức chuyên sâu và góc nhìn độc đáo về các chủ đề được đề cập. Cuốn sách phù hợp cho các nhà nghiên cứu, sinh viên và những người làm việc trong lĩnh vực {book_categories}, cũng như bất kỳ ai quan tâm đến việc mở rộng hiểu biết về các khía cạnh liên quan."""
        else:
            # Không có mô tả gốc, dùng template dài hơn
            description = f"""Cuốn sách "{book_title}" của {book_authors} là một tác phẩm quan trọng trong lĩnh vực {book_categories}. Được xuất bản bởi {publisher} vào năm {published_date}, cuốn sách này tập trung vào các chủ đề cốt lõi và những khía cạnh quan trọng nhất trong {book_categories}. Tác giả {book_authors} đã tổng hợp kiến thức chuyên sâu và kinh nghiệm thực tiễn để mang đến cho người đọc một cái nhìn toàn diện và sâu sắc về lĩnh vực này. Cuốn sách không chỉ cung cấp nền tảng lý thuyết vững chắc mà còn đưa ra những ứng dụng thực tế, giúp người đọc có thể áp dụng kiến thức vào công việc và cuộc sống hàng ngày. Đây là tài liệu tham khảo hữu ích và không thể thiếu cho sinh viên, giảng viên, nhà nghiên cứu, chuyên gia và tất cả những ai đam mê và muốn khám phá sâu hơn về {book_categories}."""

        # Giới hạn độ dài tối đa
        if len(description) > max_length:
            # Cắt ngắn tại dấu câu gần nhất
            description = description[:max_length].rsplit('.', 1)[0] + "."

        return description.strip()

    def generate_description(self,
                             title: str,
                             authors: str,
                             category: str) -> Dict[str, Any]:
        """
        Hàm chính để tạo mô tả sách.

        Args:
            title: Tên sách
            authors: Tác giả
            category: Thể loại

        Returns:
            Dictionary chứa kết quả:
            {
                "status": "success" hoặc "error",
                "message": thông báo,
                "data": {
                    "title": tên sách,
                    "authors": tác giả,
                    "category": thể loại,
                    "description": mô tả chi tiết,
                    "description_length": độ dài mô tả,
                    "source": "google_books" hoặc "template",
                    "book_info": thông tin sách từ Google Books (nếu có)
                }
            }
        """
        try:
            logger.info(f"Starting description generation for: {title} by {authors}")

            # Tìm sách trên Google Books
            book_data = self.search_google_books(title, authors, category)

            if not book_data:
                logger.warning("Book not found on Google Books, generating from metadata only")

            # Tạo mô tả chi tiết
            logger.info("Generating description with Gemini AI...")
            description = self.generate_detailed_description(
                book_data, title, authors, category, max_length=1000
            )

            result = {
                "status": "success",
                "message": "Đã tạo mô tả thành công",
                "data": {
                    "title": book_data.get('title', title) if book_data else title,
                    "authors": book_data.get('authors', [authors]) if book_data else [authors],
                    "category": category,
                    "description": description,
                    "description_length": len(description),
                    "source": "google_books" if book_data else "template",
                }
            }

            logger.info(f"Description generated successfully: {len(description)} characters")
            return result

        except Exception as e:
            logger.error(f"Failed to generate description: {str(e)}")
            return {
                "status": "error",
                "message": f"Lỗi khi tạo mô tả: {str(e)}",
                "data": None
            }
