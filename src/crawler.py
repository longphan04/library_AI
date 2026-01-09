import os
import json
import time
import requests
import logging
from datetime import datetime
from config.settings import settings

# logging setup
log_filename = os.path.join(settings.LOG_DIR, "crawler.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GoogleBooksCrawler")

class GoogleBooksCrawler:
    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.base_url = "https://www.googleapis.com/books/v1/volumes"
        
        self.stats = {
            "start_time": datetime.now(),
            "total_collected": 0,
            "requests_made": 0,
            "errors": 0,
            "topics_scanned": []
        }

    def fetch_batch(self, query, start_index=0):
        """
        Gửi request lấy 1 lô sách (tối đa 40 cuốn).
        Xử lý các mã lỗi HTTP thường gặp.
        """
        params = {
            "q": query,
            "startIndex": start_index,
            "maxResults": settings.BATCH_SIZE,
            "key": self.api_key
        }
        
        try:
            self.stats["requests_made"] += 1
            response = requests.get(self.base_url, params=params, timeout=15)
            
            if response.status_code == 200:
                items = response.json().get("items", [])
                if not items:
                    logger.info(f"   -> Empty response (End of list) for '{query}' at index {start_index}.")
                return items
            elif response.status_code == 429:
                logger.warning(f"Quota Exceeded (429). Sleeping for 60s.")
                time.sleep(60)
                return []
            
            elif response.status_code == 403:
                logger.critical("API Permission Error (403).")
                return []
            
            else:
                logger.error(f"API Error {response.status_code}: {response.text[:100]}")
                self.stats["errors"] += 1
                return []
                
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            self.stats["errors"] += 1
            return []

    def save_raw_batch(self, topic, books_data):
        """
        Lưu dữ liệu thô ngay lập tức xuống đĩa cứng để tránh mất mát.
        File name: raw_{topic}_{timestamp}_{count}.json
        """
        if not books_data:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).lower()
        
        filename = f"raw_{safe_topic}_{timestamp}_{len(books_data)}.json"
        filepath = os.path.join(settings.DATA_RAW_DIR, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(books_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved batch: {len(books_data)} books -> {filename}")
        except Exception as e:
            logger.error(f"Failed to write file {filename}: {e}")
            self.stats["errors"] += 1

    def generate_report(self):
        """
        Tạo file báo cáo tổng kết sau khi chạy xong.
        """
        end_time = datetime.now()
        duration = end_time - self.stats["start_time"]
        report_filename = f"crawl_report_{end_time.strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(settings.REPORT_DIR, report_filename)

        content = (
            f"Date         : {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Duration     : {duration}\n"
            f"Status       : COMPLETED\n"
            f"----------------------------------------\n"
            f"Total Books  : {self.stats['total_collected']}\n"
            f"API Requests : {self.stats['requests_made']}\n"
            f"Errors       : {self.stats['errors']}\n"
            f"Topics       : {', '.join(self.stats['topics_scanned'])}\n"
            f"========================================\n"
        )

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Report generated: {report_path}")
        except Exception as e:
            logger.error(f"Could not save report: {e}")

    def run(self):
        logger.info(f"STARTING CRAWLER JOB")
        logger.info(f"Data Folder: {settings.DATA_RAW_DIR}")
        logger.info(f"Topics to scan: {settings.CRAWL_TOPICS}")
        
        for topic in settings.CRAWL_TOPICS:
            # Check giới hạn ngày (Limit per day)
            if self.stats["total_collected"] >= settings.LIMIT_PER_DAY:
                logger.warning(f"Daily limit reached ({settings.LIMIT_PER_DAY}). Stopping.")
                break

            logger.info(f"Scanning Topic: '{topic}'...")
            self.stats["topics_scanned"].append(topic)
            
            for start_index in range(0, settings.BOOKS_PER_TOPIC, settings.BATCH_SIZE):
                # 1. Fetch Data
                batch = self.fetch_batch(topic, start_index)
                if not batch:
                    # Nếu hết sách hoặc lỗi thì dừng quét topic này, chuyển topic khác
                    break
                # 2. Save Data
                self.save_raw_batch(topic, batch)
                # 3. Update Stats
                count = len(batch)
                self.stats["total_collected"] += count
                # 4. Rate Limiting
                time.sleep(2)
            logger.info(f"Finished topic '{topic}'.")
        # Kết thúc session
        self.generate_report()
        logger.info(f"ALL DONE. Total books collected: {self.stats['total_collected']}")
if __name__ == "__main__":
    crawler = GoogleBooksCrawler()
    crawler.run()