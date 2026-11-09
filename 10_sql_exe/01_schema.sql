-- ============================================================
-- BÀI 10 - PHẦN 1: TẠO CSDL, BẢNG & MỐI QUAN HỆ
-- Chạy: mysql -u root -p < 01_schema.sql
-- ============================================================

DROP DATABASE IF EXISTS EcommerceDB;
CREATE DATABASE EcommerceDB
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE EcommerceDB;

-- 1. Bảng Danh mục sản phẩm
CREATE TABLE Categories (
    category_id   INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL
);

-- 2. Bảng Sản phẩm
CREATE TABLE Products (
    product_id   INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    price        DECIMAL(10, 2) NOT NULL,
    category_id  INT,
    FOREIGN KEY (category_id) REFERENCES Categories(category_id)
);

-- 3. Bảng Khách hàng
CREATE TABLE Customers (
    customer_id   INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    city          VARCHAR(50) NOT NULL
);

-- 4. Bảng Đơn hàng
CREATE TABLE Orders (
    order_id    INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    order_date  DATE NOT NULL,
    status      VARCHAR(20) CHECK (status IN ('Pending', 'Completed', 'Cancelled')),
    FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
);

-- 5. Bảng Chi tiết đơn hàng
CREATE TABLE OrderDetails (
    order_id   INT,
    product_id INT,
    quantity   INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id)   REFERENCES Orders(order_id),
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
);

-- Index hỗ trợ các truy vấn lọc/gom nhóm thường dùng
CREATE INDEX idx_orders_date   ON Orders(order_date);
CREATE INDEX idx_orders_status ON Orders(status);
CREATE INDEX idx_customers_city ON Customers(city);

SELECT 'Schema EcommerceDB created successfully.' AS result;
