-- ============================================================
-- ĐỒ ÁN 20 - Các truy vấn phân tích nâng cao (chạy độc lập để kiểm chứng
-- số liệu mà dashboard hiển thị).
-- Chạy: mysql -u root -p -t < sql/03_analysis_queries.sql
-- ============================================================

USE SaaS_AI_DB;

-- ------------------------------------------------------------
-- 1. KPI tổng quan toàn kỳ
-- ------------------------------------------------------------
SELECT '=== 1. KPI tong quan ===' AS '';

SELECT
    COUNT(DISTINCT c.customer_id) AS total_customers,
    SUM(s.status = 'Churned')     AS churned_customers,
    ROUND(SUM(s.status = 'Churned') / COUNT(DISTINCT c.customer_id) * 100, 2) AS churn_rate_pct,
    ROUND(SUM(CASE WHEN s.status IN ('Active', 'Upgraded') THEN p.monthly_price ELSE 0 END), 2) AS mrr_current,
    ROUND(AVG(u.support_tickets_opened), 2) AS avg_support_tickets
FROM Customers c
JOIN Plans p          ON p.plan_id     = c.plan_id
LEFT JOIN Subscriptions s ON s.customer_id = c.customer_id
LEFT JOIN UsageLogs u ON u.customer_id = c.customer_id
                     AND u.usage_month = (SELECT MAX(usage_month) FROM UsageLogs);


-- ------------------------------------------------------------
-- 2. Xu hướng MRR & Churn Rate theo tháng (dữ liệu cho Biểu đồ 1)
-- ------------------------------------------------------------
SELECT '=== 2. Xu huong MRR va Churn theo thang ===' AS '';

SELECT
    u.usage_month,
    COUNT(DISTINCT u.customer_id) AS active_customers,
    ROUND(SUM(CASE WHEN s.status IN ('Active', 'Upgraded') THEN p.monthly_price ELSE 0 END), 2) AS mrr,
    ROUND(SUM(u.ai_api_cost), 2) AS ai_cost,
    ROUND(SUM(CASE WHEN s.status IN ('Active', 'Upgraded') THEN p.monthly_price ELSE 0 END)
          - SUM(u.ai_api_cost), 2) AS net_margin,
    (SELECT COUNT(*)
       FROM Subscriptions s2
      WHERE s2.status = 'Churned'
        AND DATE_FORMAT(s2.updated_at, '%Y-%m') = DATE_FORMAT(u.usage_month, '%Y-%m')
    ) AS churned_this_month
FROM UsageLogs u
JOIN Customers c      ON c.customer_id = u.customer_id
JOIN Plans p          ON p.plan_id     = c.plan_id
LEFT JOIN Subscriptions s ON s.customer_id = c.customer_id
WHERE 1 = 1
GROUP BY u.usage_month
ORDER BY u.usage_month;


-- ------------------------------------------------------------
-- 3. Biên lợi nhuận AI theo từng gói dịch vụ (Insight 2)
-- ------------------------------------------------------------
SELECT '=== 3. Bien loi nhuan AI theo goi ===' AS '';

SELECT
    p.plan_name,
    p.monthly_price,
    p.ai_token_limit,
    COUNT(*)                                   AS usage_rows,
    ROUND(AVG(u.tokens_consumed), 0)           AS avg_tokens,
    ROUND(AVG(u.ai_api_cost), 2)               AS avg_ai_cost,
    ROUND(SUM(p.monthly_price - u.ai_api_cost), 2) AS total_margin,
    ROUND((SUM(p.monthly_price) - SUM(u.ai_api_cost)) / SUM(p.monthly_price) * 100, 2) AS margin_pct,
    SUM(u.tokens_consumed > p.ai_token_limit)  AS months_over_limit
FROM UsageLogs u
JOIN Customers c ON c.customer_id = u.customer_id
JOIN Plans p     ON p.plan_id     = c.plan_id
GROUP BY p.plan_id, p.plan_name, p.monthly_price, p.ai_token_limit
ORDER BY margin_pct ASC;


-- ------------------------------------------------------------
-- 4. Churn rate theo quy mô x tình trạng token (dữ liệu cho Heatmap)
-- ------------------------------------------------------------
SELECT '=== 4. Churn rate theo quy mo x overage (Insight 1) ===' AS '';

