import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import date
import pandas as pd

# --- COPY LẠI CÁC CLASS LOGIC CỦA BẠN VÀO ĐÂY ---
# (Giữ nguyên các class: Asset, Stock, Bond, Position, Portfolio, UserProfile, resolve_stock_ticker)
# Lưu ý: Trong class Asset, hãy sửa lại để nhận current_price từ yfinance nếu cần.

# --- HÀM HỖ TRỢ GIAO DIỆN ---
def get_live_price(ticker):
    try:
        data = yf.Ticker(ticker).fast_info
        return float(data['lastPrice'])
    except:
        return 0.0

# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="Investment Dashboard", layout="wide")

st.title("📊 Investment Portfolio Dashboard")

# 1. Sidebar - Thiết lập Profile
st.sidebar.header("👤 User Profile Setup")
name = st.sidebar.text_input("Investor Name", "User")
dob = st.sidebar.date_input("Date of Birth", date(2000, 1, 1))
risk = st.sidebar.slider("Risk Tolerance (1-5)", 1, 5, 3)
goal = st.sidebar.number_input("Savings Goal ($)", min_value=0.0, value=10000.0)
initial_cash = st.sidebar.number_input("Initial Cash ($)", min_value=0.0, value=5000.0)
strategy = st.sidebar.selectbox("Strategy", ["classical", "buffett", "graham"])

# Khởi tạo Portfolio trong Session State (để không bị mất dữ liệu khi load lại trang)
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = Portfolio(initial_cash)
if 'user' not in st.session_state:
    st.session_state.user = UserProfile(name, str(dob), risk, goal, strategy)

port = st.session_state.portfolio
user = st.session_state.user

# 2. Tabs chức năng
tab1, tab2, tab3 = st.tabs(["📈 Giao dịch", "💰 Danh mục", "📊 Phân tích kỹ thuật"])

with tab1:
    st.header("Mua/Bán tài sản")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Mua tài sản")
        buy_ticker = st.text_input("Nhập Ticker (vídụ: AAPL)").upper()
        buy_qty = st.number_input("Số lượng mua", min_value=1, step=1)
        asset_type = st.selectbox("Loại tài sản", ["Stock", "Bond", "Derivative"])
        
        if st.button("Xác nhận Mua"):
            ticker_resolved = resolve_stock_ticker(buy_ticker)
            if ticker_resolved:
                price = get_live_price(ticker_resolved)
                if asset_type == "Derivative" and not user.is_derivative_allowed():
                    st.error("Rủi ro quá cao! Tài khoản của bạn không được phép mua Derivative.")
                else:
                    try:
                        # Giả định dùng class Stock cho đơn giản
                        asset = Stock(ticker_resolved, price, "General")
                        port.buy(asset, buy_qty)
                        st.success(f"Đã mua {buy_qty} {ticker_resolved} tại giá ${price}")
                    except InsufficientFundsError as e:
                        st.error(e)
            else:
                st.error("Không tìm thấy mã chứng khoán.")

    with col2:
        st.subheader("Bán tài sản")
        sell_ticker = st.text_input("Nhập Ticker muốn bán").upper()
        sell_qty = st.number_input("Số lượng bán", min_value=1, step=1)
        if st.button("Xác nhận Bán"):
            try:
                port.sell_asset(sell_ticker, sell_qty)
                st.success(f"Đã bán {sell_qty} {sell_ticker}")
            except Exception as e:
                st.error(e)

with tab2:
    st.header("Chi tiết danh mục")
    st.metric("Số dư tiền mặt", f"${port.cash_balance:,.2f}")
    
    if port.positions:
        # Hiển thị bảng danh mục
        data = []
        for t, pos in port.positions.items():
            live_p = get_live_price(t)
            data.append({
                "Ticker": t,
                "Số lượng": pos.quantity,
                "Giá TB": f"${pos.avg_buy_price:.2f}",
                "Giá hiện tại": f"${live_p:.2f}",
                "P&L": f"${(live_p - pos.avg_buy_price) * pos.quantity:.2f}"
            })
        st.table(pd.DataFrame(data))
        
        # Vẽ biểu đồ tròn
        fig, ax = plt.subplots()
        weights = port.get_portfolio_weights()
        ax.pie(weights.values(), labels=weights.keys(), autopct='%1.1f%%')
        st.pyplot(fig)
    else:
        st.info("Danh mục hiện đang trống.")

with tab3:
    st.header("Biểu đồ lịch sử")
    chart_ticker = st.text_input("Nhập mã để xem biểu đồ", "AAPL").upper()
    if st.button("Xem biểu đồ"):
        hist_data = yf.download(chart_ticker, period="6mo")
        if not hist_data.empty:
            st.line_chart(hist_data['Close'])
        else:
            st.error("Không có dữ liệu.")
