-- ============================================================
--  SLMS — MySQL Database Setup
--  Run this once as root: mysql -u root -p < setup_db.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS slms_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'slms_user'@'localhost' IDENTIFIED BY 'ChangeThisPassword123!';

GRANT ALL PRIVILEGES ON slms_db.* TO 'slms_user'@'localhost';

FLUSH PRIVILEGES;

SELECT 'Database slms_db and user slms_user created successfully.' AS status;
