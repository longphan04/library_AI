import csv
import glob
import json
import logging
import os
import re
from datetime import datetime

from config.settings import settings

# --- SETUP LOGGER ---
log_filename = os.path.join(settings.LOG_DIR, "data_processor.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DataProcessor")

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
        if not identifiers:
            return "", ""
        for item in identifiers:
            if item.get('type') == 'ISBN_13':
                return item.get('identifier'), "ISBN_13"
        for item in identifiers:
            if item.get('type') == 'ISBN_10':
                return item.get('identifier'), "ISBN_10"
        first_item = identifiers[0]
        return first_item.get('identifier', ""), first_item.get('type', "UNKNOWN")

    def clean_item(self, raw_item, seen_ids):
        self.stats["total_raw_items"] += 1
        
        book_id = raw_item.get("id")
        info = raw_item.get("volumeInfo", {})
        
        # 1. Lấy dữ liệu thô
        title = info.get("title")
        subtitle = info.get("subtitle", "")
        description = info.get("description", "")
        
        # 2. Xử lý Tác giả (Đưa lên trước để check lỗi font)
        authors_list = info.get("authors", ["Unknown"])
        # Chuyển list thành string: ["Nam Cao", "To Hoai"] -> "Nam Cao, To Hoai"
        authors_str = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)

        # 3. Lấy Identifier
        ident_val, ident_type = self.extract_best_identifier(info.get("industryIdentifiers", []))

        # --- BỘ LỌC CƠ BẢN (Basic Filters) ---
        if not book_id or not title:
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
        if (self.has_font_errors(title) or 
            self.has_font_errors(description) or 
            self.has_font_errors(authors_str)):  # <--- THÊM CHECK TÁC GIẢ TẠI ĐÂY
            
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
        thumbnail = info.get("imageLinks", {}).get("thumbnail", "")
        if thumbnail:
            thumbnail = thumbnail.replace("&zoom=1", "").replace("&edge=curl", "")

        published_date = info.get("publishedDate", "N/A")
        year = published_date[:4] if len(published_date) >= 4 else "N/A"

        categories = info.get("categories", ["General"])
        category_str = categories[0] if categories else "General"

        full_title_text = f"{title} - {subtitle}" if subtitle else title
        
        # Tạo nội dung Rich Text
        rich_text = (
            f"Tiêu đề: {full_title_text}\n"
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
            "title": title,
            "subtitle": subtitle,
            "authors": authors_str,
            "publisher": info.get("publisher", "Unknown"),
            "published_year": year,
            "category": category_str,
            "language": info.get("language", "en"),
            "thumbnail": thumbnail,
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

        for filepath in raw_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    if isinstance(raw_data, list):
                        for item in raw_data:
                            cleaned_book = self.clean_item(item, seen_ids)
                            
                            if cleaned_book:
                                rich_text_content = cleaned_book.pop('rich_text', None)
                                txt_filename = self.save_individual_rich_text(cleaned_book['id'], rich_text_content)
                                cleaned_book['rich_text_file'] = txt_filename
                                
                                all_clean_books.append(cleaned_book)
                                seen_ids.add(cleaned_book['id'])
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