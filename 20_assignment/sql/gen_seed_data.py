"""
Sinh dữ liệu mẫu thực tế cho SaaS_AI_DB và ghi ra file 02_seed_data.sql.

Chạy lại khi muốn tạo bộ dữ liệu mới:
    python sql/gen_seed_data.py

Dữ liệu được sinh với RANDOM_SEED cố định nên luôn tái lập được y hệt.
Mô hình dữ liệu cài sẵn các quy luật kinh doanh để dashboard có insight thật:
  - Khách vượt giới hạn token (overage) có chi phí AI tăng vọt -> churn cao hơn.
  - Nhóm Startup dùng gói giá thấp nên overage làm biên lợi nhuận âm.
  - Khách mở nhiều support ticket có xu hướng churn cao hơn.
"""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

RANDOM_SEED = 42
N_CUSTOMERS = 140
MONTH_START = (2026, 1)
MONTH_END = (2026, 10)
# Đơn giá token theo gói (gói lớn được chiết khấu theo khối lượng).
# Mức này khiến chi phí AI chiếm ~40-50% giá gói khi dùng đúng hạn mức,
# nên chỉ cần vượt hạn mức là biên lợi nhuận có thể âm.
TOKEN_UNIT_COST = {1: 0.000048, 2: 0.000045, 3: 0.000035, 4: 0.000026}
OVERAGE_COST_MULTIPLIER = 1.8   # token vượt hạn mức bị tính giá cao hơn

rnd = random.Random(RANDOM_SEED)

# ---------------------------------------------------------------------------
# 1. Gói dịch vụ
# ---------------------------------------------------------------------------
PLANS = [
    # plan_id, plan_name, monthly_price, ai_token_limit
    (1, "Starter", 49.00, 500_000),
    (2, "Growth", 199.00, 2_000_000),
    (3, "Business", 499.00, 6_000_000),
    (4, "Enterprise", 1299.00, 20_000_000),
]
PLAN_PRICE = {p[0]: p[2] for p in PLANS}
PLAN_LIMIT = {p[0]: p[3] for p in PLANS}
PLAN_NAME = {p[0]: p[1] for p in PLANS}

# Phân khúc -> gói dịch vụ thường dùng
PLAN_WEIGHTS = {
    "Startup": [(1, 0.70), (2, 0.25), (3, 0.05), (4, 0.00)],
    "SMB": [(1, 0.15), (2, 0.50), (3, 0.30), (4, 0.05)],
    "Enterprise": [(1, 0.00), (2, 0.10), (3, 0.45), (4, 0.45)],
}
SIZE_WEIGHTS = [("Startup", 0.45), ("SMB", 0.35), ("Enterprise", 0.20)]

# Xác suất vượt hạn mức token theo phân khúc
OVERAGE_PROB = {"Startup": 0.48, "SMB": 0.28, "Enterprise": 0.30}

# Hệ số nhân rủi ro churn khi vượt token (Startup nhạy cảm giá nhất)
OVERAGE_CHURN_FACTOR = {"Startup": 2.6, "SMB": 1.7, "Enterprise": 1.3}
BASE_CHURN_PROB = {"Startup": 0.18, "SMB": 0.13, "Enterprise": 0.08}

CHURN_REASONS_OVERAGE = [
    ("Chi phi AI vuot ngan sach", 0.55),
    ("Gia goi dich vu qua cao", 0.25),
    ("Chuyen sang doi thu re hon", 0.12),
    ("Trai nghiem ho tro kem", 0.08),
]
CHURN_REASONS_NORMAL = [
    ("Thieu tinh nang can thiet", 0.30),
    ("Trai nghiem ho tro kem", 0.22),
    ("Du an ket thuc", 0.20),
    ("Chuyen sang doi thu re hon", 0.16),
    ("Gia goi dich vu qua cao", 0.12),
]

