import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # đường dẫn
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    REPORT_DIR = os.path.join(BASE_DIR, "reports")
    DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
    VECTOR_DB_DIR = os.path.join(BASE_DIR, "data", "vector_db")
    DATA_RICH_TEXT_DIR = os.path.join(BASE_DIR, "data", "rich_text")

    # API Keys
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # Cấu hình Crawler
    BATCH_SIZE = 40
    BOOKS_PER_TOPIC = 1000
    LIMIT_PER_MINUTE = 100
    LIMIT_PER_DAY = 22000

    # TOPICS để crawl
    CRAWL_TOPICS = [
    "Python Programming", "Artificial Intelligence", "Machine Learning", "Data Science", "Software Architecture", "Web Development", "Lịch sử Việt Nam",
    "Kinh tế học", "Tâm lý học", "Tiểu thuyết trinh thám", "Khoa học vũ trụ", "Lịch sử thế giới", "Nhân học", "Giải toán", "Nghệ thuật hội họa",
    "Nhiếp ảnh", "Quản trị kinh doanh", "Du lịch", "Tâm linh và Phật giáo", "Sức khỏe và Dinh dưỡng", "Văn học cổ điển", "Khám phá các nền văn hóa",
    "Khoa học môi trường", "Lập trình di động", "Blockchain và Cryptocurrency", "An ninh mạng", "Kinh doanh quốc tế", "Tự lực và phát triển bản thân",
    "Nhạc lý và âm nhạc cổ điển", "Lịch sử nghệ thuật", "Lập trình web front-end", "Lập trình web back-end"
]
    
    # MODEL EMBEDDING
    EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"
    VECTOR_DIMENSION = 768

    @staticmethod
    def ensure_directories():
        os.makedirs(Settings.DATA_RAW_DIR, exist_ok=True)
        os.makedirs(Settings.LOG_DIR, exist_ok=True)
        os.makedirs(Settings.REPORT_DIR, exist_ok=True)
        os.makedirs(Settings.DATA_PROCESSED_DIR, exist_ok=True)
        os.makedirs(Settings.VECTOR_DB_DIR, exist_ok=True)
        os.makedirs(Settings.DATA_RICH_TEXT_DIR, exist_ok=True)

settings = Settings()
settings.ensure_directories()