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
            raise InsufficientFundsError(f"Required: ${cost:,.2f}, Available: ${self.cash_balance:,.2f}")
        self.cash_balance -= cost
        if asset.ticker in self.positions:
            self.positions[asset.ticker].update_position(quantity, asset.current_price)
        else:
            self.positions[asset.ticker] = Position(asset, quantity, asset.current_price)
    def sell_asset(self, ticker, quantity):
        if ticker not in self.positions or self.positions[ticker].quantity < quantity:
            raise InsufficientSharesError(f"Insufficient shares of {ticker}.")
        pos = self.positions[ticker]
        self.cash_balance += quantity * pos.asset.current_price
        pos.quantity -= quantity
        if pos.quantity == 0: del self.positions[ticker]

class UserProfile:
    def __init__(self, name, dob_str, risk_level, savings_goal, strategy="classical"):
        self.name = name
        self.dob = dob_str if isinstance(dob_str, date) else date.fromisoformat(str(dob_str))
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
st.set_page_config(page_title="Investment Management System", layout="wide")

def get_market_info(ticker):
    try:
        t = yf.Ticker(ticker)
        # Lấy giá và loại tài sản chính xác từ Yahoo Finance
        price = float(t.fast_info['lastPrice'])
        # quoteType: EQUITY, ETF, FUTURE, CURRENCY, etc.
        mkt_type = t.info.get('quoteType', 'UNKNOWN')
        return price, mkt_type
    except:
        return None, None
        
def get_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        return float(t.fast_info['lastPrice'])
    except: return 0.0

# Sidebar Settings
st.sidebar.header("👤 User Profile Settings")
u_name = st.sidebar.text_input("Investor Name", "Name")
u_dob = st.sidebar.date_input("Date of Birth", date(2000, 1, 1))
u_risk = st.sidebar.slider("Risk Level (1-5)", 1, 5, 3)
u_goal = st.sidebar.number_input("Savings Goal ($)", value=10000.0)
u_cash = st.sidebar.number_input("Initial Cash ($)", value=5000.0)
u_strat = st.sidebar.selectbox("Investment Strategy", ["Classical", "Buffett", "Graham"])

# Session State Management & Data Sync
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = Portfolio(u_cash)

if 'user' not in st.session_state:
    st.session_state.user = UserProfile(u_name, u_dob, u_risk, u_goal, u_strat)
else:
    # Sync Sidebar changes to the dashboard instantly
    st.session_state.user.name = u_name
    st.session_state.user.dob = u_dob
    st.session_state.user.risk_level = u_risk
    st.session_state.user.strategy = u_strat
    st.session_state.user.savings_goal = u_goal

port = st.session_state.portfolio
user = st.session_state.user

# Main Dashboard Header
st.title("📊 Financial Portfolio Dashboard")
st.write(f"Welcome back, **{user.name}** ({user.age} years old) | Strategy: **{user.strategy.upper()}**")

tabs = st.tabs(["🎯 Trading Terminal", "💰 Portfolio Summary", "📈 Market Analysis"])
        
