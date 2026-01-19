-- ============================================================
-- SIMPLE TEST DATA - Just Users for API Testing
-- ============================================================
-- APIs use ChromaDB for search, not MySQL
-- This creates minimal test users only

USE library_db;

-- Ensure roles exist
INSERT IGNORE INTO roles (role_id, name) VALUES
(1, 'ADMIN'),
(2, 'STAFF'),
(3, 'MEMBER');

-- Create 3 test users (password: "password123")
INSERT INTO users (email, password_hash, status) VALUES
('admin@test.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYILSBhCRDO', 'ACTIVE'),
('user@test.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYILSBhCRDO', 'ACTIVE'),
('member@test.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYILSBhCRDO', 'ACTIVE')
ON DUPLICATE KEY UPDATE email=email;

-- Get inserted IDs
SET @admin_id = (SELECT user_id FROM users WHERE email='admin@test.com');
SET @user_id = (SELECT user_id FROM users WHERE email='user@test.com');
SET @member_id = (SELECT user_id FROM users WHERE email='member@test.com');

-- Profiles
INSERT INTO profiles (user_id, full_name, phone) VALUES
(@admin_id, 'Admin Test', '0901111111'),
(@user_id, 'User Test', '0902222222'),
(@member_id, 'Member Test', '0903333333')
ON DUPLICATE KEY UPDATE full_name=full_name;

-- Roles
INSERT IGNORE INTO user_roles (user_id, role_id) VALUES
(@admin_id, 1), (@admin_id, 2),
(@user_id, 3),
(@member_id, 3);

-- Verify
SELECT '✅ Test Users Created!' as Status;
SELECT user_id, email, status FROM users WHERE email LIKE '%test.com';
