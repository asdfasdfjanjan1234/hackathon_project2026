-- Creates the ai_wattage database and an app user. Run once as root:
--     mysql -u root -p < backend/db/setup_mysql.sql
-- Change the password here and in DATABASE_URL in backend/.env.
-- The app creates its tables (devices, samples, ai_samples, component_samples,
-- power_windows, settings) on first connect.

CREATE DATABASE IF NOT EXISTS ai_wattage CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'wattage'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON ai_wattage.* TO 'wattage'@'localhost';
FLUSH PRIVILEGES;