# TAB 1: TRADING TERMINAL
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Buy Assets")
        t_buy = st.text_input("Enter Ticker (e.g., AAPL):", key="t_buy").upper()
        q_buy = st.number_input("Quantity:", min_value=1, step=1, key="q_buy")
        a_type = st.selectbox("Asset Class:", ["Stock", "Bond", "Derivative"])
        if st.button("Confirm Purchase"):
        if t_input:
            price, mkt_type = get_market_info(t_input)
            
            if price:
                # --- LOGIC KIỂM CHỨNG (VALIDATION) ---
                error_msg = ""
                
                # 1. Kiểm tra nếu chọn Bond nhưng mã là Stock
                if user_choice == "Bond" and mkt_type == "EQUITY":
                    error_msg = f"❌ REJECTED: {t_input} is an EQUITY (Stock), you cannot buy it as a Bond."
                
                # 2. Kiểm tra nếu chọn Stock nhưng mã là ETF (Thường là Bond ETF)
                elif user_choice == "Stock" and mkt_type == "ETF":
                    st.warning(f"Note: {t_input} is an ETF. Proceeding as Stock.")
                
                # 3. Kiểm tra Derivative quyền hạn
                elif user_choice == "Derivative":
                    if u_risk < 4:
                        error_msg = "❌ REJECTED: Risk level too low for Derivatives."
                    elif mkt_type not in ["FUTURE", "OPTION", "ETF"]: # ETF có thể là Inverse/Leveraged
                        error_msg = f"❌ REJECTED: {t_input} is {mkt_type}, not a recognized Derivative."

                # --- THỰC THI NẾU KHÔNG CÓ LỖI ---
                if error_msg:
                    st.error(error_msg)
                else:
                    # Tạo đúng loại Object để lưu vào Portfolio
                    if user_choice == "Stock": new_asset = Stock(t_input, price)
                    elif user_choice == "Bond": new_asset = Bond(t_input, price)
                    else: new_asset = Derivative(t_input, price)
                    
                    try:
                        port.buy(new_asset, qty)
                        st.success(f"✅ Success: Bought {qty} {t_input} at ${price:,.2f}")
                    except InsufficientFundsError as e:
                        st.error(e)
            else:
                st.error("Could not find Ticker or fetch price.")

    with c2:
        st.subheader("Sell Assets")
        t_sell = st.text_input("Enter Ticker to Sell:", key="t_sell").upper()
        q_sell = st.number_input("Quantity to Sell:", min_value=1, step=1, key="q_sell")
        if st.button("Confirm Sell"):
            try:
                port.sell_asset(t_sell, q_sell)
                st.success(f"Successfully sold {q_sell} units of {t_sell}")
            except Exception as e: st.error(e)

# TAB 2: PORTFOLIO SUMMARY
with tabs[1]:
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Cash Balance", f"${port.cash_balance:,.2f}")
    
    if port.positions:
        rows = []
        total_assets_value = 0
        for t, pos in port.positions.items():
            current_p = get_live_price(t)
            pos.asset.current_price = current_p
            total_assets_value += pos.market_value()
            
            pnl_val = pos.pnl()
            rows.append({
                "Ticker": t, 
                "Qty": pos.quantity, 
                "Avg Price": f"${pos.avg_buy_price:,.2f}", 
                "Current Price": f"${current_p:,.2f}",
                "P&L ($)": pnl_val
            })
        
        total_nav = port.cash_balance + total_assets_value
        col_m2.metric("Total NAV", f"${total_nav:,.2f}")
        col_m3.metric("Savings Goal", f"${user.savings_goal:,.2f}", f"{((total_nav/user.savings_goal)*100):.1f}% of target")

        # Display Dataframe with color coding
        df = pd.DataFrame(rows)
        def color_pnl(val):
            color = 'green' if val > 0 else 'red'
            return f'color: {color}'
        
        st.subheader("Holdings Detail")
        st.dataframe(df.style.applymap(color_pnl, subset=['P&L ($)']))
        
        # Allocation Chart
        st.subheader("Asset Allocation")
        labels = list(port.positions.keys()) + ["Cash"]
        sizes = [p.market_value() for p in port.positions.values()] + [port.cash_balance]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
        st.pyplot(fig)
    else:
        st.info("Your portfolio is currently empty. Start trading to see your summary!")

# TAB 3: MARKET ANALYSIS
with tabs[2]:
    st.subheader("Historical Price Charts")
    t_chart = st.text_input("Symbol to Analyze:", value="AAPL").upper()
    period = st.select_slider("Select Period", options=["1mo", "3mo", "6mo", "1y", "5y"])
    if st.button("Generate Chart"):
        with st.spinner('Fetching market data...'):
            data = yf.download(t_chart, period=period)
            if not data.empty:
                st.line_chart(data['Close'])
                st.write(f"Latest Stats for {t_chart}:")
                st.table(data.tail(5))
            else: st.warning("Data not found for this symbol.")