WITH CustomerUsage AS (
    SELECT
        c.customer_id,
        c.company_size,
        s.status,
        MAX(u.tokens_consumed) > p.ai_token_limit AS ever_over_limit
    FROM Customers c
    JOIN Plans p     ON p.plan_id     = c.plan_id
    JOIN UsageLogs u ON u.customer_id = c.customer_id
    LEFT JOIN Subscriptions s ON s.customer_id = c.customer_id
    GROUP BY c.customer_id, c.company_size, s.status, p.ai_token_limit
)
SELECT
    company_size,
    IF(ever_over_limit, 'Vuot han muc token', 'Trong han muc') AS token_status,
    COUNT(*)                   AS customers,
    SUM(status = 'Churned')    AS churned,
    ROUND(SUM(status = 'Churned') / COUNT(*) * 100, 1) AS churn_rate_pct
FROM CustomerUsage
GROUP BY company_size, ever_over_limit
ORDER BY churn_rate_pct DESC;


-- ------------------------------------------------------------
-- 5. Lý do hủy dịch vụ phổ biến (dữ liệu cho Biểu đồ 3)
-- ------------------------------------------------------------
SELECT '=== 5. Ly do huy dich vu ===' AS '';

SELECT
    s.churn_reason,
    COUNT(*) AS customers,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM Subscriptions WHERE status = 'Churned') * 100, 1) AS share_pct
FROM Subscriptions s
WHERE s.status = 'Churned'
  AND s.churn_reason IS NOT NULL
GROUP BY s.churn_reason
ORDER BY customers DESC;


-- ------------------------------------------------------------
-- 6. Danh sách khách hàng NGUY CƠ CHURN CAO (GROUP BY + HAVING)
--    Tiêu chí: token đỉnh vượt hạn mức HOẶC mở > 3 ticket trong 1 tháng
-- ------------------------------------------------------------
SELECT '=== 6. Khach hang nguy co churn cao (top 20) ===' AS '';

SELECT
    c.customer_id,
    c.customer_name,
    c.company_size,
    p.plan_name,
    s.status,
    MAX(u.tokens_consumed)        AS peak_tokens,
    p.ai_token_limit,
    ROUND(MAX(u.tokens_consumed) / p.ai_token_limit * 100, 1) AS peak_usage_pct,
    MAX(u.support_tickets_opened) AS peak_tickets,
    ROUND(SUM(u.ai_api_cost), 2)  AS total_ai_cost,
    ROUND(SUM(p.monthly_price - u.ai_api_cost), 2) AS net_margin
FROM UsageLogs u
JOIN Customers c ON c.customer_id = u.customer_id
JOIN Plans p     ON p.plan_id     = c.plan_id
LEFT JOIN Subscriptions s ON s.customer_id = c.customer_id
WHERE 1 = 1
GROUP BY c.customer_id, c.customer_name, c.company_size,
         p.plan_name, p.monthly_price, p.ai_token_limit, s.status
HAVING MAX(u.tokens_consumed) > p.ai_token_limit
    OR MAX(u.support_tickets_opened) > 3
ORDER BY peak_usage_pct DESC, peak_tickets DESC
LIMIT 20;


-- ------------------------------------------------------------
-- 7. Tác động của support ticket tới churn (Insight 3)
-- ------------------------------------------------------------
SELECT '=== 7. Churn rate theo nhom support ticket ===' AS '';

WITH CustTickets AS (
    SELECT c.customer_id,
           s.status,
           MAX(u.support_tickets_opened) AS peak_tickets
    FROM Customers c
    JOIN UsageLogs u ON u.customer_id = c.customer_id
    LEFT JOIN Subscriptions s ON s.customer_id = c.customer_id
    GROUP BY c.customer_id, s.status
)
SELECT
    IF(peak_tickets > 3, 'Mo > 3 ticket/thang', 'Mo <= 3 ticket/thang') AS ticket_group,
    COUNT(*)                AS customers,
    SUM(status = 'Churned') AS churned,
    ROUND(SUM(status = 'Churned') / COUNT(*) * 100, 1) AS churn_rate_pct
FROM CustTickets
GROUP BY ticket_group
ORDER BY churn_rate_pct DESC;
