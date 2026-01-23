# CATEGORIES_MAPPING - Aligned with migration.sql
# 
# Migration has 20 Vietnamese categories.
# This mapping converts English Google Books categories → Vietnamese migration categories

CATEGORIES_MAPPING = {
    # === Technology (Công nghệ thông tin - An toàn thông tin) ===
    "Technology": "Công nghệ thông tin",
    "Information Technology": "Công nghệ thông tin",
    "Computer Science": "Khoa học máy tính",
    "Computers": "Khoa học máy tính",
    "Programming": "Lập trình",
    "Software": "Lập trình",
    "Coding": "Lập trình",
    "Artificial Intelligence": "Trí tuệ nhân tạo",
    "AI": "Trí tuệ nhân tạo",
    "Machine Learning": "Trí tuệ nhân tạo",
    "Deep Learning": "Trí tuệ nhân tạo",
    "Data Science": "Khoa học dữ liệu",
    "Big Data": "Khoa học dữ liệu",
    "Data Analysis": "Khoa học dữ liệu",
    "Network": "Mạng máy tính",
    "Networking": "Mạng máy tính",
    "Security": "An toàn thông tin",
    "Cybersecurity": "An toàn thông tin",
    "Information Security": "An toàn thông tin",
    
    # === Science (Toán học - Sinh học) ===
    "Mathematics": "Toán học",
    "Math": "Toán học",
    "Physics": "Vật lý",
    "Chemistry": "Hóa học",
    "Biology": "Sinh học",
    "Life Sciences": "Sinh học",
    
    # === Business & Economics (Kinh tế - Tài chính) ===
    "Economics": "Kinh tế",
    "Business": "Quản trị kinh doanh",
    "Management": "Quản trị kinh doanh",
    "Entrepreneurship": "Quản trị kinh doanh",
    "Marketing": "Marketing",
    "Finance": "Tài chính - Ngân hàng",
    "Banking": "Tài chính - Ngân hàng",
    "Accounting": "Tài chính - Ngân hàng",
    
    # === Skills & Psychology (Kỹ năng mềm - Tâm lý học) ===
    "Self-help": "Kỹ năng mềm",
    "Self-improvement": "Kỹ năng mềm",
    "Personal Development": "Kỹ năng mềm",
    "Leadership": "Kỹ năng mềm",
    "Communication": "Kỹ năng mềm",
    "Psychology": "Tâm lý học",
    "Mental Health": "Tâm lý học",
    
    # === Humanities (Văn học - Ngoại ngữ) ===
    "Literature": "Văn học",
    "Fiction": "Văn học",
    "Novel": "Văn học",
    "Poetry": "Văn học",
    "Drama": "Văn học",
    "History": "Lịch sử",
    "Historical": "Lịch sử",
    "Language": "Ngoại ngữ",
    "Foreign Language": "Ngoại ngữ",
    "English": "Ngoại ngữ",
    "Linguistics": "Ngoại ngữ",
    
    # === Default ===
    "General": "Văn học"  # Default to literature
}
