import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import date
import pandas as pd
from abc import ABC, abstractmethod

# ==========================================
# 1. CUSTOM EXCEPTIONS & LOGIC FUNCTIONS
# ==========================================
class InsufficientFundsError(Exception): pass
class InsufficientSharesError(Exception): pass

def resolve_stock_ticker(user_input):
    query = user_input.strip().upper()
    if 1 <= len(query) <= 5:
        return query
    try:
        search = yf.Search(query, max_results=1)
        for result in search.quotes:
            if result.get('quoteType') == 'EQUITY':
                return result['symbol']
    except:
        pass
    return None

# ==========================================
# 2. CORE CLASSES (BACKEND)
# ==========================================
class Asset(ABC):
    def __init__(self, ticker, current_price):
        self.ticker = ticker
        self.current_price = current_price
    @abstractmethod
    def get_asset_type(self) -> str: pass

class Stock(Asset):
    def __init__(self, ticker, current_price, sector="General"):
        super().__init__(ticker, current_price)
        self.sector = sector
    def get_asset_type(self): return "Stock"

class Bond(Asset):
    def __init__(self, ticker, current_price, coupon_rate=5.0):
        super().__init__(ticker, current_price)
        self.coupon_rate = coupon_rate
    def get_asset_type(self): return "Bond"

class Derivatives(Asset):
    def __init__(self, ticker, underlying):
        super().__init__(ticker, 0.0)
        self.underlying = underlying
    def get_asset_type(self): return "Derivative"

class Position:
    def __init__(self, asset, quantity, avg_buy_price):
        self.asset = asset
        self.quantity = quantity
        self.avg_buy_price = avg_buy_price
    def market_value(self): return self.quantity * self.asset.current_price
    def pnl(self): return (self.asset.current_price - self.avg_buy_price) * self.quantity
    def update_position(self, extra_qty, price):
        total_cost = (self.quantity * self.avg_buy_price) + (extra_qty * price)
        self.quantity += extra_qty
        self.avg_buy_price = total_cost / self.quantity

class Portfolio:
    def __init__(self, initial_cash):
        self.cash_balance = initial_cash
        self.positions = {}
    def buy(self, asset, quantity):
        cost = asset.current_price * quantity
        if cost > self.cash_balance:
            raise InsufficientFundsError(f"Cần ${cost:,.2f}, nhưng bạn chỉ có ${self.cash_balance:,.2f}")
        self.cash_balance -= cost
        if asset.ticker in self.positions:
            self.positions[asset.ticker].update_position(quantity, asset.current_price)
        else:
            self.positions[asset.ticker] = Position(asset, quantity, asset.current_price)
    def sell_asset(self, ticker, quantity):
        if ticker not in self.positions or self.positions[ticker].quantity < quantity:
            raise InsufficientSharesError(f"Không đủ cổ phiếu {ticker} để bán.")
        pos = self.positions[ticker]
        self.cash_balance += quantity * pos.asset.current_price
        pos.quantity -= quantity
        if pos.quantity == 0: del self.positions[ticker]

class UserProfile:
    def __init__(self, name, dob_str, risk_level, savings_goal, strategy="classical"):
        self.name = name
        self.dob = date.fromisoformat(dob_str)
        self.risk_level = risk_level
        self.savings_goal = savings_goal
        self.strategy = strategy
    @property
    def age(self):
        today = date.today()
        return today.year - self.dob.year
    def get_target_weights(self):
        if self.strategy == "buffett": return {"Stocks": 90, "Cash/Bonds": 10}
        if self.strategy == "graham": return {"Stocks": 50, "Bonds": 50}
        equity = max(100 - self.age, 20)
        return {"Stocks": equity, "Fixed Income": 100 - equity}
    def is_derivative_allowed(self): return self.risk_level >= 4

# ==========================================
# 3. STREAMLIT UI (FRONTEND)
# ==========================================
st.set_page_config(page_title="Hệ thống Quản lý Đầu tư", layout="wide")

def get_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        return float(t.fast_info['lastPrice'])
    except: return 0.0

