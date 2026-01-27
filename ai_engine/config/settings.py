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
    BOOKS_PER_TOPIC = 20  # Reduced for <500 total target
    TOTAL_TARGET_BOOKS = 1000
    LIMIT_PER_MINUTE = 100
    LIMIT_PER_DAY = 10000  # Match target

    # TOPICS để crawl - Vietnamese Focus (Aligned with migration.sql categories)
    CRAWL_TOPICS = [
        # === Công nghệ thông tin / Lập trình ===
        "Lập trình Python",
        "Khoa học máy tính",
        "Công nghệ thông tin",
        
        # === Trí tuệ nhân tạo / Khoa học dữ liệu ===
        "Trí tuệ nhân tạo",
        "Machine Learning",
        "Khoa học dữ liệu",
        
        # === An toàn thông tin / Mạng ===
        "An toàn thông tin",
        "Mạng máy tính",
        
        # === Toán - Lý - Hóa - Sinh ===
        "Toán học",
        "Vật lý",
        
        # === Kinh tế / Kinh doanh ===
        "Kinh tế học",
        "Quản trị kinh doanh",
        "Marketing",
        
        # === Kỹ năng / Tâm lý ===
        "Kỹ năng mềm",
        "Tâm lý học",
        "Phát triển bản thân",
        
        # === Văn học / Lịch sử Việt Nam ===
        "Văn học Việt Nam",
        "Nguyễn Nhật Ánh",
        "Lịch sử Việt Nam",
        
        # === English (limited for quality technical books) ===
        "Python Programming",
        "Artificial Intelligence"
    ]
    
    # MODEL EMBEDDING
    EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"
    VECTOR_DIMENSION = 786

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3307))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_NAME = os.getenv("DB_NAME", "library_db")

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