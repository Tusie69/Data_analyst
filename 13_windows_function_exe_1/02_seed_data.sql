-- ============================================================
-- BÀI 13 - PHẦN 2: THÊM DỮ LIỆU MẪU
-- Chạy: mysql -u root -p < 02_seed_data.sql
-- ============================================================

USE RetailAnalyticsDB;

-- Employees (Ha Noi có 2 nhân viên cùng lương 25tr để thấy rõ đồng hạng)
INSERT INTO Employees (employee_id, employee_name, branch, salary) VALUES
(1, 'Nguyen Van A', 'Ha Noi', 20000000),
(2, 'Tran Thi B',   'Ha Noi', 25000000),
(3, 'Le Van C',     'Ha Noi', 25000000),
(4, 'Pham Thi D',   'HCM',    18000000),
(5, 'Hoang Van E',  'HCM',    30000000),
(6, 'Vu Thi F',     'HCM',    22000000);

-- Orders
INSERT INTO Orders (order_id, customer_name, order_date, total_amount) VALUES
(101, 'Anh Tuan',  '2026-10-01',  5000000),
(102, 'Anh Tuan',  '2026-10-10', 12000000),
(103, 'Minh Hang', '2026-10-02',  3000000),
(104, 'Minh Hang', '2026-10-15', 15000000),
(105, 'Anh Tuan',  '2026-10-18',  8000000);

-- DailySales
INSERT INTO DailySales (sale_date, revenue) VALUES
('2026-10-01', 50000000),
('2026-10-02', 45000000),
('2026-10-03', 60000000),
('2026-10-04', 55000000),
('2026-10-05', 70000000);

SELECT
    (SELECT COUNT(*) FROM Employees)  AS employees,
    (SELECT COUNT(*) FROM Orders)     AS orders,
    (SELECT COUNT(*) FROM DailySales) AS daily_sales;
