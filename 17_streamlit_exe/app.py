"""
BÀI TẬP 17 - LÀM VIỆC VỚI STREAMLIT
Dashboard Phân tích Doanh số & Hành vi Mua hàng E-Commerce (CSDL EcommerceDB - bài tập 10).

Chạy ứng dụng:
    streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

try:  # Nạp biến môi trường từ file .env nếu có python-dotenv
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ----------------------------------------------------------------------------
# 0. CẤU HÌNH TRANG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="E-Commerce Sales Dashboard",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLOR_PRIMARY = "#2563EB"   # xanh - doanh thu
COLOR_ACCENT = "#F59E0B"    # cam - sản phẩm bán chạy


# ----------------------------------------------------------------------------
# 1. KẾT NỐI CSDL (cache_resource: chỉ tạo engine 1 lần cho cả phiên)
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Đang kết nối MySQL...")
def get_engine() -> Engine:
    """Tạo SQLAlchemy Engine. Ưu tiên st.secrets, sau đó biến môi trường."""
    try:
        cfg = dict(st.secrets.get("mysql", {}))
    except Exception:  # không có .streamlit/secrets.toml -> dùng .env
        cfg = {}

    host = cfg.get("host") or os.getenv("DB_HOST", "localhost")
    port = int(cfg.get("port") or os.getenv("DB_PORT", 3306))
    user = cfg.get("user") or os.getenv("DB_USER", "root")
    password = cfg.get("password") or os.getenv("DB_PASSWORD", "")
    database = cfg.get("database") or os.getenv("DB_NAME", "EcommerceDB")

    url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)

    # Kiểm tra kết nối ngay để báo lỗi sớm, rõ ràng
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Chạy SELECT và trả về DataFrame. Kết quả được cache 5 phút."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def in_clause(values: list, prefix: str) -> tuple[str, dict]:
    """Sinh mệnh đề IN có tham số hóa an toàn: (:p0, :p1, ...)."""
    keys = [f"{prefix}{i}" for i in range(len(values))]
    placeholders = ", ".join(f":{k}" for k in keys)
    return f"({placeholders})", dict(zip(keys, values))


# ----------------------------------------------------------------------------
# 2. TRUY VẤN LẤY DỮ LIỆU CHO BỘ LỌC
# ----------------------------------------------------------------------------
SQL_FILTER_OPTIONS = """
SELECT MIN(order_date) AS min_date, MAX(order_date) AS max_date
FROM Orders
"""

SQL_STATUSES = "SELECT DISTINCT status FROM Orders ORDER BY status"
SQL_CITIES = "SELECT DISTINCT city FROM Customers ORDER BY city"
SQL_CATEGORIES = "SELECT DISTINCT category_name FROM Categories ORDER BY category_name"


# ----------------------------------------------------------------------------
# 3. TRUY VẤN CHÍNH - BẢNG FACT CHI TIẾT (JOIN 5 BẢNG + WHERE 1=1 ĐỘNG)
# ----------------------------------------------------------------------------
def build_fact_query(
    start: date,
    end: date,
    statuses: list[str],
    cities: list[str],
    categories: list[str],
) -> tuple[str, dict]:
    """Dựng câu SQL động theo bộ lọc. Mẫu WHERE 1=1 giúp nối thêm điều kiện dễ dàng."""
    sql = """
SELECT  o.order_id,
        o.order_date,
        o.status,
        cu.customer_name,
        cu.city,
        c.category_name,
        p.product_name,
        od.quantity,
        od.unit_price,
        (od.quantity * od.unit_price) AS line_revenue
FROM Orders o
JOIN Customers    cu ON cu.customer_id = o.customer_id
JOIN OrderDetails od ON od.order_id    = o.order_id
JOIN Products     p  ON p.product_id   = od.product_id
JOIN Categories   c  ON c.category_id  = p.category_id
WHERE 1 = 1
  AND o.order_date BETWEEN :start_date AND :end_date