# Sidebar Setup
st.sidebar.header("👤 Cài đặt Người dùng")
u_name = st.sidebar.text_input("Tên nhà đầu tư", "Học viên UEH")
u_dob = st.sidebar.date_input("Ngày sinh", date(2000, 1, 1))
u_risk = st.sidebar.slider("Mức độ rủi ro (1-5)", 1, 5, 3)
u_goal = st.sidebar.number_input("Mục tiêu tiết kiệm ($)", value=10000.0)
u_cash = st.sidebar.number_input("Vốn ban đầu ($)", value=5000.0)
u_strat = st.sidebar.selectbox("Chiến thuật", ["classical", "buffett", "graham"])

# Lưu trữ trạng thái bằng Session State
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = Portfolio(u_cash)
if 'user' not in st.session_state:
    st.session_state.user = UserProfile(u_name, str(u_dob), u_risk, u_goal, u_strat)

port = st.session_state.portfolio
user = st.session_state.user

# Giao diện chính
st.title("📊 Financial Portfolio Dashboard")
st.write(f"Chào mừng **{user.name}** ({user.age} tuổi) | Chiến thuật: **{user.strategy.upper()}**")

tab1, tab2, tab3 = st.tabs(["🎯 Giao dịch", "💰 Danh mục hiện tại", "📈 Biểu đồ lịch sử"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Mua tài sản")
        t_buy = st.text_input("Nhập mã (Ticker):", key="t_buy").upper()
        q_buy = st.number_input("Số lượng mua:", min_value=1, step=1, key="q_buy")
        a_type = st.selectbox("Phân loại:", ["Stock", "Bond", "Derivative"])
        if st.button("Xác nhận Mua"):
            ticker = resolve_stock_ticker(t_buy)
            if ticker:
                price = get_live_price(ticker)
                if price > 0:
                    if a_type == "Derivative" and not user.is_derivative_allowed():
                        st.error("Rủi ro cấp độ 4 mới được phép giao dịch Phái sinh!")
                    else:
                        try:
                            asset = Stock(ticker, price) if a_type == "Stock" else Bond(ticker, price)
                            port.buy(asset, q_buy)
                            st.success(f"Đã mua {q_buy} {ticker} tại giá ${price:,.2f}")
                        except InsufficientFundsError as e: st.error(e)
                else: st.error("Không lấy được giá thị trường.")
            else: st.error("Mã không hợp lệ.")

    with c2:
        st.subheader("Bán tài sản")
        t_sell = st.text_input("Mã muốn bán:", key="t_sell").upper()
        q_sell = st.number_input("Số lượng bán:", min_value=1, step=1, key="q_sell")
        if st.button("Xác nhận Bán"):
            try:
                port.sell_asset(t_sell, q_sell)
                st.success(f"Đã bán {q_sell} {t_sell}")
            except Exception as e: st.error(e)

with tab2:
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Tiền mặt dư", f"${port.cash_balance:,.2f}")
    
    if port.positions:
        rows = []
        total_nav = port.cash_balance
        for t, pos in port.positions.items():
            current_p = get_live_price(t)
            pos.asset.current_price = current_p
            total_nav += pos.market_value()
            rows.append({
                "Ticker": t, "Số lượng": pos.quantity, 
                "Giá TB": f"${pos.avg_buy_price:.2f}", 
                "Giá hiện tại": f"${current_p:.2f}",
                "Lãi/Lỗ ($)": f"{pos.pnl():.2f}"
            })
        col_m2.metric("Tổng giá trị (NAV)", f"${total_nav:,.2f}")
        st.table(pd.DataFrame(rows))
        
        # Biểu đồ tỷ trọng
        st.subheader("Phân bổ tài sản")
        labels = list(port.positions.keys()) + ["Cash"]
        sizes = [p.market_value() for p in port.positions.values()] + [port.cash_balance]
        fig, ax = plt.subplots()
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        st.pyplot(fig)
    else:
        st.info("Danh mục của bạn chưa có cổ phiếu nào.")

with tab3:
    t_chart = st.text_input("Mã chứng khoán xem lịch sử:", value="AAPL").upper()
    period = st.selectbox("Khoảng thời gian", ["1mo", "3mo", "6mo", "1y", "5y"])
    if st.button("Tải biểu đồ"):
        data = yf.download(t_chart, period=period)
        if not data.empty:
            st.line_chart(data['Close'])
        else: st.warning("Không tìm thấy dữ liệu.")
