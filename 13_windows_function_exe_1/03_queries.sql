-- ============================================================
-- BÀI 13 - PHẦN 3: 4 TRUY VẤN WINDOW FUNCTIONS
-- Chạy: mysql -u root -p -t < 03_queries.sql
-- ============================================================

USE RetailAnalyticsDB;

-- ------------------------------------------------------------
-- CÂU 1: Xếp hạng lương trong từng chi nhánh - DENSE_RANK()
-- Đồng hạng và KHÔNG nhảy số (25tr, 25tr, 20tr -> 1, 1, 2)
-- ------------------------------------------------------------
SELECT '=== CAU 1: Xep hang luong theo chi nhanh (DENSE_RANK) ===' AS '';

SELECT  employee_id,
        employee_name,
        branch,
        salary,
        DENSE_RANK() OVER (
            PARTITION BY branch
            ORDER BY salary DESC
        ) AS salary_rank
FROM Employees
ORDER BY branch, salary_rank, employee_name;

-- So sánh 3 hàm xếp hạng để thấy rõ khác biệt
SELECT '--- Cau 1b: So sanh ROW_NUMBER vs RANK vs DENSE_RANK ---' AS '';

SELECT  employee_name,
        branch,
        salary,
        ROW_NUMBER() OVER (PARTITION BY branch ORDER BY salary DESC) AS rn,
        RANK()       OVER (PARTITION BY branch ORDER BY salary DESC) AS rnk,
        DENSE_RANK() OVER (PARTITION BY branch ORDER BY salary DESC) AS dense_rnk
FROM Employees
ORDER BY branch, salary DESC;


-- ------------------------------------------------------------
-- CÂU 2: Đơn hàng lớn nhất của từng khách hàng - ROW_NUMBER() + CTE
-- ROW_NUMBER đảm bảo đúng 1 dòng/khách; order_date DESC phá thế hòa
-- Không thể viết WHERE ROW_NUMBER() = 1 vì window function
-- được tính SAU mệnh đề WHERE -> bắt buộc bọc trong CTE/subquery
-- ------------------------------------------------------------
SELECT '=== CAU 2: Don hang lon nhat cua tung khach hang ===' AS '';

WITH RankedOrders AS (
    SELECT  order_id,
            customer_name,
            order_date,
            total_amount,
            ROW_NUMBER() OVER (
                PARTITION BY customer_name
                ORDER BY total_amount DESC, order_date DESC
            ) AS rn
    FROM Orders
)
SELECT  order_id,
        customer_name,
        order_date,
        total_amount
FROM RankedOrders
WHERE rn = 1
ORDER BY total_amount DESC;


-- ------------------------------------------------------------
-- CÂU 3: So sánh doanh thu với ngày hôm trước - LAG()
-- LAG(revenue, 1): lùi 1 dòng; COALESCE(..., 0) thay cho giá trị
-- mặc định khi không có dòng trước.
--
-- LƯU Ý TƯƠNG THÍCH: MySQL 8.0 cho phép viết gọn LAG(revenue, 1, 0)
-- (tham số thứ 3 là giá trị mặc định), nhưng MariaDB (bản đi kèm XAMPP)
-- KHÔNG hỗ trợ tham số này và sẽ báo lỗi 1064. Dạng COALESCE dưới đây
-- chạy đúng trên cả hai hệ.
-- ------------------------------------------------------------
SELECT '=== CAU 3: Bien dong doanh thu so voi ngay truoc (LAG) ===' AS '';

SELECT  sale_date,
        revenue,
        COALESCE(LAG(revenue, 1) OVER (ORDER BY sale_date ASC), 0) AS previous_day_revenue,
        revenue - COALESCE(LAG(revenue, 1) OVER (ORDER BY sale_date ASC), 0) AS revenue_diff
FROM DailySales
ORDER BY sale_date ASC;

-- Bản mở rộng: thêm % tăng trưởng và nhãn xu hướng
SELECT '--- Cau 3b: Them % tang truong va nhan xu huong ---' AS '';

WITH Daily AS (
    SELECT  sale_date,
            revenue,
            LAG(revenue) OVER (ORDER BY sale_date) AS prev_revenue
    FROM DailySales
)
SELECT  sale_date,
        revenue,
        COALESCE(prev_revenue, 0)          AS previous_day_revenue,
        revenue - COALESCE(prev_revenue, 0) AS revenue_diff,
        CASE WHEN prev_revenue IS NULL THEN NULL
             ELSE ROUND((revenue - prev_revenue) / prev_revenue * 100, 2)
        END AS growth_percent,
        CASE WHEN prev_revenue IS NULL   THEN 'N/A'
             WHEN revenue > prev_revenue THEN 'Tang'
             WHEN revenue < prev_revenue THEN 'Giam'
             ELSE 'Khong doi'
        END AS trend
FROM Daily
ORDER BY sale_date;


-- ------------------------------------------------------------
-- CÂU 4: Tổng doanh thu lũy kế - SUM() OVER (Running Total)
-- ------------------------------------------------------------
SELECT '=== CAU 4: Tong doanh thu luy ke (Running Total) ===' AS '';

SELECT  sale_date,
        revenue,
        SUM(revenue) OVER (
            ORDER BY sale_date ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_total
FROM DailySales
ORDER BY sale_date ASC;

-- Bản mở rộng: thêm trung bình trượt 3 ngày và tỷ trọng trên tổng kỳ
SELECT '--- Cau 4b: Them moving average 3 ngay va ty trong ---' AS '';

SELECT  sale_date,
        revenue,
        SUM(revenue) OVER (ORDER BY sale_date
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
        ROUND(AVG(revenue) OVER (ORDER BY sale_date
                           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2)      AS moving_avg_3days,
        ROUND(revenue * 100.0 / SUM(revenue) OVER (), 2)                      AS pct_of_total
FROM DailySales
ORDER BY sale_date;