FIRST_NAMES = [
    "Alpha", "Beta", "Gamma", "Delta", "Omega", "Nova", "Zenith", "Vertex",
    "Lumen", "Orbit", "Pixel", "Quanta", "Helix", "Nimbus", "Vector", "Aurora",
    "Cobalt", "Falcon", "Granite", "Horizon", "Ionic", "Jupiter", "Kinetic",
    "Lattice", "Meridian", "Nucleus", "Onyx", "Polaris", "Quartz", "Radian",
    "Summit", "Tectonic", "Umbra", "Vanta", "Willow", "Xenon", "Yield", "Zephyr",
]
SUFFIXES = ["Tech", "Labs", "Soft", "Systems", "Digital", "Analytics", "Cloud", "Works"]


def weighted_choice(pairs: list[tuple]) -> object:
    r = rnd.random()
    acc = 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]


def month_list(start: tuple[int, int], end: tuple[int, int]) -> list[date]:
    months, (y, m) = [], start
    while (y, m) <= end:
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return months


MONTHS = month_list(MONTH_START, MONTH_END)


def sql_str(value) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# 2. Sinh khách hàng
# ---------------------------------------------------------------------------
customers: list[dict] = []
used_names: set[str] = set()

for cid in range(1, N_CUSTOMERS + 1):
    while True:
        name = f"{rnd.choice(FIRST_NAMES)} {rnd.choice(SUFFIXES)}"
        if name not in used_names:
            used_names.add(name)
            break

    size = weighted_choice(SIZE_WEIGHTS)
    plan_id = weighted_choice(PLAN_WEIGHTS[size])

    # Ngày đăng ký: rải từ 2025-03 đến 2026-08
    signup_year = rnd.choice([2025, 2025, 2026])
    if signup_year == 2025:
        signup = date(2025, rnd.randint(3, 12), rnd.randint(1, 28))
    else:
        signup = date(2026, rnd.randint(1, 8), rnd.randint(1, 28))

    customers.append(
        {
            "customer_id": cid,
            "customer_name": name,
            "company_size": size,
            "signup_date": signup,
            "plan_id": plan_id,
            "is_overage": rnd.random() < OVERAGE_PROB[size],
        }
    )