"""
    params: dict = {"start_date": start, "end_date": end}

    if statuses:
        clause, p = in_clause(statuses, "st")
        sql += f"  AND o.status IN {clause}\n"
        params.update(p)

    if cities:
        clause, p = in_clause(cities, "ci")
        sql += f"  AND cu.city IN {clause}\n"
        params.update(p)

    if categories:
        clause, p = in_clause(categories, "ca")
        sql += f"  AND c.category_name IN {clause}\n"
        params.update(p)

    sql += "ORDER BY o.order_date DESC, o.order_id DESC"
    return sql, params


# ----------------------------------------------------------------------------
# 4. SIDEBAR - THANH BỘ LỌC
# ----------------------------------------------------------------------------
st.sidebar.title("🔎 Bộ lọc dữ liệu")

try:
    bounds = run_query(SQL_FILTER_OPTIONS)
    all_statuses = run_query(SQL_STATUSES)["status"].tolist()
    all_cities = run_query(SQL_CITIES)["city"].tolist()
    all_categories = run_query(SQL_CATEGORIES)["category_name"].tolist()
except SQLAlchemyError as exc:
    st.error("❌ Không kết nối được MySQL. Hãy kiểm tra lại cấu hình trong `.env` / `secrets.toml`.")
    st.code(str(exc.__cause__ or exc), language="text")
    st.info(
        "Checklist: (1) MySQL đang chạy? (2) Đã tạo CSDL `EcommerceDB` bằng "
        "`sql/01_ecommerce_schema_seed.sql`? (3) User/password đúng chưa?"
    )
    st.stop()

min_date = bounds.loc[0, "min_date"] or date.today()
max_date = bounds.loc[0, "max_date"] or date.today()

date_range = st.sidebar.date_input(
    "Khoảng thời gian đặt hàng",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    help="Chọn ngày bắt đầu và ngày kết thúc.",
)

# date_input trả về tuple 1 phần tử khi người dùng mới click ngày đầu tiên
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range if not isinstance(date_range, (list, tuple)) else date_range[0]

sel_statuses = st.sidebar.multiselect(
    "Trạng thái đơn hàng",
    options=all_statuses,
    default=["Completed"] if "Completed" in all_statuses else all_statuses,
)

sel_cities = st.sidebar.multiselect("Thành phố", options=all_cities, default=[])
sel_categories = st.sidebar.multiselect("Danh mục sản phẩm", options=all_categories, default=[])

st.sidebar.caption("Để trống một bộ lọc = chọn tất cả giá trị của bộ lọc đó.")

if st.sidebar.button("🔄 Làm mới dữ liệu (xóa cache)", use_container_width=True):
    st.cache_data.clear()
    st.rerun()


# ----------------------------------------------------------------------------
# 5. LẤY DỮ LIỆU THEO BỘ LỌC
# ----------------------------------------------------------------------------
sql_fact, params_fact = build_fact_query(
    start_date, end_date, sel_statuses, sel_cities, sel_categories
)

try:
    df = run_query(sql_fact, params_fact)
except SQLAlchemyError as exc:
    st.error("❌ Lỗi khi truy vấn dữ liệu.")
    st.code(str(exc.__cause__ or exc), language="text")
    st.stop()

st.title("🛒 Dashboard Phân tích Doanh số & Hành vi Mua hàng")
st.caption(
    f"Dữ liệu từ **{start_date:%d/%m/%Y}** đến **{end_date:%d/%m/%Y}** · "
    f"Trạng thái: **{', '.join(sel_statuses) if sel_statuses else 'Tất cả'}** · "
    f"{len(df):,} dòng chi tiết"
)

if df.empty:
    st.warning("⚠️ Không có dữ liệu nào khớp với bộ lọc hiện tại. Hãy nới rộng điều kiện lọc.")
    st.stop()


# ----------------------------------------------------------------------------
# 6. KHU VỰC 1 - THẺ CHỈ SỐ (METRICS)
# ----------------------------------------------------------------------------
total_revenue = float(df["line_revenue"].sum())
total_orders = int(df["order_id"].nunique())
total_quantity = int(df["quantity"].sum())
aov = total_revenue / total_orders if total_orders else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 Tổng doanh thu", f"${total_revenue:,.2f}")
k2.metric("🧾 Số đơn hàng", f"{total_orders:,}")
k3.metric("📊 Giá trị TB/đơn (AOV)", f"${aov:,.2f}")
k4.metric("📦 Tổng sản phẩm bán ra", f"{total_quantity:,}")

st.divider()


# ----------------------------------------------------------------------------
# 7. KHU VỰC 2 - TRỰC QUAN HÓA
# ----------------------------------------------------------------------------
col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    revenue_by_day = (
        df.groupby("order_date", as_index=False)["line_revenue"]
        .sum()
        .sort_values("order_date")
        .rename(columns={"line_revenue": "revenue"})
    )
    peak = revenue_by_day.loc[revenue_by_day["revenue"].idxmax()]
    fig_line = px.line(
        revenue_by_day,
        x="order_date",
        y="revenue",
        markers=True,
        title=f"Doanh thu đạt đỉnh ${peak['revenue']:,.0f} vào ngày {peak['order_date']:%d/%m}",
        labels={"order_date": "Ngày đặt hàng", "revenue": "Doanh thu (USD)"},
    )
    fig_line.update_traces(line_color=COLOR_PRIMARY, line_width=3)
    fig_line.update_layout(hovermode="x unified", margin=dict(t=60, b=10, l=10, r=10))
    st.plotly_chart(fig_line, use_container_width=True)

with col_right:
    top_products = (
        df.groupby("product_name", as_index=False)
        .agg(total_quantity=("quantity", "sum"), revenue=("line_revenue", "sum"))
        .sort_values("total_quantity", ascending=False)
        .head(5)
    )
    fig_bar = px.bar(
        top_products.sort_values("total_quantity"),
        x="total_quantity",
        y="product_name",
        orientation="h",
        text="total_quantity",
        title=f"Top 5 bán chạy: {top_products.iloc[0]['product_name']} dẫn đầu",
        labels={"total_quantity": "Số lượng bán", "product_name": ""},
        custom_data=["revenue"],
    )
    fig_bar.update_traces(
        marker_color=COLOR_ACCENT,
        textposition="outside",
        hovertemplate="%{y}<br>Số lượng: %{x}<br>Doanh thu: $%{customdata[0]:,.2f}<extra></extra>",
    )
    fig_bar.update_layout(margin=dict(t=60, b=10, l=10, r=10))
    st.plotly_chart(fig_bar, use_container_width=True)

# Biểu đồ bổ sung: doanh thu theo danh mục & theo thành phố
col_a, col_b = st.columns(2, gap="large")

with col_a:
    by_category = (
        df.groupby("category_name", as_index=False)["line_revenue"]
        .sum()
        .sort_values("line_revenue", ascending=False)
    )
    fig_cat = px.bar(
        by_category,
        x="category_name",
        y="line_revenue",
        title="Doanh thu theo danh mục sản phẩm",
        labels={"category_name": "Danh mục", "line_revenue": "Doanh thu (USD)"},
        color="line_revenue",
        color_continuous_scale="Blues",
    )
    fig_cat.update_layout(coloraxis_showscale=False, margin=dict(t=60, b=10, l=10, r=10))
    st.plotly_chart(fig_cat, use_container_width=True)

with col_b:
    by_city = (
        df.groupby("city", as_index=False)["line_revenue"]
        .sum()
        .sort_values("line_revenue", ascending=False)
    )
    fig_city = px.pie(
        by_city,
        names="city",
        values="line_revenue",
        hole=0.45,
        title="Tỷ trọng doanh thu theo thành phố",
    )
    fig_city.update_traces(textinfo="label+percent")
    fig_city.update_layout(margin=dict(t=60, b=10, l=10, r=10))
    st.plotly_chart(fig_city, use_container_width=True)

st.divider()


# ----------------------------------------------------------------------------
# 8. KHU VỰC 3 - BẢNG CHI TIẾT & XUẤT DỮ LIỆU
# ----------------------------------------------------------------------------
st.subheader("📋 Bảng dữ liệu chi tiết")

search = st.text_input(
    "Tìm kiếm (khách hàng / sản phẩm / thành phố)",
    placeholder="Ví dụ: Nguyen, Laptop, Ha Noi...",
)

view = df.copy()
if search:
    mask = (
        view["customer_name"].str.contains(search, case=False, na=False)
        | view["product_name"].str.contains(search, case=False, na=False)
        | view["city"].str.contains(search, case=False, na=False)
    )
    view = view[mask]

st.dataframe(
    view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "order_id": st.column_config.NumberColumn("Mã đơn", format="%d"),
        "order_date": st.column_config.DateColumn("Ngày đặt", format="DD/MM/YYYY"),
        "status": "Trạng thái",
        "customer_name": "Khách hàng",
        "city": "Thành phố",
        "category_name": "Danh mục",
        "product_name": "Sản phẩm",
        "quantity": st.column_config.NumberColumn("SL", format="%d"),
        "unit_price": st.column_config.NumberColumn("Đơn giá", format="$%.2f"),
        "line_revenue": st.column_config.NumberColumn("Doanh thu dòng", format="$%.2f"),
    },
)

st.download_button(
    "⬇️ Tải dữ liệu đã lọc (CSV)",
    data=view.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"ecommerce_report_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
    mime="text/csv",
    use_container_width=False,
)

with st.expander("🧩 Xem câu lệnh SQL đang được sử dụng"):
    st.code(sql_fact, language="sql")
    st.write("**Tham số truyền vào (parameterized - chống SQL Injection):**")
    st.json({k: str(v) for k, v in params_fact.items()})
