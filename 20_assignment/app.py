"""
ĐỒ ÁN 20 - UNIFIED SAAS & AI COST ANALYTICS DASHBOARD
Phân tích Tỉ lệ Churn (khách hàng rời bỏ) & Chi phí Tích hợp AI trong dịch vụ SaaS.

Stack: Streamlit + MySQL (SQLAlchemy) + Plotly Express.
Chạy:  streamlit run app.py
"""

from __future__ import annotations

import io
import os
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ===========================================================================
# 0. CẤU HÌNH & BẢNG MÀU CÓ MỤC ĐÍCH
# ===========================================================================
st.set_page_config(
    page_title="SaaS & AI Cost Analytics",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Màu có ngữ nghĩa: xanh = doanh thu/tốt, đỏ-cam = churn/chi phí/cảnh báo
C_REVENUE = "#0F766E"   # teal - MRR
C_CHURN = "#DC2626"     # đỏ - churn
C_COST = "#EA580C"      # cam - chi phí AI
C_NEUTRAL = "#64748B"
PLAN_COLORS = {
    "Starter": "#F59E0B",
    "Growth": "#3B82F6",
    "Business": "#8B5CF6",
    "Enterprise": "#0F766E",
}
SIZE_ORDER = ["Startup", "SMB", "Enterprise"]
PLAN_ORDER = ["Starter", "Growth", "Business", "Enterprise"]

CSS = """
<style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    div[data-testid="stMetric"] {
        background: rgba(148, 163, 184, 0.10);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 12px;
        padding: 16px 18px;
    }
    div[data-testid="stMetricLabel"] p {font-size: 0.85rem; opacity: 0.85;}
    h3 {margin-top: 0.4rem;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ===========================================================================
# 1. TẦNG KẾT NỐI CSDL (caching + xử lý lỗi)
# ===========================================================================
@st.cache_resource(show_spinner="Đang kết nối MySQL...")
def get_engine() -> Engine:
    """Tạo Engine 1 lần duy nhất cho cả phiên làm việc (cache_resource)."""
    try:
        cfg = dict(st.secrets.get("mysql", {}))
    except Exception:
        cfg = {}

    host = cfg.get("host") or os.getenv("DB_HOST", "localhost")
    port = int(cfg.get("port") or os.getenv("DB_PORT", 3306))
    user = cfg.get("user") or os.getenv("DB_USER", "root")
    password = cfg.get("password") or os.getenv("DB_PASSWORD", "")
    database = cfg.get("database") or os.getenv("DB_NAME", "SaaS_AI_DB")

    engine = create_engine(
        f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}",
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Chạy SELECT, trả DataFrame. Cache 5 phút theo (sql, params)."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def in_clause(values: list, prefix: str) -> tuple[str, dict]:
    """Sinh mệnh đề IN tham số hóa an toàn: (:p0, :p1, ...)."""
    keys = [f"{prefix}{i}" for i in range(len(values))]
    return f"({', '.join(f':{k}' for k in keys)})", dict(zip(keys, values))


# ===========================================================================
# 2. CÁC CÂU TRUY VẤN SQL
# ===========================================================================
SQL_BOUNDS = "SELECT MIN(usage_month) AS min_m, MAX(usage_month) AS max_m FROM UsageLogs"
SQL_SIZES = "SELECT DISTINCT company_size FROM Customers WHERE company_size IS NOT NULL"
SQL_STATUSES = "SELECT DISTINCT status FROM Subscriptions ORDER BY status"
SQL_PLANS = "SELECT plan_id, plan_name, monthly_price, ai_token_limit FROM Plans ORDER BY plan_id"


def build_fact_query(
    start: date, end: date, sizes: list[str], status: str | None
) -> tuple[str, dict]:
    """
    Bảng fact chi tiết: 1 dòng = 1 khách hàng x 1 tháng sử dụng.
    JOIN 4 bảng + mệnh đề điều kiện động theo mẫu WHERE 1=1.
    """
    sql = """
SELECT  c.customer_id,
        c.customer_name,
        c.company_size,
        c.signup_date,
        p.plan_id,
        p.plan_name,
        p.monthly_price,
        p.ai_token_limit,
        u.usage_month,
        u.tokens_consumed,
        u.ai_api_cost,
        u.support_tickets_opened,
        s.status,
        s.churn_reason,
        s.updated_at,
        (u.tokens_consumed > p.ai_token_limit)      AS is_over_limit,
        (u.tokens_consumed - p.ai_token_limit)      AS tokens_over,
        (p.monthly_price - u.ai_api_cost)           AS net_margin
FROM UsageLogs u
JOIN Customers     c ON c.customer_id = u.customer_id
JOIN Plans         p ON p.plan_id     = c.plan_id
LEFT JOIN Subscriptions s ON s.customer_id = c.customer_id
WHERE 1 = 1
  AND u.usage_month BETWEEN :start_m AND :end_m
"""
    params: dict = {"start_m": start, "end_m": end}

    if sizes:
        clause, p = in_clause(sizes, "sz")
        sql += f"  AND c.company_size IN {clause}\n"
        params.update(p)

    if status and status != "Tất cả":
        sql += "  AND s.status = :status\n"
        params["status"] = status

    sql += "ORDER BY u.usage_month, c.customer_id"
    return sql, params


def build_at_risk_query(
    start: date, end: date, sizes: list[str], status: str | None, min_tickets: int
) -> tuple[str, dict]:
    """
    Danh sách khách hàng nguy cơ Churn cao - dùng GROUP BY + HAVING:
    tiêu thụ token vượt giới hạn gói HOẶC mở nhiều hơn `min_tickets` ticket/tháng.
    """
    sql = """
SELECT  c.customer_id,
        c.customer_name,
        c.company_size,
        p.plan_name,
        p.monthly_price,
        p.ai_token_limit,
        s.status,
        COUNT(u.log_id)                        AS active_months,
        MAX(u.tokens_consumed)                 AS peak_tokens,
        ROUND(AVG(u.tokens_consumed), 0)       AS avg_tokens,
        ROUND(SUM(u.ai_api_cost), 2)           AS total_ai_cost,
        MAX(u.support_tickets_opened)          AS peak_tickets,
        SUM(u.support_tickets_opened)          AS total_tickets,
        ROUND(SUM(p.monthly_price - u.ai_api_cost), 2) AS net_margin,
        ROUND(MAX(u.tokens_consumed) / p.ai_token_limit * 100, 1) AS peak_usage_pct
FROM UsageLogs u
JOIN Customers     c ON c.customer_id = u.customer_id
JOIN Plans         p ON p.plan_id     = c.plan_id
LEFT JOIN Subscriptions s ON s.customer_id = c.customer_id
WHERE 1 = 1
  AND u.usage_month BETWEEN :start_m AND :end_m
"""
    params: dict = {"start_m": start, "end_m": end, "min_tickets": min_tickets}

    if sizes:
        clause, p = in_clause(sizes, "sz")
        sql += f"  AND c.company_size IN {clause}\n"
        params.update(p)

    if status and status != "Tất cả":
        sql += "  AND s.status = :status\n"
        params["status"] = status

    sql += """GROUP BY c.customer_id, c.customer_name, c.company_size,
         p.plan_name, p.monthly_price, p.ai_token_limit, s.status
HAVING MAX(u.tokens_consumed) > p.ai_token_limit
    OR MAX(u.support_tickets_opened) > :min_tickets
ORDER BY peak_usage_pct DESC, total_tickets DESC"""
    return sql, params


# ===========================================================================
# 3. SIDEBAR - BỘ LỌC ĐỘNG
# ===========================================================================
st.sidebar.title("⚙️ Bộ lọc dữ liệu")

try:
    bounds = run_query(SQL_BOUNDS)
    all_sizes = run_query(SQL_SIZES)["company_size"].tolist()
    all_statuses = run_query(SQL_STATUSES)["status"].tolist()
    df_plans = run_query(SQL_PLANS)
except SQLAlchemyError as exc:
    st.error("❌ Không kết nối được MySQL / CSDL `SaaS_AI_DB`.")
    st.code(str(exc.__cause__ or exc), language="text")
    st.info(
        "**Checklist khắc phục**\n"
        "1. MySQL server đang chạy?\n"
        "2. Đã tạo CSDL: `mysql -u root -p < sql/01_schema.sql` "
        "rồi `mysql -u root -p < sql/02_seed_data.sql`?\n"
        "3. Thông tin trong `.env` (DB_USER / DB_PASSWORD / DB_NAME) đã đúng?"
    )
    st.stop()

min_m = bounds.loc[0, "min_m"] or date(2026, 1, 1)
max_m = bounds.loc[0, "max_m"] or date.today()

picked = st.sidebar.date_input(
    "Khoảng thời gian (theo tháng)",
    value=(min_m, max_m),
    min_value=min_m,
    max_value=max_m,
    help="Dữ liệu sử dụng được ghi theo tháng (ngày đầu tháng).",
)
if isinstance(picked, (list, tuple)) and len(picked) == 2:
    start_m, end_m = picked
else:
    start_m = end_m = picked[0] if isinstance(picked, (list, tuple)) else picked

sel_sizes = st.sidebar.multiselect(
    "Phân khúc doanh nghiệp",
    options=[s for s in SIZE_ORDER if s in all_sizes],
    default=[s for s in SIZE_ORDER if s in all_sizes],
)

sel_status = st.sidebar.selectbox(
    "Trạng thái dịch vụ", options=["Tất cả"] + all_statuses, index=0
)

min_tickets = st.sidebar.slider(
    "Ngưỡng cảnh báo support ticket / tháng", min_value=1, max_value=8, value=3,
    help="Khách mở nhiều hơn ngưỡng này sẽ bị xếp vào nhóm nguy cơ Churn.",
)

st.sidebar.divider()
if st.sidebar.button("🔄 Làm mới dữ liệu (xóa cache)", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

with st.sidebar.expander("📦 Bảng giá các gói"):
    st.dataframe(
        df_plans.rename(
            columns={
                "plan_name": "Gói",
                "monthly_price": "Giá/tháng",
                "ai_token_limit": "Hạn mức token",
            }
        )[["Gói", "Giá/tháng", "Hạn mức token"]],
        hide_index=True,
        use_container_width=True,
    )

if not sel_sizes:
    st.warning("⚠️ Hãy chọn ít nhất một phân khúc doanh nghiệp ở sidebar.")
    st.stop()


# ===========================================================================
# 4. LẤY DỮ LIỆU
# ===========================================================================
sql_fact, params_fact = build_fact_query(start_m, end_m, sel_sizes, sel_status)
sql_risk, params_risk = build_at_risk_query(
    start_m, end_m, sel_sizes, sel_status, min_tickets
)

try:
    df = run_query(sql_fact, params_fact)
    df_risk = run_query(sql_risk, params_risk)
except SQLAlchemyError as exc:
    st.error("❌ Lỗi khi truy vấn dữ liệu.")
    st.code(str(exc.__cause__ or exc), language="text")
    st.stop()

st.title("📉 Unified SaaS & AI Cost Analytics Dashboard")
st.caption(
    f"Kỳ phân tích **{start_m:%m/%Y} – {end_m:%m/%Y}** · "
    f"Phân khúc: **{', '.join(sel_sizes)}** · Trạng thái: **{sel_status}** · "
    f"{len(df):,} dòng usage log"
)

if df.empty:
    st.warning("⚠️ Không có dữ liệu khớp bộ lọc. Hãy nới rộng khoảng thời gian hoặc bộ lọc.")
    st.stop()

# Chuẩn hóa kiểu dữ liệu
df["usage_month"] = pd.to_datetime(df["usage_month"])
df["updated_at"] = pd.to_datetime(df["updated_at"])
df["is_over_limit"] = df["is_over_limit"].astype(bool)
for col in ("monthly_price", "ai_api_cost", "net_margin"):
    df[col] = df[col].astype(float)

# Bảng mức khách hàng (1 dòng = 1 khách)
cust = (
    df.groupby("customer_id", as_index=False)
    .agg(
        customer_name=("customer_name", "first"),
        company_size=("company_size", "first"),
        plan_name=("plan_name", "first"),
        monthly_price=("monthly_price", "first"),
        status=("status", "first"),
        churn_reason=("churn_reason", "first"),
        updated_at=("updated_at", "first"),
        total_ai_cost=("ai_api_cost", "sum"),
        peak_tickets=("support_tickets_opened", "max"),
        ever_over_limit=("is_over_limit", "any"),
    )
)


# ===========================================================================
# 5. KHU VỰC 1 - THẺ CHỈ SỐ KPI CỐT LÕI
# ===========================================================================
st.subheader("1️⃣ Chỉ số kinh doanh cốt lõi")

last_month = df["usage_month"].max()
df_last = df[df["usage_month"] == last_month]

# MRR: doanh thu tháng gần nhất từ khách Active hoặc Upgraded
paying_last = df_last[df_last["status"].isin(["Active", "Upgraded"])]
mrr = float(paying_last["monthly_price"].sum())

# MRR tháng trước để tính delta
months_sorted = sorted(df["usage_month"].unique())
if len(months_sorted) >= 2:
    prev_month = months_sorted[-2]
    prev_paying = df[
        (df["usage_month"] == prev_month) & (df["status"].isin(["Active", "Upgraded"]))
    ]
    mrr_prev = float(prev_paying["monthly_price"].sum())
    mrr_delta = f"{(mrr - mrr_prev) / mrr_prev * 100:+.1f}% so với tháng trước" if mrr_prev else None
else:
    mrr_delta = None

# Churn Rate = số khách Churned / tổng số khách
total_customers = int(cust["customer_id"].nunique())
churned_customers = int((cust["status"] == "Churned").sum())
churn_rate = churned_customers / total_customers * 100 if total_customers else 0.0

# Net AI Profitability Margin = tổng giá gói thu được - tổng chi phí API AI
gross_plan_revenue = float(df["monthly_price"].sum())
total_ai_cost = float(df["ai_api_cost"].sum())
net_margin = gross_plan_revenue - total_ai_cost
margin_pct = net_margin / gross_plan_revenue * 100 if gross_plan_revenue else 0.0

# Avg Support Tickets / khách / tháng
avg_tickets = float(df["support_tickets_opened"].mean())

k1, k2, k3, k4 = st.columns(4)
k1.metric(
    f"💵 MRR ({last_month:%m/%Y})",
    f"${mrr:,.0f}",
    delta=mrr_delta,
    help="Doanh thu lặp lại hàng tháng từ khách Active + Upgraded của tháng gần nhất.",
)
k2.metric(
    "🚪 Churn Rate",
    f"{churn_rate:.1f}%",
    delta=f"{churned_customers}/{total_customers} khách rời bỏ",
    delta_color="inverse",
    help="Số khách Churned / Tổng số khách trong phạm vi đang lọc.",
)
k3.metric(
    "📈 Net AI Profitability",
    f"${net_margin:,.0f}",
    delta=f"Biên {margin_pct:.1f}% · Chi phí AI ${total_ai_cost:,.0f}",
    delta_color="normal" if margin_pct >= 40 else "inverse",
    help="Tổng giá gói thu được − Tổng chi phí API AI phải trả (toàn kỳ lọc).",
)
k4.metric(
    "🎧 Avg Support Tickets",
    f"{avg_tickets:.2f}",
    delta=f"Ngưỡng cảnh báo: > {min_tickets}",
    delta_color="off",
    help="Số ticket trung bình mỗi khách hàng mở trong một tháng.",
)

if margin_pct < 40:
    st.warning(
        f"⚠️ Biên lợi nhuận sau chi phí AI chỉ còn **{margin_pct:.1f}%** — "
        "chi phí API đang ăn mòn doanh thu gói. Xem biểu đồ phân tán bên dưới để khoanh vùng khách hàng vượt hạn mức."
    )

st.divider()


# ===========================================================================
# 6. KHU VỰC 2 - TRỰC QUAN HÓA (4 BIỂU ĐỒ PLOTLY)
# ===========================================================================
st.subheader("2️⃣ Trực quan hóa dữ liệu")

# --- Biểu đồ 1: Line - Xu hướng MRR & Churn Rate theo tháng ---------------
monthly = (
    df[df["status"].isin(["Active", "Upgraded"])]
    .groupby("usage_month", as_index=False)["monthly_price"]
    .sum()
    .rename(columns={"monthly_price": "mrr"})
)
active_per_month = (
    df.groupby("usage_month")["customer_id"].nunique().rename("active_customers")
)
churn_per_month = (
    cust[cust["status"] == "Churned"]
    .assign(churn_month=lambda d: d["updated_at"].dt.to_period("M").dt.to_timestamp())
    .groupby("churn_month")["customer_id"]
    .nunique()
    .rename("churned")
)
trend = (
    pd.DataFrame(index=sorted(df["usage_month"].unique()))
    .join(monthly.set_index("usage_month"))
    .join(active_per_month)
    .join(churn_per_month)
    .fillna({"mrr": 0, "churned": 0})
)
trend["churn_rate"] = (trend["churned"] / trend["active_customers"] * 100).fillna(0)
trend = trend.reset_index(names="usage_month")

worst = trend.loc[trend["churn_rate"].idxmax()]
fig1 = make_subplots(specs=[[{"secondary_y": True}]])
fig1.add_trace(
    go.Bar(
        x=trend["usage_month"],
        y=trend["mrr"],
        name="MRR (USD)",
        marker_color=C_REVENUE,
        opacity=0.85,
        hovertemplate="%{x|%m/%Y}<br>MRR: $%{y:,.0f}<extra></extra>",
    ),
    secondary_y=False,
)
fig1.add_trace(
    go.Scatter(
        x=trend["usage_month"],
        y=trend["churn_rate"],
        name="Churn Rate (%)",
        mode="lines+markers",
        line=dict(color=C_CHURN, width=3),
        marker=dict(size=9),
        hovertemplate="%{x|%m/%Y}<br>Churn: %{y:.1f}%<extra></extra>",
    ),
    secondary_y=True,
)
fig1.update_layout(
    title=dict(
        text=f"<b>MRR tăng đều nhưng churn đạt đỉnh {worst['churn_rate']:.1f}% "
        f"vào {pd.Timestamp(worst['usage_month']):%m/%Y}</b>"
    ),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(t=90, b=20, l=10, r=10),
    height=420,
)
fig1.update_yaxes(title_text="MRR (USD)", secondary_y=False)
fig1.update_yaxes(title_text="Churn Rate (%)", secondary_y=True, showgrid=False)
st.plotly_chart(fig1, use_container_width=True)

col1, col2 = st.columns(2, gap="large")

# --- Biểu đồ 2: Scatter - Tokens vs Chi phí AI, màu theo gói --------------
with col1:
    over_share = df["is_over_limit"].mean() * 100
    df_scatter = df.assign(
        token_status=df["is_over_limit"].map(
            {True: "Vượt hạn mức", False: "Trong hạn mức"}
        )
    )
    fig2 = px.scatter(
        df_scatter,
        x="tokens_consumed",
        y="ai_api_cost",
        color="plan_name",
        symbol="token_status",
        size="support_tickets_opened",
        size_max=16,
        category_orders={
            "plan_name": PLAN_ORDER,
            "token_status": ["Trong hạn mức", "Vượt hạn mức"],
        },
        color_discrete_map=PLAN_COLORS,
        hover_data={
            "customer_name": True,
            "company_size": True,
            "usage_month": "|%m/%Y",
            "ai_token_limit": ":,",
            "net_margin": ":.2f",
            "token_status": True,
        },
        labels={
            "tokens_consumed": "AI Tokens tiêu thụ",
            "ai_api_cost": "Chi phí API AI (USD)",
            "plan_name": "Gói dịch vụ",
            "token_status": "Tình trạng token",
        },
        title=f"<b>{over_share:.0f}% tháng-khách vượt hạn mức token, đẩy chi phí API lên phi tuyến</b>",
    )
    fig2.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, x=0),
        margin=dict(t=80, b=10, l=10, r=10),
        height=460,
    )
    st.plotly_chart(fig2, use_container_width=True)

# --- Biểu đồ 3: Bar - Lý do hủy dịch vụ phổ biến nhất ---------------------
with col2:
    churned = cust[(cust["status"] == "Churned") & cust["churn_reason"].notna()]
    if churned.empty:
        st.info("Không có khách hàng `Churned` nào trong phạm vi lọc hiện tại.")
    else:
        reasons = (
            churned.groupby("churn_reason", as_index=False)
            .agg(customers=("customer_id", "nunique"))
            .sort_values("customers", ascending=True)
        )
        reasons["share"] = reasons["customers"] / reasons["customers"].sum() * 100
        top_reason = reasons.iloc[-1]
        fig3 = px.bar(
            reasons,
            x="customers",
            y="churn_reason",
            orientation="h",
            text=reasons.apply(lambda r: f"{r['customers']:.0f} ({r['share']:.0f}%)", axis=1),
            color="customers",
            color_continuous_scale=["#FCA5A5", C_CHURN],
            labels={"customers": "Số khách rời bỏ", "churn_reason": ""},
            title=f"<b>\"{top_reason['churn_reason']}\" là lý do hủy số 1 "
            f"({top_reason['share']:.0f}% ca churn)</b>",
        )
        fig3.update_traces(textposition="outside", cliponaxis=False)
        fig3.update_layout(
            coloraxis_showscale=False,
            margin=dict(t=80, b=10, l=10, r=40),
            height=460,
        )
        st.plotly_chart(fig3, use_container_width=True)

# --- Biểu đồ 4: Heatmap - Phân bố rủi ro Churn theo quy mô công ty --------
risk = (
    cust.assign(
        is_churned=lambda d: (d["status"] == "Churned").astype(int),
        token_status=lambda d: d["ever_over_limit"].map(
            {True: "Vượt hạn mức token", False: "Trong hạn mức"}
        ),
    )
    .groupby(["company_size", "token_status"], as_index=False)
    .agg(customers=("customer_id", "nunique"), churned=("is_churned", "sum"))
)
risk["churn_rate"] = risk["churned"] / risk["customers"] * 100

pivot = (
    risk.pivot(index="company_size", columns="token_status", values="churn_rate")
    .reindex([s for s in SIZE_ORDER if s in risk["company_size"].unique()])
)
counts = risk.pivot(index="company_size", columns="token_status", values="customers").reindex(
    pivot.index
)

fig4 = px.imshow(
    pivot,
    text_auto=".1f",
    aspect="auto",
    color_continuous_scale=["#ECFDF5", "#FEF3C7", "#FCA5A5", C_CHURN],
    labels=dict(x="Tình trạng tiêu thụ token", y="Quy mô công ty", color="Churn %"),
    title="<b>Rủi ro churn tập trung ở nhóm Startup vượt hạn mức token</b>",
)
fig4.update_traces(
    customdata=counts.values,
    hovertemplate="%{y} · %{x}<br>Churn rate: %{z:.1f}%<br>Số khách: %{customdata}<extra></extra>",
)
fig4.update_layout(margin=dict(t=70, b=10, l=10, r=10), height=360)
st.plotly_chart(fig4, use_container_width=True)

with st.expander("📊 Bảng số liệu rủi ro churn chi tiết (dữ liệu của heatmap)"):
    st.dataframe(
        risk.sort_values("churn_rate", ascending=False).rename(
            columns={
                "company_size": "Quy mô",
                "token_status": "Tiêu thụ token",
                "customers": "Số khách",
                "churned": "Đã churn",
                "churn_rate": "Churn rate (%)",
            }
        ),
        hide_index=True,
        use_container_width=True,
        column_config={"Churn rate (%)": st.column_config.NumberColumn(format="%.1f%%")},
    )

st.divider()


# ===========================================================================
# 7. KHU VỰC 3 - BẢNG DỮ LIỆU & TÍNH NĂNG TỰ PHỤC VỤ
# ===========================================================================
st.subheader("3️⃣ Tra cứu & Tự phục vụ")

tab_risk, tab_raw = st.tabs(["🚨 Khách hàng nguy cơ Churn cao", "🗂️ Toàn bộ usage log"])

with tab_risk:
    st.caption(
        f"Tiêu chí (áp dụng bằng `GROUP BY ... HAVING` trong SQL): "
        f"token đỉnh **vượt hạn mức gói** HOẶC mở **> {min_tickets} ticket** trong một tháng."
    )

    if df_risk.empty:
        st.success("✅ Không có khách hàng nào vượt ngưỡng rủi ro trong phạm vi lọc.")
        view_risk = df_risk
    else:
        c_a, c_b = st.columns([2, 1])
        kw = c_a.text_input(
            "Tìm theo tên khách hàng", placeholder="Ví dụ: Nova, Helix..."
        )
        sort_by = c_b.selectbox(
            "Sắp xếp theo",
            ["peak_usage_pct", "total_ai_cost", "total_tickets", "net_margin"],
            format_func=lambda c: {
                "peak_usage_pct": "% dùng token đỉnh",
                "total_ai_cost": "Tổng chi phí AI",
                "total_tickets": "Tổng support ticket",
                "net_margin": "Biên lợi nhuận (thấp trước)",
            }[c],
        )

        view_risk = df_risk.copy()
        if kw:
            view_risk = view_risk[
                view_risk["customer_name"].str.contains(kw, case=False, na=False)
            ]
        view_risk = view_risk.sort_values(
            sort_by, ascending=(sort_by == "net_margin")
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Số khách nguy cơ", f"{len(df_risk):,}")
        m2.metric(
            "Trong đó đã churn",
            f"{int((df_risk['status'] == 'Churned').sum()):,}",
            delta_color="inverse",
        )
        m3.metric(
            "Biên lợi nhuận nhóm này",
            f"${df_risk['net_margin'].astype(float).sum():,.0f}",
        )

        st.dataframe(
            view_risk,
            use_container_width=True,
            hide_index=True,
            height=420,
            column_config={
                "customer_id": st.column_config.NumberColumn("ID", format="%d"),
                "customer_name": "Khách hàng",
                "company_size": "Quy mô",
                "plan_name": "Gói",
                "monthly_price": st.column_config.NumberColumn("Giá gói", format="$%.2f"),
                "ai_token_limit": st.column_config.NumberColumn("Hạn mức token", format="%d"),
                "status": "Trạng thái",
                "active_months": st.column_config.NumberColumn("Số tháng", format="%d"),
                "peak_tokens": st.column_config.NumberColumn("Token đỉnh", format="%d"),
                "avg_tokens": st.column_config.NumberColumn("Token TB", format="%d"),
                "total_ai_cost": st.column_config.NumberColumn("Chi phí AI", format="$%.2f"),
                "peak_tickets": st.column_config.NumberColumn("Ticket cao nhất", format="%d"),
                "total_tickets": st.column_config.NumberColumn("Tổng ticket", format="%d"),
                "net_margin": st.column_config.NumberColumn("Biên LN", format="$%.2f"),
                "peak_usage_pct": st.column_config.ProgressColumn(
                    "% hạn mức đã dùng",
                    format="%.0f%%",
                    min_value=0,
                    max_value=float(max(df_risk["peak_usage_pct"].max(), 100)),
                ),
            },
        )

with tab_raw:
    st.dataframe(
        df.drop(columns=["tokens_over"]),
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={
            "usage_month": st.column_config.DateColumn("Tháng", format="MM/YYYY"),
            "ai_api_cost": st.column_config.NumberColumn("Chi phí AI", format="$%.2f"),
            "monthly_price": st.column_config.NumberColumn("Giá gói", format="$%.2f"),
            "net_margin": st.column_config.NumberColumn("Biên LN", format="$%.2f"),
            "tokens_consumed": st.column_config.NumberColumn("Token", format="%d"),
        },
    )

# --- Xuất báo cáo: CSV + Excel nhiều sheet ---------------------------------
st.markdown("##### 📤 Xuất báo cáo")


@st.cache_data(ttl=300, show_spinner=False)
def to_excel(fact: pd.DataFrame, at_risk: pd.DataFrame, trend_df: pd.DataFrame) -> bytes:
    """Đóng gói nhiều bảng thành 1 file Excel (mỗi bảng một sheet)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        fact.to_excel(writer, sheet_name="UsageDetail", index=False)
        at_risk.to_excel(writer, sheet_name="AtRiskCustomers", index=False)
        trend_df.to_excel(writer, sheet_name="MonthlyTrend", index=False)
    return buffer.getvalue()


e1, e2, e3 = st.columns(3)
stamp = f"{start_m:%Y%m}_{end_m:%Y%m}"

e1.download_button(
    "⬇️ Usage log (CSV)",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"saas_usage_{stamp}.csv",
    mime="text/csv",
    use_container_width=True,
)
e2.download_button(
    "⬇️ Khách nguy cơ churn (CSV)",
    data=df_risk.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"saas_at_risk_{stamp}.csv",
    mime="text/csv",
    use_container_width=True,
    disabled=df_risk.empty,
)
e3.download_button(
    "⬇️ Báo cáo tổng hợp (Excel)",
    data=to_excel(df, df_risk, trend),
    file_name=f"saas_ai_report_{stamp}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

# --- SQL Viewer ------------------------------------------------------------
with st.expander("🧩 SQL Viewer — câu lệnh JOIN đang dùng để trích xuất dữ liệu"):
    st.markdown("**1. Truy vấn bảng fact chi tiết** (JOIN 4 bảng + `WHERE 1=1` động)")
    st.code(sql_fact, language="sql")
    st.json({k: str(v) for k, v in params_fact.items()}, expanded=False)

    st.markdown(
        "**2. Truy vấn khách hàng nguy cơ Churn** (`GROUP BY` + `HAVING` trên hàm gom tụ)"
    )
    st.code(sql_risk, language="sql")
    st.json({k: str(v) for k, v in params_risk.items()}, expanded=False)

    st.caption(
        "Mọi giá trị bộ lọc đều truyền qua tham số (`:start_m`, `:sz0`, ...) "
        "thay vì nối chuỗi — chống SQL Injection."
    )

st.divider()


# ===========================================================================
# 8. KHU VỰC 4 - BÁO CÁO INSIGHT & ĐỀ XUẤT HÀNH ĐỘNG (tính động từ dữ liệu)
# ===========================================================================
st.subheader("4️⃣ Insight kinh doanh & Đề xuất hành động")


def churn_rate_of(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    return (frame["status"] == "Churned").mean() * 100


# Insight 1: Startup vượt token vs trong hạn mức
startup = cust[cust["company_size"] == "Startup"]
s_over = churn_rate_of(startup[startup["ever_over_limit"]])
s_in = churn_rate_of(startup[~startup["ever_over_limit"]])
ratio = s_over / s_in if s_in else float("inf")

# Insight 2: biên lợi nhuận theo gói
by_plan = (
    df.groupby("plan_name", as_index=False)
    .agg(
        revenue=("monthly_price", "sum"),
        ai_cost=("ai_api_cost", "sum"),
        rows=("customer_id", "size"),
    )
    .assign(
        margin=lambda d: d["revenue"] - d["ai_cost"],
        margin_pct=lambda d: (d["revenue"] - d["ai_cost"]) / d["revenue"] * 100,
    )
    .sort_values("margin_pct")
)
worst_plan = by_plan.iloc[0]

# Insight 3: tác động của support ticket
hi = cust[cust["peak_tickets"] > min_tickets]
lo = cust[cust["peak_tickets"] <= min_tickets]

i1, i2, i3 = st.columns(3)
with i1:
    st.error(
        f"**🔥 Insight 1 — Overage token là nguyên nhân churn số 1 của Startup**\n\n"
        f"Startup **vượt hạn mức token** churn **{s_over:.1f}%**, so với "
        f"**{s_in:.1f}%** ở nhóm dùng trong hạn mức — "
        f"cao hơn **{ratio:.1f} lần**."
    )
with i2:
    st.warning(
        f"**💸 Insight 2 — Gói `{worst_plan['plan_name']}` có biên lợi nhuận mỏng nhất**\n\n"
        f"Chi phí AI ăn **{100 - worst_plan['margin_pct']:.1f}%** doanh thu gói này, "
        f"biên chỉ còn **{worst_plan['margin_pct']:.1f}%** "
        f"(${worst_plan['margin']:,.0f} trên ${worst_plan['revenue']:,.0f}) — "
        f"thấp nhất trong {len(by_plan)} gói."
    )
with i3:
    st.info(
        f"**🎧 Insight 3 — Support ticket là tín hiệu cảnh báo sớm**\n\n"
        f"Khách từng mở **> {min_tickets} ticket/tháng** churn **{churn_rate_of(hi):.1f}%**, "
        f"so với **{churn_rate_of(lo):.1f}%** ở nhóm còn lại "
        f"({len(hi)} vs {len(lo)} khách)."
    )

st.markdown(
    f"""
##### 🎯 Đề xuất hành động

**Cho Product / Pricing**
1. **Thêm bậc token linh hoạt (token add-on) cho gói `{worst_plan['plan_name']}`:** bán thêm
   token theo khối lượng thay vì để khách vượt hạn mức rồi chịu chi phí phi tuyến — vừa cải thiện
   biên lợi nhuận (hiện chỉ **{worst_plan['margin_pct']:.1f}%**), vừa giảm cú sốc hóa đơn gây churn.
2. **Cảnh báo in-app tại mốc 80% hạn mức** kèm gợi ý nâng gói: nhóm vượt hạn mức có churn
   **{ratio:.1f} lần** cao hơn, nên chặn trước khi hóa đơn tăng vọt là biện pháp rẻ nhất.
3. **Tối ưu chi phí kỹ thuật:** bật caching/prompt ngắn, định tuyến truy vấn đơn giản sang
   model nhỏ hơn để hạ đơn giá token trung bình.

**Cho Customer Success**
4. **Playbook can thiệp theo ngưỡng ticket:** mở > {min_tickets} ticket trong một tháng →
   tự động tạo task gọi khách trong 48h (nhóm này churn **{churn_rate_of(hi):.1f}%**).
5. **Ưu tiên danh sách ở tab "Khách hàng nguy cơ Churn cao"** ({len(df_risk)} khách):
   sắp xếp theo *% hạn mức đã dùng* để chăm sóc nhóm sát ngưỡng trước.
6. **Khảo sát lý do hủy** tập trung vào nhóm lý do liên quan chi phí — đây là nhóm lý do
   dẫn đầu, và cũng là nhóm doanh nghiệp **có thể tự điều chỉnh được** bằng chính sách giá.
"""
)

st.caption(
    "Mọi con số trong phần Insight được tính trực tiếp từ dữ liệu đang lọc — "
    "đổi bộ lọc ở sidebar, các kết luận sẽ tự cập nhật."
)
