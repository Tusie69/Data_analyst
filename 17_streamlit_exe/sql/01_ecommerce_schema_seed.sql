-- ============================================================
-- BÀI 17 - CSDL EcommerceDB cho Streamlit Dashboard
-- Chạy: mysql -u root -p < sql/01_ecommerce_schema_seed.sql
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
USE EcommerceDB;

-- Categories
INSERT INTO Categories (category_name) VALUES
('Electronics'),
('Clothing'),
('Home & Kitchen');

-- Products
INSERT INTO Products (product_name, price, category_id) VALUES
('Laptop Dell XPS', 1500.00, 1),
('iPhone 15',       1000.00, 1),
('Wireless Mouse',    25.00, 1),
('T-Shirt Cotton',    20.00, 2),
('Jeans Slim Fit',    50.00, 2),
('Coffee Maker',      80.00, 3),
('Air Fryer',        120.00, 3);

-- Customers
INSERT INTO Customers (customer_name, city) VALUES
('Nguyen Van A', 'Ha Noi'),
('Tran Thi B',   'HCM'),
('Le Van C',     'Da Nang'),
('Pham Thi D',   'Ha Noi'),
('Hoang Van E',  'HCM');

-- Orders
INSERT INTO Orders (customer_id, order_date, status) VALUES
(1, '2026-09-01', 'Completed'),
(2, '2026-09-02', 'Completed'),
(3, '2026-09-03', 'Cancelled'),
(1, '2026-09-05', 'Completed'),
(4, '2026-09-10', 'Completed'),
(5, '2026-09-12', 'Pending'),
(2, '2026-09-15', 'Completed');

-- OrderDetails
INSERT INTO OrderDetails (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 1500.00),
(1, 3, 2,   25.00),
(2, 2, 1, 1000.00),
(2, 4, 3,   20.00),
(3, 5, 2,   50.00),
(4, 3, 5,   25.00),
(4, 6, 1,   80.00),
(5, 7, 2,  120.00),
(6, 1, 1, 1500.00),
(7, 2, 2, 1000.00),
(7, 5, 1,   50.00);

SELECT
    (SELECT COUNT(*) FROM Categories)   AS categories,
    (SELECT COUNT(*) FROM Products)     AS products,
    (SELECT COUNT(*) FROM Customers)    AS customers,
    (SELECT COUNT(*) FROM Orders)       AS orders,
    (SELECT COUNT(*) FROM OrderDetails) AS order_details;
