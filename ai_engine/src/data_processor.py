import json
import csv
import os
import glob
import logging
import re
from datetime import datetime
from config.settings import settings
from config.categories import CATEGORIES_MAPPING
from config.logging_config import get_logger

# Get logger (config done in main.py)
logger = get_logger("DataProcessor")

class DataProcessor:
    def __init__(self):
        self.raw_dir = settings.DATA_RAW_DIR
        self.processed_dir = settings.DATA_PROCESSED_DIR
        self.report_dir = settings.REPORT_DIR
        self.rich_text_dir = settings.DATA_RICH_TEXT_DIR
        
        # Thống kê (Thêm dropped_font_error)
        self.stats = {
            "start_time": datetime.now(),
            "total_raw_items": 0,
            "success": 0,
            "dropped_duplicate": 0,
            "dropped_no_desc": 0,
            "dropped_short_desc": 0,
            "dropped_bad_data": 0,
            "dropped_no_id": 0,
            "dropped_font_error": 0  # <--- MỚI: Đếm số lượng lỗi font
        }

    # --- MỚI: Hàm kiểm tra lỗi font ---
    def has_font_errors(self, text):
        """
        Trả về True nếu phát hiện lỗi font/encoding nghiêm trọng
        """
        if not text:
            return False
            
        # 1. Ký tự thay thế  (Replacement Character - U+FFFD)
        # Đây là dấu hiệu rõ nhất của việc mất dữ liệu
        if "\ufffd" in text:
            return True
        
        if "¿" in text:
            return True
        
        # 2. Kiểm tra chuỗi Mojibake phổ biến (Tiếng Việt bị lỗi sang Latin-1)
        # Ví dụ: "Nguyễn" -> "NguyÃªn" (Chữ Ã xuất hiện kèm ký tự lạ)
        # Regex này tìm các cặp ký tự lạ thường thấy khi lỗi encoding
        # Lưu ý: Cẩn thận vì chữ Ã đứng một mình có thể đúng, nhưng Ã©, Ãª, Ã± thường là lỗi
        mojibake_pattern = r'Ã[©ª«®±µ»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ]'
        if re.search(mojibake_pattern, text):
            return True

        # 3. Kiểm tra nếu chứa quá nhiều ký tự vô nghĩa liên tiếp (Garbage)
        # Ví dụ: â˜…â˜… (Lỗi icon)
        if "â˜" in text or "ðŸ" in text:
            return True
            
        return False

    def extract_best_identifier(self, identifiers):
        """
        Parse identifier với priority:
        1. ISBN_13 (chuẩn quốc tế)
        2. ISBN_10
        3. OTHER types (parse PREFIX:NUMBER → lưu NUMBER, type=PREFIX)
        
        Examples:
          "OCLC:951285305" → identifier="951285305", type="OCLC"
          "HARVARD:32044088773080" → identifier="32044088773080", type="HARVARD"
          "978-0-13-468599-1" → identifier="978-0-13-468599-1", type="ISBN_13"
        """
        if not identifiers:
            return "", ""
        
        # Priority 1: ISBN_13
        for item in identifiers:
            if item.get('type') == 'ISBN_13':
                isbn = item.get('identifier', '')
                return isbn, "ISBN_13"
        
        # Priority 2: ISBN_10
        for item in identifiers:
            if item.get('type') == 'ISBN_10':
                isbn = item.get('identifier', '')
                return isbn, "ISBN_10"
        
        # Priority 3: OTHER types - parse PREFIX:NUMBER format
        for item in identifiers:
            raw_id = item.get('identifier', '')
            
            # Check if format is "PREFIX:NUMBER"
            if ':' in raw_id:
                parts = raw_id.split(':', 1)
                prefix = parts[0].strip().upper()  # OCLC, HARVARD, etc.
                number = parts[1].strip()          # 951285305
                return number, prefix
        
        # Fallback: return first identifier as-is
        # Fallback: return first identifier as-is
        first_item = identifiers[0]
        return first_item.get('identifier', ""), first_item.get('type', "UNKNOWN")

    def clean_text(self, text):
        """
        Loại bỏ ký tự đặc biệt không mong muốn.
        
        Examples:
          ""Python"" → "Python"
          "Data Science" → "Data Science"
        """
        if not text:
            return text
        
        # Loại bỏ các loại dấu ngoặc kép khác nhau
        replacements = {
            '"': '',  # Left double quotation mark (U+201C)
            '"': '',  # Right double quotation mark (U+201D)
            '"': '',  # Standard ASCII quote
            '„': '',  # Double low-9 quotation mark
            '\ufffd': '',  # Replacement character
            '�': ''   # Also replacement character
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Normalize whitespace (multiple spaces → single space)
        text = ' '.join(text.split())
        
        return text.strip()

    def build_full_title(self, title, subtitle):
        """
        Kết hợp title và subtitle để tránh trùng lặp.
        
        Examples:
          title="Python", subtitle="A Guide" → "Python - A Guide"
          title="Python", subtitle="" → "Python"
          title="Python", subtitle=None → "Python"
        """
        if not title:
            return "Unknown"
        
        # Clean title
        title = self.clean_text(title)
        
        # Nếu có subtitle, kết hợp lại
        if subtitle and subtitle.strip():
            subtitle = self.clean_text(subtitle)
            return f"{title} - {subtitle}"
        
        return title

    def clean_item(self, raw_item, seen_ids):
        self.stats["total_raw_items"] += 1
        
        book_id = raw_item.get("id")
        info = raw_item.get("volumeInfo", {})
        
        # 1. Lấy dữ liệu thô
        title_raw = info.get("title")
        subtitle_raw = info.get("subtitle", "")
        description = info.get("description", "")
        
        # 2. Build full title (kết hợp title + subtitle, clean special chars)
        full_title = self.build_full_title(title_raw, subtitle_raw)
        
        # 3. Xử lý Tác giả
        authors_list = info.get("authors", ["Unknown"])
        # Chuyển list thành string: ["Nam Cao", "To Hoai"] -> "Nam Cao, To Hoai"
        authors_str = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)
        # Clean special chars trong authors
        authors_str = self.clean_text(authors_str)

        # 4. Lấy Identifier (với smart parsing)
        ident_val, ident_type = self.extract_best_identifier(info.get("industryIdentifiers", []))

        # --- BỘ LỌC CƠ BẢN (Basic Filters) ---
        if not book_id or not title_raw:
            self.stats["dropped_bad_data"] += 1
            return None
        
        if book_id in seen_ids:
            self.stats["dropped_duplicate"] += 1
            return None

        if not ident_val:
            self.stats["dropped_no_id"] += 1
            return None

        # --- KIỂM TRA LỖI FONT (Encoding Check) ---
        # Kiểm tra cả 3 trường: Tiêu đề, Mô tả, Tác giả
        if (self.has_font_errors(full_title) or 
            self.has_font_errors(description) or 
            self.has_font_errors(authors_str)):
            
            self.stats["dropped_font_error"] += 1
            return None
        # ------------------------------------------

        if not description:
            self.stats["dropped_no_desc"] += 1
            return None

        if len(description) < 20:
            self.stats["dropped_short_desc"] += 1
            return None

        # --- LÀM SẠCH DỮ LIỆU KHÁC ---
        # Lưu FULL image links từ Google Books (không clean URL)
        # Để sau này có module download images, sẽ xử lý riêng
        image_links = info.get("imageLinks", {})
        cover_url = image_links.get("thumbnail", "")  # Primary image (zoom=1)
        small_thumbnail = image_links.get("smallThumbnail", "")  # Smaller version (zoom=5)
        
        # NOTE: Giữ nguyên full URL với &zoom=1, &edge=curl
        # Không remove parameters để đảm bảo link hoạt động lâu dài
        # Module tải ảnh về sau sẽ xử lý việc tải và lưu local

        published_date = info.get("publishedDate", "N/A")
        year = published_date[:4] if len(published_date) >= 4 else "N/A"

        # Lấy TẤT CẢ categories và xử lý & để split
        categories = info.get("categories", ["General"])
        if isinstance(categories, list) and categories:
            # Process each category
            processed_cats = []
            for cat in categories:
                if not cat:
                    continue
                # Split by & to separate combined categories
                # "Business & Economics" → ["Business", "Economics"]
                if '&' in cat:
                    parts = [p.strip() for p in cat.split('&')]
                    processed_cats.extend(parts)
                else:
                    processed_cats.append(cat.strip())
            
            # Convert to Vietnamese using CATEGORIES_MAPPING
            vietnamese_cats = []
            for cat in processed_cats:
                vietnamese = CATEGORIES_MAPPING.get(cat, "Khác")  # Default to "Khác" if not found
                vietnamese_cats.append(vietnamese)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_cats = []
            for cat in vietnamese_cats:
                if cat not in seen:
                    seen.add(cat)
                    unique_cats.append(cat)
            
            # Remove "Khác" if there are other categories
            if len(unique_cats) > 1 and "Khác" in unique_cats:
                unique_cats = [c for c in unique_cats if c != "Khác"]
            
            # Join with comma: ["Computers", "Programming"] -> "Khoa học máy tính, Lập trình"
            category_str = ", ".join(unique_cats) if unique_cats else "Khác"
        else:
            category_str = "Khác"
        
        
        publisher = self.clean_text(info.get("publisher", "Unknown"))

        # Tạo nội dung Rich Text với full_title
        rich_text = (
            f"Tiêu đề: {full_title}\n"
            f"Mã định danh: {ident_val} ({ident_type})\n"
            f"Tác giả: {authors_str}\n"
            f"Thể loại: {category_str}\n"
            f"Năm xuất bản: {year}\n"
            f"Tóm tắt nội dung: {description}"
        )

        clean_data = {
            "id": book_id,
            "identifier": ident_val,    
            "type": ident_type,         
            "title": full_title,  # Sử dụng full_title (đã clean + merge subtitle)
            "subtitle": subtitle_raw,  # Vẫn giữ subtitle gốc nếu cần
            "authors": authors_str,
            "publisher": publisher,
            "publish_year": year,
            "category": category_str,
            "language": info.get("language", "en"),
            "cover_url": cover_url,  # Primary thumbnail (full URL)
            "small_thumbnail": small_thumbnail,  # Smaller thumbnail (full URL)
            "google_link": info.get("infoLink", ""),
            "description": description, 
            "rich_text": rich_text 
        }

        self.stats["success"] += 1
        return clean_data

    def save_individual_rich_text(self, book_id, content):
        if not content:
            return None
        safe_filename = re.sub(r'[\\/*?:"<>|]', "_", str(book_id)) + ".txt"
        file_path = os.path.join(self.rich_text_dir, safe_filename)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return safe_filename 
        except Exception as e:
            logger.error(f"Error saving rich text for book {book_id}: {e}")
            return None

    def save_to_json(self, data, filename):
        path = os.path.join(self.processed_dir, filename)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON Saved: {path}")
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")

    def save_to_csv(self, data, filename):
        if not data: return
        path = os.path.join(self.processed_dir, filename)
        keys = data[0].keys()
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
            logger.info(f"CSV Saved: {path}")
        except Exception as e:
            logger.error(f"Error saving CSV: {e}")

    def generate_report_content(self):
        duration = datetime.now() - self.stats["start_time"]
        content = (
            f"========================================\n"
            f"          DATA PROCESSING REPORT          \n"
            f"========================================\n"
            f"Date         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Duration     : {duration}\n"
            f"Status       : COMPLETED\n"
            f"----------------------------------------\n"
            f"TOTAL RAW INPUT     : {self.stats['total_raw_items']:>5}\n"
            f"VALID BOOKS (KEPT)  : {self.stats['success']:>5}\n"
            f"----------------------------------------\n"
            f"DROPPED ITEMS DETAILS:\n"
            f"Duplicate ID        : {self.stats['dropped_duplicate']:>5}\n"
            f"Font/Encoding Err   : {self.stats['dropped_font_error']:>5}\n"
            f"No Identifier       : {self.stats['dropped_no_id']:>5}\n"
            f"No Description      : {self.stats['dropped_no_desc']:>5}\n"
            f"Short Description   : {self.stats['dropped_short_desc']:>5}\n"
            f"Bad Data (ID/Title) : {self.stats['dropped_bad_data']:>5}\n"
            f"========================================\n"
        )
        return content

    def save_report_to_file(self):
        report_content = self.generate_report_content()
        print("\n" + report_content)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"processor_report_{timestamp}.txt"
        filepath = os.path.join(self.report_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            logger.info(f"Report saved to: {filepath}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")

    def run(self):
        logger.info("STARTING DATA PROCESSOR...")
        
        raw_files = glob.glob(os.path.join(self.raw_dir, "*.json"))
        if not raw_files:
            logger.warning("No raw files found. Please run 'crawl' first!")
            return

        all_clean_books = [] 
        seen_ids = set()

        logger.info(f"Found {len(raw_files)} raw files. Processing...")

        for idx, filepath in enumerate(raw_files, 1):
            try:
                logger.info(f"[{idx}/{len(raw_files)}] Processing: {os.path.basename(filepath)}")
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    if isinstance(raw_data, list):
                        processed_count = 0
                        for item in raw_data:
                            cleaned_book = self.clean_item(item, seen_ids)
                            
                            if cleaned_book:
                                rich_text_content = cleaned_book.pop('rich_text', None)
                                txt_filename = self.save_individual_rich_text(cleaned_book['id'], rich_text_content)
                                cleaned_book['rich_text_file'] = txt_filename
                                
                                all_clean_books.append(cleaned_book)
                                seen_ids.add(cleaned_book['id'])
                                processed_count += 1
                        
                        logger.info(f"  ✓ Processed {processed_count} valid books from {os.path.basename(filepath)}")
            except Exception as e:
                logger.error(f"Error processing file {filepath}: {e}")

        self.save_report_to_file()

        if all_clean_books:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.save_to_json(all_clean_books, f"clean_books_{timestamp}.json")
            self.save_to_csv(all_clean_books, f"clean_books_{timestamp}.csv")
            logger.info(f"Processed {len(all_clean_books)} books successfully.")
        else:
            logger.warning("No valid books found.")

def run_processor():
    processor = DataProcessor()
    processor.run()

if __name__ == "__main__":
    run_processor()