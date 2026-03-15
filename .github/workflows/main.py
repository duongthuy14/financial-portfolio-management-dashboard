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
    if 1 <= len(query) <= 5 or "=" in query: # Support Futures like ES=F
        return query
    try:
        search = yf.Search(query, max_results=1)
        for result in search.quotes:
            return result['symbol']
    except:
        pass
    return None

# ==========================================
# 2. CORE CLASSES (BACKEND)
# ==========================================
class Asset(ABC):
    def __init__(self, ticker, current_price, asset_type):
        self.ticker = ticker
        self.current_price = current_price
        self.asset_type = asset_type
    
    @abstractmethod
    def get_display_name(self) -> str: pass

class Stock(Asset):
    def __init__(self, ticker, current_price):
        super().__init__(ticker, current_price, "Stock")
    def get_display_name(self): return f"Equity: {self.ticker}"

class Bond(Asset):
    def __init__(self, ticker, current_price):
        super().__init__(ticker, current_price, "Bond")
    def get_display_name(self): return f"Fixed Income: {self.ticker}"

class Derivative(Asset):
    def __init__(self, ticker, current_price):
        super().__init__(ticker, current_price, "Derivative")
    def get_display_name(self): return f"Derivative/Future: {self.ticker}"

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
    def __init__(self, name, dob, risk_level, savings_goal, strategy):
        self.name = name
        self.dob = dob
        self.risk_level = risk_level
        self.savings_goal = savings_goal
        self.strategy = strategy
    @property
    def age(self):
        return date.today().year - self.dob.year
    def is_derivative_allowed(self): return self.risk_level >= 4

# ==========================================
# 3. STREAMLIT UI (FRONTEND)
# ==========================================
st.set_page_config(page_title="Smart Portfolio Dashboard", layout="wide")

def get_market_data(ticker):
    try:
        t = yf.Ticker(ticker)
        # Fetching price and type info
        price = float(t.fast_info['lastPrice'])
        q_type = t.info.get('quoteType', 'EQUITY')
        return price, q_type
    except: return None, None

# Sidebar Setup
st.sidebar.header("👤 Profile Settings")
u_name = st.sidebar.text_input("Investor Name", "UEH Student")
u_dob = st.sidebar.date_input("Date of Birth", date(2000, 1, 1))
u_risk = st.sidebar.slider("Risk Level (1-5)", 1, 5, 3)
u_goal = st.sidebar.number_input("Savings Goal ($)", value=10000.0)
u_cash = st.sidebar.number_input("Initial Cash ($)", value=5000.0)
u_strat = st.sidebar.selectbox("Strategy", ["classical", "buffett", "graham"])

if st.sidebar.button("Reset All Data"):
    st.session_state.clear()
    st.rerun()

# Session State & Sync
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = Portfolio(u_cash)
if 'user' not in st.session_state:
    st.session_state.user = UserProfile(u_name, u_dob, u_risk, u_goal, u_strat)
else:
    # Update user object with current sidebar values
    st.session_state.user.name, st.session_state.user.dob = u_name, u_dob
    st.session_state.user.risk_level, st.session_state.user.strategy = u_risk, u_strat
    st.session_state.user.savings_goal = u_goal

port = st.session_state.portfolio
user = st.session_state.user

st.title("📊 Financial Portfolio Dashboard")
st.info(f"Investor: **{user.name}** | Age: **{user.age}** | Strategy: **{user.strategy.upper()}**")

tabs = st.tabs(["🎯 Auto-Detect Trade", "💰 Portfolio Summary", "📈 Market View"])

# TAB 1: SMART TRADING
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Buy Asset (Auto-Detect)")
        t_buy = st.text_input("Ticker Symbol (e.g., TSLA, BND, ES=F):", key="t_buy").upper()
        q_buy = st.number_input("Quantity:", min_value=1, step=1)
        
        if st.button("Execute Purchase"):
            ticker = resolve_stock_ticker(t_buy)
            if ticker:
                price, mkt_type = get_market_data(ticker)
                if price:
                    st.write(f"**Detected Asset Type:** {mkt_type} | **Price:** ${price:,.2f}")
                    
                    # Logic Mapping
                    asset = None
                    if mkt_type == 'EQUITY':
                        asset = Stock(ticker, price)
                    elif mkt_type == 'ETF':
                        # Bonds are usually ETFs in Yahoo Finance (BND, AGG)
                        asset = Bond(ticker, price)
                    elif mkt_type in ['FUTURE', 'OPTION']:
                        if not user.is_derivative_allowed():
                            st.error("Access Denied: Risk Level 4 required for Derivatives.")
                        else:
                            asset = Derivative(ticker, price)
                    else:
                        asset = Stock(ticker, price) # Default fallback
                    
                    if asset:
                        try:
                            port.buy(asset, q_buy)
                            st.success(f"Successfully added {q_buy} units of {ticker} to your portfolio.")
                        except InsufficientFundsError as e: st.error(e)
                else: st.error("Price data unavailable for this ticker.")
            else: st.error("Ticker not found.")

    with c2:
        st.subheader("Sell Asset")
        t_sell = st.text_input("Symbol to Sell:", key="t_sell").upper()
        q_sell = st.number_input("Quantity to Sell:", min_value=1, step=1, key="qs")
        if st.button("Execute Sale"):
            try:
                port.sell_asset(t_sell, q_sell)
                st.success(f"Sale confirmed: {q_sell} {t_sell}")
            except Exception as e: st.error(e)

# TAB 2: SUMMARY
with tabs[1]:
    m1, m2, m3 = st.columns(3)
    m1.metric("Available Cash", f"${port.cash_balance:,.2f}")
    
    if port.positions:
        rows = []
        total_assets = 0
        for t, pos in port.positions.items():
            # Refresh price
            t_price, _ = get_market_data(t)
            if t_price: pos.asset.current_price = t_price
            
            val = pos.market_value()
            total_assets += val
            rows.append({
                "Ticker": t, "Type": pos.asset.asset_type, "Qty": pos.quantity,
                "Avg Cost": f"${pos.avg_buy_price:,.2f}", "Current": f"${pos.asset.current_price:,.2f}",
                "Profit/Loss": pos.pnl()
            })
        
        nav = port.cash_balance + total_assets
        m2.metric("Portfolio NAV", f"${nav:,.2f}")
        m3.metric("Goal Progress", f"{(nav/user.savings_goal)*100:.1f}%")

        df = pd.DataFrame(rows)
        st.dataframe(df.style.applymap(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Profit/Loss']))

        # Chart
        fig, ax = plt.subplots(figsize=(5,3))
        ax.pie([pos.market_value() for pos in port.positions.values()] + [port.cash_balance], 
               labels=list(port.positions.keys()) + ["Cash"], autopct='%1.1f%%')
        st.pyplot(fig)
    else:
        st.info("No active positions.")

# TAB 3: ANALYSIS
with tabs[2]:
    t_view = st.text_input("Search Symbol for Chart:", value="AAPL").upper()
    if st.button("Show History"):
        hist = yf.download(t_view, period="6mo")
        if not hist.empty:
            st.line_chart(hist['Close'])
        else: st.error("Data not found.")
