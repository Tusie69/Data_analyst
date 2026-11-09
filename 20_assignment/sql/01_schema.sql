-- ============================================================
-- ĐỒ ÁN 20: UNIFIED SAAS & AI COST ANALYTICS DASHBOARD
-- Phần 1: Cấu trúc CSDL SaaS_AI_DB (4 bảng)
-- Chạy: mysql -u root -p < sql/01_schema.sql
-- ============================================================

DROP DATABASE IF EXISTS SaaS_AI_DB;
CREATE DATABASE SaaS_AI_DB
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE SaaS_AI_DB;

-- 1. Bảng Gói dịch vụ
CREATE TABLE Plans (
    plan_id        INT AUTO_INCREMENT PRIMARY KEY,
    plan_name      VARCHAR(50) NOT NULL,
    monthly_price  DECIMAL(10, 2) NOT NULL,
    ai_token_limit INT NOT NULL
);

-- 2. Bảng Khách hàng
CREATE TABLE Customers (
    customer_id   INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    company_size  VARCHAR(20) CHECK (company_size IN ('Startup', 'SMB', 'Enterprise')),
    signup_date   DATE NOT NULL,
    plan_id       INT,
    FOREIGN KEY (plan_id) REFERENCES Plans(plan_id)
);

-- 3. Bảng Lịch sử Sử dụng & Chi phí AI Hàng tháng
CREATE TABLE UsageLogs (
    log_id                 INT AUTO_INCREMENT PRIMARY KEY,
    customer_id            INT,
    usage_month            DATE NOT NULL,
    tokens_consumed        INT NOT NULL,
    ai_api_cost            DECIMAL(10, 2) NOT NULL,
    support_tickets_opened INT DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
);

-- 4. Bảng Trạng thái Đăng ký
CREATE TABLE Subscriptions (
    subscription_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT,
    status          VARCHAR(20) CHECK (status IN ('Active', 'Churned', 'Upgraded')),
    churn_reason    VARCHAR(150),
    updated_at      DATE NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
);

-- ------------------------------------------------------------
-- Index phục vụ các truy vấn lọc động của dashboard
-- ------------------------------------------------------------
CREATE INDEX idx_customers_size   ON Customers(company_size);
CREATE INDEX idx_customers_plan   ON Customers(plan_id);
CREATE INDEX idx_usage_month      ON UsageLogs(usage_month);
CREATE INDEX idx_usage_customer   ON UsageLogs(customer_id, usage_month);
CREATE INDEX idx_subs_status      ON Subscriptions(status);
CREATE UNIQUE INDEX uq_subs_customer ON Subscriptions(customer_id);
CREATE UNIQUE INDEX uq_usage_cust_month ON UsageLogs(customer_id, usage_month);

SELECT 'Schema SaaS_AI_DB created successfully.' AS result;
