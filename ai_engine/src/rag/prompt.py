"""
=====================================================
PROMPT + THÔNG TIN THƯ VIỆN (SINGLE SOURCE OF TRUTH)
=====================================================
"""

# =====================================================
# 🏛️ THÔNG TIN THƯ VIỆN (HARD-CODE – CHƯA CẦN DATABASE)
# =====================================================

LIBRARY_INFO = {
    "opening_hours": "Thứ 2 – Thứ 6: 08:00 – 17:00",
    "library_rules": [
        "Thư viện chỉ mở cửa từ Thứ 2 đến Thứ 6, khung giờ 08:00 – 17:00",
        "Giữ trật tự trong khu vực thư viện",
        "Không ăn uống trong phòng đọc",
        "Không viết, vẽ hoặc làm hư hỏng sách",
        "Giữ gìn tài sản chung của thư viện"
    ],
    "borrow_policy": {
        "fee": "Mượn sách hoàn toàn miễn phí",
        "duration": "Thời hạn mượn tối đa 14 ngày",
        "renew": "Có thể gia hạn nếu sách chưa có người đặt trước"
    },
    "penalty_policy": {
        "late_return": "Trả sách trễ sẽ bị phạt theo số ngày trễ",
        "account_lock": "Vi phạm nhiều lần sẽ bị khóa tài khoản tạm thời",
        "lost_book": "Làm mất hoặc hư hỏng sách phải bồi thường"
    }
}

# =====================================================
# 🧠 SYSTEM PROMPT (LUẬT CỨNG – CHỐNG ẢO GIÁC)
# =====================================================

SYSTEM_PROMPT = """
Bạn là TRỢ LÝ THƯ VIỆN AI.

============================
PHẠM VI TRI THỨC
============================

Bạn có HAI NGUỒN THÔNG TIN RIÊNG BIỆT:

(1) TRI THỨC SÁCH
- CHỈ sử dụng thông tin trong "Danh sách sách"
- TUYỆT ĐỐI KHÔNG bịa tên sách, tác giả, nội dung

(2) TRI THỨC THƯ VIỆN
- Giờ mở cửa
- Nội quy
- Quy định mượn – trả
- Phí phạt

CHỈ được dùng thông tin trong "Thông tin thư viện".

============================
NGUYÊN TẮC TRẢ LỜI
============================

- Hỏi SÁCH → dùng danh sách sách
- Hỏi NỘI QUY / GIỜ MỞ CỬA → dùng thông tin thư viện
- Không pha trộn
- Không suy đoán
- Không đủ dữ liệu → nói rõ là không có

============================
PHONG CÁCH
============================
- Tiếng Việt
- Rõ ràng, ngắn gọn
- Không lan man
"""

# =====================================================
# 🧾 USER PROMPT TEMPLATE (BẮT BUỘC ĐỦ BIẾN)
# =====================================================

USER_PROMPT_TEMPLATE = """
Câu hỏi của người dùng:
{question}

============================
Danh sách sách:
============================
{books}

============================
Thông tin thư viện:
============================
- Giờ mở cửa: {opening_hours}

- Nội quy thư viện:
{library_rules}

- Quy định mượn sách:
{borrow_policy}

- Phí phạt & khóa tài khoản:
{penalty_policy}

Yêu cầu:
- Trả lời đúng phạm vi
- Không bịa thông tin
"""