# ---------------------------------------------------------------------------
# 3. Quyết định trạng thái đăng ký & tháng churn
# ---------------------------------------------------------------------------
for c in customers:
    size, overage = c["company_size"], c["is_overage"]

    churn_prob = BASE_CHURN_PROB[size]
    if overage:
        churn_prob *= OVERAGE_CHURN_FACTOR[size]

    # Khách mới đăng ký chưa kịp churn
    first_active = max(c["signup_date"].replace(day=1), MONTHS[0])
    available = [m for m in MONTHS if m >= first_active]
    if len(available) <= 2:
        churn_prob *= 0.3

    if rnd.random() < min(churn_prob, 0.85) and len(available) >= 2:
        c["status"] = "Churned"
        # Churn xảy ra ở một trong các tháng sau tháng hoạt động đầu tiên
        later = available[1:]
        # Nghiêng về các tháng gần đây: lặp lại nửa sau của danh sách
        weighted = later + later[len(later) // 2:]
        c["churn_month"] = rnd.choice(weighted)
        reasons = CHURN_REASONS_OVERAGE if overage else CHURN_REASONS_NORMAL
        c["churn_reason"] = weighted_choice(reasons)
        c["updated_at"] = date(
            c["churn_month"].year, c["churn_month"].month, rnd.randint(5, 28)
        )
    else:
        c["churn_month"] = None
        c["churn_reason"] = None
        # Khách không churn: một phần nâng cấp gói
        upgrade_prob = 0.10 if overage else 0.24
        if size == "Enterprise":
            upgrade_prob += 0.08
        if rnd.random() < upgrade_prob and c["plan_id"] < 4:
            c["status"] = "Upgraded"
            c["plan_id"] += 1  # nâng lên gói cao hơn
        else:
            c["status"] = "Active"
        c["updated_at"] = date(2026, 10, rnd.randint(1, 28))

# ---------------------------------------------------------------------------
# 4. Sinh UsageLogs theo từng tháng hoạt động
# ---------------------------------------------------------------------------
usage_rows: list[tuple] = []

for c in customers:
    plan_id = c["plan_id"]
    limit = PLAN_LIMIT[plan_id]
    # Mức dùng nền: 35% - 70% hạn mức
    base_tokens = limit * rnd.uniform(0.35, 0.70)
    growth = rnd.uniform(1.01, 1.14)       # tăng trưởng sử dụng mỗi tháng
    overage_ramp = rnd.uniform(1.45, 2.40) if c["is_overage"] else 1.0

    first_active = max(c["signup_date"].replace(day=1), MONTHS[0])
    active_months = [m for m in MONTHS if m >= first_active]
    if c["churn_month"]:
        active_months = [m for m in active_months if m <= c["churn_month"]]

    for idx, m in enumerate(active_months):
        tokens = base_tokens * (growth ** idx) * rnd.uniform(0.92, 1.10)
        if c["is_overage"]:
            # Vượt hạn mức ngay từ những tháng đầu rồi tăng dần
            tokens *= 1 + (overage_ramp - 1) * min((idx + 1.5) / 3, 1.0)
        tokens = int(max(tokens, limit * 0.15))
        if not c["is_overage"]:
            # Khách trong hạn mức không bao giờ vượt trần gói (tối đa 97%),
            # nhờ vậy cột "vượt hạn mức" trên dashboard đúng nghĩa là nhóm overage.
            tokens = min(tokens, int(limit * 0.97))

        # Chi phí: phần trong hạn mức giá thường, phần vượt bị tính đắt hơn
        within = min(tokens, limit)
        over = max(tokens - limit, 0)
        unit = TOKEN_UNIT_COST[plan_id]
        cost = (within + over * OVERAGE_COST_MULTIPLIER) * unit
        cost *= rnd.uniform(0.94, 1.08)    # nhiễu giá theo mô hình/nhà cung cấp

        # Support ticket: tăng mạnh khi vượt hạn mức hoặc sắp churn
        lam = 0.8
        if over > 0:
            lam += 2.2
        if c["status"] == "Churned":
            lam += 0.8                       # khách sắp rời bỏ gặp nhiều vấn đề hơn
            if m == c["churn_month"]:
                lam += 2.0
        tickets = min(int(rnd.gauss(lam, 1.2)), 12)
        tickets = max(tickets, 0)

        usage_rows.append((c["customer_id"], m, tokens, round(cost, 2), tickets))

# ---------------------------------------------------------------------------
# 5. Ghi file SQL
# ---------------------------------------------------------------------------
out_path = Path(__file__).with_name("02_seed_data.sql")
lines: list[str] = [
    "-- ============================================================",
    "-- ĐỒ ÁN 20: Dữ liệu mẫu cho SaaS_AI_DB",
    f"-- File này được sinh tự động bởi gen_seed_data.py (seed={RANDOM_SEED})",
    "-- Chạy: mysql -u root -p < sql/02_seed_data.sql",
    "-- ============================================================",
    "",
    "USE SaaS_AI_DB;",
    "",
    "-- 1. Plans",
    "INSERT INTO Plans (plan_id, plan_name, monthly_price, ai_token_limit) VALUES",
]
lines.append(
    ",\n".join(
        f"({p[0]}, {sql_str(p[1])}, {p[2]:.2f}, {p[3]})" for p in PLANS
    )
    + ";"
)

lines += ["", f"-- 2. Customers ({len(customers)} khách hàng)",
          "INSERT INTO Customers (customer_id, customer_name, company_size, signup_date, plan_id) VALUES"]
lines.append(
    ",\n".join(
        f"({c['customer_id']}, {sql_str(c['customer_name'])}, {sql_str(c['company_size'])}, "
        f"{sql_str(c['signup_date'])}, {c['plan_id']})"
        for c in customers
    )
    + ";"
)

lines += ["", f"-- 3. UsageLogs ({len(usage_rows)} dòng)",
          "INSERT INTO UsageLogs (customer_id, usage_month, tokens_consumed, ai_api_cost, support_tickets_opened) VALUES"]
lines.append(
    ",\n".join(
        f"({cid}, {sql_str(m)}, {tok}, {cost:.2f}, {tk})"
        for cid, m, tok, cost, tk in usage_rows
    )
    + ";"
)

lines += ["", "-- 4. Subscriptions",
          "INSERT INTO Subscriptions (customer_id, status, churn_reason, updated_at) VALUES"]
lines.append(
    ",\n".join(
        f"({c['customer_id']}, {sql_str(c['status'])}, {sql_str(c['churn_reason'])}, "
        f"{sql_str(c['updated_at'])})"
        for c in customers
    )
    + ";"
)

lines += [
    "",
    "SELECT",
    "    (SELECT COUNT(*) FROM Plans)         AS plans,",
    "    (SELECT COUNT(*) FROM Customers)     AS customers,",
    "    (SELECT COUNT(*) FROM UsageLogs)     AS usage_logs,",
    "    (SELECT COUNT(*) FROM Subscriptions) AS subscriptions;",
    "",
]

out_path.write_text("\n".join(lines), encoding="utf-8")

# ---------------------------------------------------------------------------
# 6. In thống kê kiểm chứng (dùng để viết phần Insight trong README)
# ---------------------------------------------------------------------------
def pct(a: int, b: int) -> str:
    return f"{a / b * 100:5.1f}%" if b else "  n/a"


print(f"Da ghi {out_path.name}: {len(customers)} customers, {len(usage_rows)} usage logs\n")

print("--- Churn rate theo phan khuc ---")
for size, _ in SIZE_WEIGHTS:
    grp = [c for c in customers if c["company_size"] == size]
    churned = [c for c in grp if c["status"] == "Churned"]
    print(f"{size:11s} n={len(grp):3d}  churn={pct(len(churned), len(grp))}")

print("\n--- Churn rate: vuot token vs khong vuot ---")
for size, _ in SIZE_WEIGHTS:
    for flag in (True, False):
        grp = [c for c in customers if c["company_size"] == size and c["is_overage"] == flag]
        churned = [c for c in grp if c["status"] == "Churned"]
        label = "vuot token" if flag else "trong han muc"
        print(f"{size:11s} {label:14s} n={len(grp):3d}  churn={pct(len(churned), len(grp))}")

print("\n--- Bien loi nhuan AI theo goi (thang 2026-10) ---")
last_month = MONTHS[-1]
by_plan: dict[int, list[float]] = {}
for cid, m, tok, cost, tk in usage_rows:
    if m != last_month:
        continue
    c = customers[cid - 1]
    by_plan.setdefault(c["plan_id"], []).append(PLAN_PRICE[c["plan_id"]] - cost)
for pid in sorted(by_plan):
    vals = by_plan[pid]
    neg = sum(1 for v in vals if v < 0)
    print(
        f"{PLAN_NAME[pid]:11s} n={len(vals):3d}  margin TB=${sum(vals)/len(vals):8.2f}  "
        f"so KH margin am={neg}"
    )

print("\n--- Churn theo so support ticket ---")
tickets_by_cust: dict[int, int] = {}
for cid, m, tok, cost, tk in usage_rows:
    tickets_by_cust[cid] = max(tickets_by_cust.get(cid, 0), tk)
for label, cond in (("<=3 ticket", lambda t: t <= 3), (">3 ticket", lambda t: t > 3)):
    grp = [c for c in customers if cond(tickets_by_cust.get(c["customer_id"], 0))]
    churned = [c for c in grp if c["status"] == "Churned"]
    print(f"{label:11s} n={len(grp):3d}  churn={pct(len(churned), len(grp))}")

print("\n--- Ly do churn pho bien ---")
reasons: dict[str, int] = {}
for c in customers:
    if c["churn_reason"]:
        reasons[c["churn_reason"]] = reasons.get(c["churn_reason"], 0) + 1
for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f"{n:3d}  {r}")
