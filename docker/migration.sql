DROP DATABASE IF EXISTS library_db;
CREATE DATABASE library_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE library_db;

-- =========================================================
-- (Tuỳ chọn) STRICT MODE
-- Mục đích: giúp MySQL báo lỗi khi dữ liệu sai kiểu/overflow thay vì tự “ép” âm thầm.
-- Bạn có thể bỏ dòng này nếu không muốn.
-- =========================================================
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';

-- =========================================================
-- 1) AUTH & PHÂN QUYỀN (RBAC)
-- =========================================================

-- =========================================================
-- Bảng Users
-- Dùng để: lưu tài khoản đăng nhập (email/password), trạng thái tài khoản, phục vụ JWT auth.
-- Không để thông tin cá nhân ở đây (để ở profiles).
-- =========================================================
CREATE TABLE users (
    user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    status ENUM('PENDING','ACTIVE','BANNED') NOT NULL DEFAULT 'PENDING',
    last_login_at DATETIME DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Profiles
-- Dùng để: lưu hồ sơ người dùng (tên, sđt, avatar, địa chỉ, ngày sinh). 1-1 với users.
-- =========================================================
CREATE TABLE profiles (
    profile_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    full_name VARCHAR(120) NOT NULL,
    phone VARCHAR(30) UNIQUE DEFAULT NULL,
    avatar_url VARCHAR(255) DEFAULT NULL,
    address VARCHAR(255) DEFAULT NULL,
    dob DATE DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_profiles_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Roles
-- Dùng để: danh sách vai trò hệ thống (ADMIN/STAFF/MEMBER).
-- =========================================================
CREATE TABLE roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    name ENUM('ADMIN','STAFF','MEMBER') NOT NULL UNIQUE,
    description VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- =========================================================
-- Bảng User_Roles
-- Dùng để: gán vai trò cho user (N-N). 1 user có thể có nhiều role.
-- =========================================================
CREATE TABLE user_roles (
    user_id BIGINT NOT NULL,
    role_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id, role_id),

    CONSTRAINT fk_user_roles_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role
        FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Auth_Tokens
-- Dùng để: xác nhận email (WEB link / APP OTP), quên mật khẩu qua email.
-- Lưu token dạng hash + hạn dùng + trạng thái đã dùng.
-- =========================================================
CREATE TABLE auth_tokens (
    token_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    -- VERIFY_EMAIL: web click link
    -- VERIFY_EMAIL_OTP: mobile app nhập OTP 6 số
    -- RESET_PASSWORD: reset password
    purpose ENUM('VERIFY_EMAIL','VERIFY_EMAIL_OTP','RESET_PASSWORD') NOT NULL DEFAULT 'RESET_PASSWORD',
    token_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME DEFAULT NULL,
    -- Chỉ dùng cho OTP (VERIFY_EMAIL_OTP): đếm số lần nhập sai để giới hạn brute-force
    otp_fail_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_auth_token_hash (token_hash),
    INDEX idx_auth_user_purpose (user_id, purpose),
    INDEX idx_auth_expires (expires_at),

    CONSTRAINT fk_auth_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Refresh_Tokens (tuỳ chọn)
-- Dùng để: refresh JWT, quản lý đăng nhập nhiều thiết bị, revoke từng phiên (logout thiết bị).
-- Nếu bạn không dùng refresh token thì có thể bỏ cả bảng này.
-- =========================================================
CREATE TABLE refresh_tokens (
    rt_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    revoked_at DATETIME DEFAULT NULL,
    user_agent VARCHAR(255) DEFAULT NULL,
    ip_address VARCHAR(64) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_rt_user (user_id),
    INDEX idx_rt_expires (expires_at),

    CONSTRAINT fk_rt_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =========================================================
-- 3) BOOK MANAGEMENT & CATALOG
-- =========================================================

-- =========================================================
-- Bảng Categories
-- Dùng để: danh mục/thể loại sách.
-- =========================================================
CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    image VARCHAR(255),  -- hình đại diện danh mục (tuỳ chọn)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_categories_name (name)
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Authors
-- Dùng để: lưu tác giả, hỗ trợ filter/search theo tác giả.
-- =========================================================
CREATE TABLE authors (
    author_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    bio TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_author_name (name)
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Publishers
-- Dùng để: chuẩn hoá nhà xuất bản (không lưu text rời trong books).
-- =========================================================
CREATE TABLE publishers (
    publisher_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Shelves
-- Dùng để: vị trí vật lý/kệ sách trong thư viện (A1-03...).
-- =========================================================
CREATE TABLE shelves (
    shelf_id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(120) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- =========================================================
-- Bảng Books (đầu sách)
-- Dùng để: thông tin sách cho catalog (identifier, title, cover, category...), KHÔNG phải từng cuốn.
-- Có cache total/available để dashboard nhanh (tuỳ bạn dùng hay bỏ).
-- =========================================================
CREATE TABLE books (
    book_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    identifier VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    publish_year INT DEFAULT NULL,
    language VARCHAR(50) DEFAULT NULL,

    cover_url VARCHAR(255) DEFAULT NULL,
    publisher_id INT DEFAULT NULL,
    shelf_id INT NOT NULL,

    status ENUM('ACTIVE','ARCHIVED') NOT NULL DEFAULT 'ACTIVE',

    -- Ai tạo/sửa (tuỳ chọn)
    created_by BIGINT DEFAULT NULL,
    updated_by BIGINT DEFAULT NULL,

    -- Cache số lượng (tuỳ chọn)
    total_copies INT NOT NULL DEFAULT 0,
    available_copies INT NOT NULL DEFAULT 0,
    total_borrow_count INT NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_books_title (title),
    INDEX idx_books_publisher (publisher_id),
    INDEX idx_books_year (publish_year),
    INDEX idx_books_shelf (shelf_id),
    UNIQUE KEY uq_books_identifier (identifier),

    CONSTRAINT fk_books_publisher
        FOREIGN KEY (publisher_id) REFERENCES publishers(publisher_id) ON DELETE SET NULL,
    CONSTRAINT fk_books_shelf
        FOREIGN KEY (shelf_id) REFERENCES shelves(shelf_id) ON DELETE RESTRICT,
    CONSTRAINT fk_books_created_by
        FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_books_updated_by
        FOREIGN KEY (updated_by) REFERENCES users(user_id) ON DELETE SET NULL,

    CONSTRAINT chk_publish_year CHECK (publish_year IS NULL OR (publish_year >= 0 AND publish_year <= 2100)),
    CONSTRAINT chk_book_copies_nonneg CHECK (total_copies >= 0 AND available_copies >= 0)
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Book_Categories (bảng nối N-N)
-- Dùng để: gán nhiều category cho 1 book, và 1 category chứa nhiều book.
-- =========================================================
CREATE TABLE book_categories (
    book_id BIGINT NOT NULL,
    category_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (book_id, category_id),

    INDEX idx_bc_category (category_id, book_id),

    CONSTRAINT fk_bc_book
        FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE,
    CONSTRAINT fk_bc_category
        FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Book_Authors (N-N)
-- Dùng để: 1 sách nhiều tác giả, 1 tác giả nhiều sách.
-- =========================================================
CREATE TABLE book_authors (
    book_id BIGINT NOT NULL,
    author_id BIGINT NOT NULL,

    PRIMARY KEY (book_id, author_id),
    INDEX idx_ba_author (author_id, book_id),

    CONSTRAINT fk_ba_book
        FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE,
    CONSTRAINT fk_ba_author
        FOREIGN KEY (author_id) REFERENCES authors(author_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Book_Copies (từng cuốn)
-- Dùng để: quản lý từng cuốn sách vật lý (barcode), phục vụ mượn/trả từng cuốn.
-- status: AVAILABLE/BORROWED/LOST/DAMAGED/REMOVED
-- =========================================================
CREATE TABLE book_copies (
    copy_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    barcode VARCHAR(64) NOT NULL UNIQUE,

    status ENUM('AVAILABLE','HELD','BORROWED','REMOVED') NOT NULL DEFAULT 'AVAILABLE',

    acquired_at DATETIME DEFAULT NULL,
    note VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_copies_book (book_id),
    INDEX idx_copies_status (status),

    CONSTRAINT fk_copies_book
        FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Borrow_Cart (giỏ mượn tạm)
-- Dùng để: member add sách vào giỏ trước khi tạo phiếu mượn.
-- Mỗi mục trong giỏ tương ứng 1 cuốn (copy).
-- =========================================================
CREATE TABLE book_holds (
  hold_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  member_id BIGINT NOT NULL,
  copy_id BIGINT NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  -- 1 member không add trùng 1 cuốn
  UNIQUE KEY uq_member_copy (member_id, copy_id),

  -- 1 cuốn không được nằm trong giỏ của 2 người cùng lúc
  UNIQUE KEY uq_copy (copy_id),

  INDEX idx_cart_member (member_id),
  INDEX idx_cart_expires (expires_at),

  CONSTRAINT fk_cart_member
    FOREIGN KEY (member_id) REFERENCES users(user_id) ON DELETE RESTRICT,
  CONSTRAINT fk_cart_copy
    FOREIGN KEY (copy_id) REFERENCES book_copies(copy_id) ON DELETE RESTRICT
) ENGINE=InnoDB;


-- =========================================================
-- 4) BORROW TICKET / RETURN
-- =========================================================

-- =========================================================
-- Bảng Borrow_Tickets (phiếu mượn)
-- Dùng để: staff tạo phiếu mượn cho member, chứa nhiều dòng borrow_items.
-- =========================================================
CREATE TABLE borrow_tickets (
  ticket_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ticket_code VARCHAR(30) NOT NULL UNIQUE,

  member_id BIGINT NOT NULL,

  status ENUM('PENDING','APPROVED','PICKED_UP','RETURNED','CANCELLED') NOT NULL DEFAULT 'PENDING',

  requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  approved_at DATETIME NULL,   -- duyệt phiếu (thời gian)
  approved_by BIGINT NULL,     -- duyệt phiếu (ai)

  pickup_expires_at DATETIME NULL,   -- approved + 1 day

  picked_up_at DATETIME NULL,   -- lấy sách (thời gian)
  picked_up_by BIGINT NULL,     -- lấy sách (ai duyệt)

  due_date DATETIME NULL,            -- picked_up + 10 days

  renew_count TINYINT NOT NULL DEFAULT 0,  -- số lần gia hạn (chỉ 1 lần)

  overdue_notified BOOLEAN NOT NULL DEFAULT FALSE,  
  -- đánh dấu ĐÃ gửi thông báo quá hạn hay CHƯA
  -- dùng cho cron, tránh gửi thông báo BORROW_OVERDUE nhiều lần

  returned_at DATETIME NULL,     -- thời điểm trả sách (khi chuyển sang RETURNED)
  cancelled_at DATETIME NULL,    -- thời điểm hủy phiếu (khi chuyển sang CANCELLED)

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX idx_ticket_member (member_id),
  INDEX idx_ticket_status (status),
  INDEX idx_ticket_pickup_exp (pickup_expires_at),
  INDEX idx_ticket_due (due_date),

  CONSTRAINT fk_ticket_member
    FOREIGN KEY (member_id) REFERENCES users(user_id) ON DELETE RESTRICT,
  CONSTRAINT fk_ticket_approved_by
    FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT fk_ticket_picked_up_by
    FOREIGN KEY (picked_up_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;



-- =========================================================
-- Bảng Borrow_Items (chi tiết phiếu mượn)
-- Dùng để: mỗi dòng tương ứng 1 cuốn/copy -> trả từng cuốn, tránh trả trùng.
-- UNIQUE(ticket_id, copy_id) để 1 cuốn không bị add 2 lần vào cùng ticket.
-- =========================================================
CREATE TABLE borrow_items (
    borrow_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticket_id BIGINT NOT NULL,
    copy_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,  -- lưu dư để thống kê/top sách nhanh

    returned_at DATETIME DEFAULT NULL,      -- thời điểm trả
    returned_by BIGINT DEFAULT NULL,         -- ai nhận trả (sẽ là staff)

    status ENUM('BORROWED','RETURNED','REMOVED',"CANCELLED") NOT NULL DEFAULT 'BORROWED',

    UNIQUE (ticket_id, copy_id),

    INDEX idx_bi_ticket (ticket_id),
    INDEX idx_bi_copy (copy_id),
    INDEX idx_bi_book (book_id),
    INDEX idx_bi_status (status),

    CONSTRAINT fk_bi_ticket
        FOREIGN KEY (ticket_id) REFERENCES borrow_tickets(ticket_id) ON DELETE CASCADE,
    CONSTRAINT fk_bi_copy
        FOREIGN KEY (copy_id) REFERENCES book_copies(copy_id) ON DELETE RESTRICT,
    CONSTRAINT fk_bi_book
        FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE RESTRICT,
    CONSTRAINT fk_bi_returned_by
        FOREIGN KEY (returned_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Notifications
-- Dùng để: lưu thông báo gửi đến user (member/staff).
-- =========================================================
CREATE TABLE notifications (
    notification_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    type ENUM(
        'BORROW_CREATED',
        'BORROW_APPROVED',
        'BORROW_PICKED_UP',
        'BORROW_RETURNED',
        'BORROW_CANCELLED',
        'BORROW_OVERDUE'
    ) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    reference_id BIGINT DEFAULT NULL,  -- borrow_ticket_id
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_notification_user_read (user_id, is_read),
    INDEX idx_notification_created (created_at),

    CONSTRAINT fk_notification_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =========================================================
-- Bảng Ticket_Fines (phạt quá hạn + trạng thái thanh toán ZaloPay)
-- 1 ticket tối đa 1 khoản phạt (đơn giản).
-- =========================================================
CREATE TABLE ticket_fines (
  fine_id BIGINT AUTO_INCREMENT PRIMARY KEY,

  ticket_id BIGINT NOT NULL UNIQUE,     -- mỗi phiếu mượn chỉ có 1 bản ghi phạt
  member_id BIGINT NOT NULL,            -- lưu dư để query theo member nhanh

  rate_per_day INT NOT NULL DEFAULT 3000,      -- tiền phạt / ngày / 1 cuốn (VD 3000đ)
  days_overdue INT NOT NULL DEFAULT 0,         -- số ngày quá hạn (chốt tại thời điểm tính)
  unreturned_count INT NOT NULL DEFAULT 0,     -- số cuốn chưa trả trong ticket (chốt)
  amount INT NOT NULL DEFAULT 0,               -- tổng tiền phạt (VND) = rate * days * unreturned_count

  status ENUM('UNPAID','PENDING','PAID','FAILED')
    NOT NULL DEFAULT 'UNPAID',

  -- Tracking ZaloPay (tối thiểu để map callback và đối soát)
  app_trans_id VARCHAR(40) DEFAULT NULL UNIQUE,  -- mã giao dịch do BE tạo
  zp_trans_id VARCHAR(64) DEFAULT NULL,          -- mã giao dịch ZaloPay trả về (nếu có)
  paid_at DATETIME DEFAULT NULL,                 -- thời điểm thanh toán thành công

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX idx_fine_member (member_id),
  INDEX idx_fine_status (status),

  CONSTRAINT fk_fine_ticket
    FOREIGN KEY (ticket_id) REFERENCES borrow_tickets(ticket_id) ON DELETE CASCADE,

  CONSTRAINT fk_fine_member
    FOREIGN KEY (member_id) REFERENCES users(user_id) ON DELETE RESTRICT
) ENGINE=InnoDB;


-- =========================================================
-- Bảng Book_Views (lịch sử xem chi tiết sách của user)
-- Dùng để gợi ý sách dựa trên hành vi xem
-- =========================================================
CREATE TABLE book_views (
  view_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  book_id BIGINT NOT NULL,
  viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_view_user (user_id),
  INDEX idx_view_book (book_id),
  INDEX idx_view_time (viewed_at),

  CONSTRAINT fk_view_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_view_book
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
) ENGINE=InnoDB;


-- =========================================================
-- TRIGGERS tự động cập nhật số lượng sách trong books khi thay đổi book_copies
-- và tự động đổi trạng thái book_copies khi mượn/trả trong borrow_items
-- =========================================================
-- Nên có index này
ALTER TABLE book_copies
ADD INDEX idx_copies_book_status (book_id, status);

-- Xoá trigger cũ nếu có
DROP TRIGGER IF EXISTS trg_copies_ai;
DROP TRIGGER IF EXISTS trg_copies_au;
DROP TRIGGER IF EXISTS trg_copies_ad;

-- NOTE: trg_bi_ai removed (handled in backend code instead)
-- DROP TRIGGER IF EXISTS trg_bi_ai;
DROP TRIGGER IF EXISTS trg_bi_au;

DELIMITER $$

/* =========================================================
   1) BOOK_COPIES -> tự cập nhật books.total_copies, books.available_copies
   Quy ước:
   - total_copies = số cuốn KHÔNG REMOVED
   - available_copies = số cuốn status = AVAILABLE
   ========================================================= */

CREATE TRIGGER trg_copies_ai
AFTER INSERT ON book_copies
FOR EACH ROW
BEGIN
  UPDATE books
  SET total_copies     = total_copies + CASE WHEN NEW.status <> 'REMOVED' THEN 1 ELSE 0 END,
      available_copies = available_copies + CASE WHEN NEW.status = 'AVAILABLE' THEN 1 ELSE 0 END
  WHERE book_id = NEW.book_id;
END$$

CREATE TRIGGER trg_copies_ad
AFTER DELETE ON book_copies
FOR EACH ROW
BEGIN
  UPDATE books
  SET total_copies     = total_copies - CASE WHEN OLD.status <> 'REMOVED' THEN 1 ELSE 0 END,
      available_copies = available_copies - CASE WHEN OLD.status = 'AVAILABLE' THEN 1 ELSE 0 END
  WHERE book_id = OLD.book_id;
END$$

CREATE TRIGGER trg_copies_au
AFTER UPDATE ON book_copies
FOR EACH ROW
BEGIN
  IF OLD.book_id <> NEW.book_id THEN
    -- trừ ở book cũ
    UPDATE books
    SET total_copies     = total_copies - CASE WHEN OLD.status <> 'REMOVED' THEN 1 ELSE 0 END,
        available_copies = available_copies - CASE WHEN OLD.status = 'AVAILABLE' THEN 1 ELSE 0 END
    WHERE book_id = OLD.book_id;

    -- cộng ở book mới
    UPDATE books
    SET total_copies     = total_copies + CASE WHEN NEW.status <> 'REMOVED' THEN 1 ELSE 0 END,
        available_copies = available_copies + CASE WHEN NEW.status = 'AVAILABLE' THEN 1 ELSE 0 END
    WHERE book_id = NEW.book_id;
  ELSE
    -- cùng book: cập nhật theo delta status
    UPDATE books
    SET total_copies = total_copies
        + (CASE WHEN NEW.status <> 'REMOVED' THEN 1 ELSE 0 END
         - CASE WHEN OLD.status <> 'REMOVED' THEN 1 ELSE 0 END),
        available_copies = available_copies
        + (CASE WHEN NEW.status = 'AVAILABLE' THEN 1 ELSE 0 END
         - CASE WHEN OLD.status = 'AVAILABLE' THEN 1 ELSE 0 END)
    WHERE book_id = NEW.book_id;
  END IF;
END$$


/* =========================================================
   2) BORROW_ITEMS -> đổi trạng thái copy (books sẽ tự update nhờ trigger ở trên)
   - Insert borrow_item => copy AVAILABLE -> BORROWED (nếu không AVAILABLE thì báo lỗi)
   - Update borrow_item BORROWED->RETURNED => copy -> AVAILABLE
   - Update borrow_item BORROWED->DAMAGED  => copy -> REMOVED (vì copy table không có DAMAGED)
   ========================================================= */

-- NOTE: trg_bi_ai removed (handled in backend code instead)
-- CREATE TRIGGER trg_bi_ai
-- AFTER INSERT ON borrow_items
-- FOR EACH ROW
-- BEGIN
--   UPDATE book_copies
--   SET status = 'BORROWED'
--   WHERE copy_id = NEW.copy_id AND status = 'AVAILABLE';
--
--   IF ROW_COUNT() = 0 THEN
--     SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Copy is not AVAILABLE, cannot borrow.';
--   END IF;
-- END$$

-- CREATE TRIGGER trg_bi_au
-- AFTER UPDATE ON borrow_items
-- FOR EACH ROW
-- BEGIN
--   IF OLD.status = 'BORROWED' AND NEW.status = 'RETURNED' THEN
--     UPDATE book_copies
--     SET status = 'AVAILABLE'
--     WHERE copy_id = NEW.copy_id;
--   END IF;

--   IF OLD.status = 'BORROWED' AND NEW.status = 'DAMAGED' THEN
--     UPDATE book_copies
--     SET status = 'REMOVED'
--     WHERE copy_id = NEW.copy_id;
--   END IF;
-- END$$

-- DELIMITER ;


-- =========================================================
-- Seed dữ liệu role cơ bản
-- =========================================================
INSERT INTO roles(name, description) VALUES
('ADMIN', 'Quản trị viên'),
('STAFF', 'Nhân viên thư viện'),
('MEMBER', 'Thành viên');
-- =========================================================
-- Seed dữ liệu kệ sách mẫu
-- =========================================================
INSERT INTO shelves (code, name) VALUES
('1A-01', 'Day 1A - Ke 01'),
('1A-02', 'Day 1A - Ke 02'),
('1A-03', 'Day 1A - Ke 03'),
('1A-04', 'Day 1A - Ke 04'),
('1A-05', 'Day 1A - Ke 05'),

('1B-01', 'Day 1B - Ke 01'),
('1B-02', 'Day 1B - Ke 02'),
('1B-03', 'Day 1B - Ke 03'),
('1B-04', 'Day 1B - Ke 04'),
('1B-05', 'Day 1B - Ke 05'),

('1C-01', 'Day 1C - Ke 01'),
('1C-02', 'Day 1C - Ke 02'),
('1C-03', 'Day 1C - Ke 03'),
('1C-04', 'Day 1C - Ke 04'),
('1C-05', 'Day 1C - Ke 05'),

('1D-01', 'Day 1D - Ke 01'),
('1D-02', 'Day 1D - Ke 02'),
('1D-03', 'Day 1D - Ke 03'),
('1D-04', 'Day 1D - Ke 04'),
('1D-05', 'Day 1D - Ke 05');

INSERT INTO categories (name, image) VALUES
('Công nghệ thông tin', 'category/it.jpg'),
('Máy tính', 'category/computer_science.jpg'),
('Trí tuệ và Dữ liệu', 'category/ai_data.jpg'),
('Kỹ thuật', 'category/engineering.jpg'),

('Toán', 'category/math.jpg'),
('Vật lý', 'category/physics.jpg'),
('Hóa học', 'category/chemistry.jpg'),
('Sinh học', 'category/biology.jpg'),
('Môi trường', 'category/environment.jpg'),

('Kinh tế', 'category/economics.jpg'),
('Kinh doanh', 'category/business.jpg'),
('Tài chính', 'category/finance.jpg'),
('Marketing', 'category/marketing.jpg'),
('Khởi nghiệp', 'category/startup.jpg'),

('Tâm lý', 'category/psychology.jpg'),
('Xã hội', 'category/society.jpg'),
('Lịch sử', 'category/history.jpg'),
('Giáo dục', 'category/education.jpg'),

('Ngoại ngữ', 'category/language.jpg'),
('Kỹ năng', 'category/self_development.jpg'),

('Văn học', 'category/literature.jpg'),
('Khác', 'category/other.jpg');
