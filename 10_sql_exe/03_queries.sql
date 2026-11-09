-- ============================================================
-- BÀI 10 - PHẦN 3: 9 TRUY VẤN GOM NHÓM & GOM TỤ DỮ LIỆU
-- Chạy: mysql -u root -p -t < 03_queries.sql
--   (-t để in kết quả dạng bảng cho dễ đọc)
-- ============================================================

USE EcommerceDB;

-- ------------------------------------------------------------
-- CÂU 1: Tổng số sản phẩm trong từng danh mục
-- LEFT JOIN để danh mục chưa có sản phẩm vẫn hiện với số đếm 0
-- ------------------------------------------------------------
SELECT '=== CAU 1: So luong san pham theo danh muc ===' AS '';

SELECT  c.category_name,
        COUNT(p.product_id) AS total_products
FROM Categories c
LEFT JOIN Products p ON p.category_id = c.category_id
GROUP BY c.category_id, c.category_name
ORDER BY total_products DESC;


-- ------------------------------------------------------------
-- CÂU 2: Giá trung bình / lớn nhất / nhỏ nhất theo danh mục
-- ------------------------------------------------------------
SELECT '=== CAU 2: Gia AVG / MAX / MIN theo danh muc ===' AS '';

SELECT  c.category_name,
        ROUND(AVG(p.price), 2) AS avg_price,
        MAX(p.price)           AS max_price,
        MIN(p.price)           AS min_price
FROM Categories c
JOIN Products p ON p.category_id = c.category_id
GROUP BY c.category_id, c.category_name
ORDER BY avg_price DESC;


-- ------------------------------------------------------------
-- CÂU 3: Tổng số đơn hàng theo từng trạng thái
-- ------------------------------------------------------------
SELECT '=== CAU 3: So don hang theo trang thai ===' AS '';

SELECT  status,
        COUNT(*) AS total_orders
FROM Orders
GROUP BY status
ORDER BY total_orders DESC;


-- ------------------------------------------------------------
-- CÂU 4: Số đơn hàng Completed của từng khách hàng
-- Điều kiện status đặt trong ON để có thể đổi sang LEFT JOIN
-- mà vẫn giữ được khách hàng có 0 đơn hoàn tất
-- ------------------------------------------------------------
SELECT '=== CAU 4: So don Completed theo khach hang ===' AS '';

SELECT  cu.customer_name,
        COUNT(o.order_id) AS completed_orders
FROM Customers cu
JOIN Orders o
      ON o.customer_id = cu.customer_id
     AND o.status = 'Completed'
GROUP BY cu.customer_id, cu.customer_name
ORDER BY completed_orders DESC, cu.customer_name;


-- ------------------------------------------------------------
-- CÂU 5: Doanh thu của từng đơn hàng Completed
-- ------------------------------------------------------------
SELECT '=== CAU 5: Doanh thu tung don Completed ===' AS '';

SELECT  o.order_id,
        o.order_date,
        SUM(od.quantity * od.unit_price) AS total_revenue
FROM Orders o
JOIN OrderDetails od ON od.order_id = o.order_id
WHERE o.status = 'Completed'
GROUP BY o.order_id, o.order_date
ORDER BY total_revenue DESC;


-- ------------------------------------------------------------
-- CÂU 6: Tổng số lượng đã bán của từng mặt hàng
-- ------------------------------------------------------------
SELECT '=== CAU 6: Tong so luong ban ra theo san pham ===' AS '';

SELECT  p.product_name,
        SUM(od.quantity) AS total_quantity
FROM Products p
JOIN OrderDetails od ON od.product_id = p.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_quantity DESC;

-- Biến thể: chỉ tính hàng thực sự bán được (loại Cancelled / Pending)
SELECT '--- Cau 6b: chi tinh don Completed ---' AS '';

SELECT  p.product_name,
        SUM(od.quantity) AS total_quantity
FROM Products p
JOIN OrderDetails od ON od.product_id = p.product_id
JOIN Orders o        ON o.order_id    = od.order_id
WHERE o.status = 'Completed'
GROUP BY p.product_id, p.product_name
ORDER BY total_quantity DESC;


-- ------------------------------------------------------------
-- CÂU 7: Khách hàng chi tiêu > 1,000 USD (đơn Completed)
-- Điều kiện trên hàm gom tụ bắt buộc nằm ở HAVING
-- ------------------------------------------------------------
SELECT '=== CAU 7: Khach hang chi tieu > 1000 USD ===' AS '';

SELECT  cu.customer_name,
        SUM(od.quantity * od.unit_price) AS total_spent
FROM Customers cu
JOIN Orders o        ON o.customer_id = cu.customer_id
JOIN OrderDetails od ON od.order_id   = o.order_id
WHERE o.status = 'Completed'
GROUP BY cu.customer_id, cu.customer_name
HAVING total_spent > 1000
ORDER BY total_spent DESC;


-- ------------------------------------------------------------
-- CÂU 8: Danh mục bán ra hơn 3 sản phẩm
-- ------------------------------------------------------------
SELECT '=== CAU 8: Danh muc ban ra > 3 san pham ===' AS '';

SELECT  c.category_name,
        SUM(od.quantity) AS total_sold
FROM Categories c
JOIN Products p      ON p.category_id = c.category_id
JOIN OrderDetails od ON od.product_id = p.product_id
GROUP BY c.category_id, c.category_name
HAVING total_sold > 3
ORDER BY total_sold DESC;


-- ------------------------------------------------------------
-- CÂU 9: Doanh thu theo thành phố, chỉ lấy thành phố > 1,500 USD
-- ------------------------------------------------------------
SELECT '=== CAU 9: Doanh thu theo thanh pho > 1500 USD ===' AS '';

SELECT  cu.city,
        SUM(od.quantity * od.unit_price) AS city_revenue
FROM Customers cu
JOIN Orders o        ON o.customer_id = cu.customer_id
JOIN OrderDetails od ON od.order_id   = o.order_id
WHERE o.status = 'Completed'
GROUP BY cu.city
HAVING city_revenue > 1500
ORDER BY city_revenue DESC;
