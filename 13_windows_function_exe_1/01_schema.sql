-- ============================================================
-- BÀI 13 - PHẦN 1: TẠO CSDL RetailAnalyticsDB & 3 BẢNG
-- Yêu cầu: MySQL 8.0+ (Window Functions)
-- Chạy: mysql -u root -p < 01_schema.sql
-- ============================================================

DROP DATABASE IF EXISTS RetailAnalyticsDB;
CREATE DATABASE RetailAnalyticsDB
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE RetailAnalyticsDB;

-- Kiểm tra phiên bản MySQL (Window Functions chỉ có từ 8.0)
SELECT VERSION() AS mysql_version,
       IF(SUBSTRING_INDEX(VERSION(), '.', 1) >= 8,
          'OK - ho tro Window Functions',
          'CANH BAO - can MySQL 8.0 tro len') AS compatibility;

-- 1. Bảng Nhân viên
CREATE TABLE Employees (
    employee_id   INT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    branch        VARCHAR(50) NOT NULL,
    salary        DECIMAL(10, 2) NOT NULL
);

-- 2. Bảng Đơn hàng
CREATE TABLE Orders (
    order_id      INT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    order_date    DATE NOT NULL,
    total_amount  DECIMAL(10, 2) NOT NULL
);

-- 3. Bảng Doanh thu theo ngày
CREATE TABLE DailySales (
    sale_date DATE PRIMARY KEY,
    revenue   DECIMAL(12, 2) NOT NULL
);

CREATE INDEX idx_employees_branch ON Employees(branch, salary);
CREATE INDEX idx_orders_customer  ON Orders(customer_name, total_amount);

SELECT 'Schema RetailAnalyticsDB created successfully.' AS result;
