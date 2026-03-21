import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import json
import os
from datetime import date
from abc import ABC, abstractmethod

# =====================================================================
# PART 1: LOGIC CODE
# =====================================================================

def resolve_stock_ticker(user_input):
    query = user_input.strip().upper()
    if not query:
        return None

    try:
        ticker = yf.Ticker(query)
        info = ticker.fast_info
        if info.get('lastPrice', 0) > 0:
            return query
    except Exception:
        pass

    # Tìm kiếm thay thế (dùng yfinance search-like behavior)
    try:
        suggestions = yf.utils.get_all_symbol_info(query)
        if suggestions:
            for sym in suggestions:
                if sym.upper().startswith(query):
                    t = yf.Ticker(sym)
                    if t.fast_info.get('lastPrice', 0) > 0:
                        return sym
    except Exception:
        pass

    return None


class UserProfile:
    def __init__(self, name, dob_str, risk_level, savings_goal, strategy="classical"):
        self.name = name
        self.dob = date.fromisoformat(dob_str)
        self.risk_level = int(risk_level)
        self.savings_goal = float(savings_goal)
        self.strategy = strategy.lower()

    @property
    def age(self):
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

    def get_target_weights(self):
        if self.strategy == "buffett":
            return {"Stocks": 90, "Fixed Income": 10, "Commodities": 0}
        elif self.strategy == "graham":
            return {"Stocks": 50, "Fixed Income": 50, "Commodities": 0}
        # classical / age-based
        equity_target = max(100 - self.age, 20)
        return {"Stocks": equity_target, "Fixed Income": 100 - equity_target, "Commodities": 0}

    def is_derivative_allowed(self):
        return self.risk_level >= 4


class InsufficientFundsError(Exception):
    pass


class InsufficientSharesError(Exception):
    pass


class Asset(ABC):
    def __init__(self, ticker: str, current_price: float):
        self.ticker = ticker.upper()
        self.current_price = float(current_price)

    @abstractmethod
    def get_asset_type(self) -> str:
        pass


class Stock(Asset):
    def __init__(self, ticker: str, current_price: float, sector: str = "Unknown"):
        super().__init__(ticker, current_price)
        self.sector = sector

    def get_asset_type(self):
        return "Stock"


class Bond(Asset):
    def __init__(self, ticker: str, current_price: float, coupon_rate: float = 0.0):
        super().__init__(ticker, current_price)
        self.coupon_rate = coupon_rate

    def get_asset_type(self):
        return "Bond"


class EquityFund(Asset):  
    def __init__(self, ticker: str, current_price: float):
        super().__init__(ticker, current_price)
        try:
            info = yf.Ticker(ticker).info
            self.expense_ratio = info.get('expenseRatio', 0.0)
            self.fund_family = info.get('fundFamily', 'Unknown')
            self.category = info.get('category', 'Equity Fund')
        except:
            self.expense_ratio = 0.0
            self.fund_family = 'Unknown'
            self.category = 'Equity Fund'

    def get_asset_type(self):
        return "Equity Fund"

    def get_annual_cost(self, market_value):
        return market_value * self.expense_ratio


class Commodities(Asset):
    def __init__(self, ticker: str, current_price: float):
        super().__init__(ticker, current_price)
        try:
            info = yf.Ticker(ticker).info
            self.full_name = info.get('shortName', ticker)
        except:
            self.full_name = ticker

    def get_asset_type(self):
        return "Commodity"


class Derivatives(Asset):
    def __init__(self, ticker: str, current_price: float, underlying_ticker: str = ""):
        super().__init__(ticker, current_price)
        self.underlying_ticker = underlying_ticker
        try:
            info = yf.Ticker(ticker).info
            self.multiplier = info.get('multiplier', 100)
        except:
            self.multiplier = 100

    def get_asset_type(self):
        return "Derivative"


class Position:
    def __init__(self, asset: Asset, quantity: int, avg_buy_price: float):
        self.asset = asset
        self.quantity = int(quantity)
        self.avg_buy_price = float(avg_buy_price)

    def market_value(self) -> float:
        return self.quantity * self.asset.current_price

    def pnl(self) -> float:
        return (self.asset.current_price - self.avg_buy_price) * self.quantity

    def update_position(self, extra_qty: int, price: float):
        total_cost = (self.quantity * self.avg_buy_price) + (extra_qty * price)
        self.quantity += extra_qty
        self.avg_buy_price = total_cost / self.quantity


class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash_balance = float(initial_cash)
        self.positions = {} 

    def buy(self, asset: Asset, quantity: int):
        cost = asset.current_price * quantity
        if cost > self.cash_balance + 0.001: 
            raise InsufficientFundsError(f"Required: ${cost:,.2f} — Available: ${self.cash_balance:,.2f}")
        self.cash_balance -= cost
        ticker = asset.ticker
        if ticker in self.positions:
            self.positions[ticker].update_position(quantity, asset.current_price)
        else:
            self.positions[ticker] = Position(asset, quantity, asset.current_price)

    def sell_asset(self, ticker: str, quantity: int):
        if ticker not in self.positions or self.positions[ticker].quantity < quantity:
            raise InsufficientSharesError(f"Not enough {ticker} to sell ({quantity} requested)")
        pos = self.positions[ticker]
        revenue = quantity * pos.asset.current_price
        self.cash_balance += revenue
        pos.quantity -= quantity
        if pos.quantity <= 0:
            del self.positions[ticker]

    def get_portfolio_weights(self):
        total = self.cash_balance + sum(p.market_value() for p in self.positions.values())
        if total <= 0:
            return {"Cash": 1.0}
        weights = {t: p.market_value() / total for t, p in self.positions.items()}
        weights["Cash"] = self.cash_balance / total
        return weights


# =====================================================================
# File handling
# =====================================================================

USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    try:
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Cannot save user data: {e}")


def get_live_price(ticker: str) -> float:
    try:
        price = yf.Ticker(ticker).fast_info["lastPrice"]
        return float(price)
    except Exception:
        return 0.0


# =====================================================================
# STREAMLIT UI
# =====================================================================

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

# Khởi tạo session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = None


def render_login():
    st.title("📊 Investment Portfolio Dashboard")
    st.subheader("Create or load investor profile")

    users = load_users()

    with st.form("setup_form"):
        name = st.text_input("Investor's Name", value="").strip()
        dob = st.text_input("Date of Birth (YYYY-MM-DD)", value="2000-01-01")
        risk = st.slider("Risk Tolerance (1–5)", 1, 5, 3)
        goal = st.number_input("Savings Goal ($)", min_value=0.0, value=10000.0, step=1000.0)
        initial_cash = st.number_input("Initial Cash ($)", min_value=0.0, value=10000.0, step=1000.0)
        strategy = st.selectbox("Investment Style", ["classical", "buffett", "graham"])

        submitted = st.form_submit_button("Start Investing", type="primary")

        if submitted:
            if not name:
                st.error("Please enter your name.")
                return
            try:
                date.fromisoformat(dob)
            except:
                st.error("Invalid date format. Use YYYY-MM-DD")
                return
            if initial_cash > goal + 1:
                st.error("Initial cash should not exceed savings goal.")
                return

            st.session_state.user = UserProfile(name, dob, risk, goal, strategy)
            st.session_state.portfolio = Portfolio(initial_cash)
            st.session_state.logged_in = True

            users[name] = dob
            save_users(users)

            st.success(f"Welcome {name}!")
            st.rerun()


def render_dashboard():
    user = st.session_state.user
    portfolio = st.session_state.portfolio

    st.sidebar.title("Control Panel")
    st.sidebar.markdown(f"**Investor:** {user.name} ({user.age} y/o)")
    st.sidebar.markdown(f"**Style:** {user.strategy.title()}")
    st.sidebar.markdown("---")

    menu = [
        "1. Portfolio Overview",
        "2. Buy / Sell",
        "3. Asset Allocation",
        "4. Price History"
    ]
    choice = st.sidebar.radio("Menu", menu, index=0)

    if st.sidebar.button("Logout", type="secondary"):
        for key in ['logged_in', 'user', 'portfolio']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    if choice.startswith("1"):
        st.header("Portfolio Overview")

        live_cash = f"${portfolio.cash_balance:,.2f}"
        st.metric("Cash Balance", live_cash)

        if not portfolio.positions:
            st.info("Your portfolio is currently empty.")
        else:
            total_value = portfolio.cash_balance
            rows = []
            for ticker, pos in portfolio.positions.items():
                price = get_live_price(ticker)
                if price > 0:
                    pos.asset.current_price = price
                mv = pos.market_value()
                total_value += mv
                rows.append({
                    "Ticker": ticker,
                    "Qty": pos.quantity,
                    "Avg Cost": f"${pos.avg_buy_price:,.2f}",
                    "Price": f"${price:,.2f}",
                    "P/L ($)": f"{pos.pnl():+,.2f}",
                    "Market Value": f"${mv:,.2f}"
                })
            st.dataframe(rows, use_container_width=True)
            st.metric("Total Portfolio Value", f"${total_value:,.2f}", delta_color="normal")

        st.subheader("Target Allocation (according to your profile)")
        targets = user.get_target_weights()
        for asset, pct in targets.items():
            st.write(f"• **{asset}**: {pct}%")

    elif choice.startswith("2"):
        st.header("Trade Execution")

        tab_buy, tab_sell = st.tabs(["Buy", "Sell"])

        with tab_buy:
            ticker_raw = st.text_input("Ticker / Symbol", key="buy_ticker").strip().upper()
            qty = st.number_input("Quantity", min_value=1, step=1, key="buy_qty")
            asset_class = st.selectbox("Asset Class", [
                "Stock", "Bond", "Equity Fund", "Commodity", "Derivative"
            ], key="buy_class")

            if st.button("Execute BUY", type="primary"):
                ticker = resolve_stock_ticker(ticker_raw)
                if not ticker:
                    st.error("Cannot find valid ticker.")
                    st.stop()

                price = get_live_price(ticker)
                if price <= 0:
                    st.error("Cannot get current price.")
                    st.stop()

                if asset_class == "Derivative" and not user.is_derivative_allowed():
                    st.error("Your risk tolerance does not allow derivatives.")
                    st.stop()

                try:
                    if asset_class == "Stock":
                        asset = Stock(ticker, price)
                    elif asset_class == "Bond":
                        asset = Bond(ticker, price)
                    elif asset_class == "Equity Fund":
                        asset = EquityFund(ticker, price)
                    elif asset_class == "Commodity":
                        asset = Commodities(ticker, price)
                    else:  # Derivative
                        asset = Derivatives(ticker, price)

                    portfolio.buy(asset, qty)
                    st.success(f"Bought {qty} × {ticker} successfully!")
                except InsufficientFundsError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Trade failed: {e}")

        with tab_sell:
            ticker_sell = st.text_input("Ticker to sell", key="sell_ticker").strip().upper()
            qty_sell = st.number_input("Quantity to sell", min_value=1, step=1, key="sell_qty")

            if st.button("Execute SELL", type="primary"):
                ticker = resolve_stock_ticker(ticker_sell)
                if not ticker:
                    st.error("Invalid ticker.")
                else:
                    try:
                        portfolio.sell_asset(ticker, qty_sell)
                        st.success(f"Sold {qty_sell} × {ticker} successfully!")
                    except InsufficientSharesError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Error: {e}")

    elif choice.startswith("3"):
        st.header("Asset Allocation")

        weights = portfolio.get_portfolio_weights()
        active_weights = {k: v for k, v in weights.items() if v > 0.001}

        if len(active_weights) <= 1:
            st.info("No allocation data to display yet.")
        else:
            fig, ax = plt.subplots(figsize=(7, 7))
            ax.pie(active_weights.values(), labels=active_weights.keys(),
                   autopct='%1.1f%%', startangle=90, pctdistance=0.85)
            ax.axis('equal')
            st.pyplot(fig)

    elif choice.startswith("4"):
        st.header("Historical Price")

        ticker_raw = st.text_input("Enter ticker (e.g. AAPL, VOO, GC=F)").strip().upper()
        period = st.select_slider("Period", ["1mo", "3mo", "6mo", "1y", "5y", "max"])

        if st.button("Load Chart"):
            ticker = resolve_stock_ticker(ticker_raw)
            if not ticker:
                st.error("Ticker not found.")
            else:
                with st.spinner("Downloading data..."):
                    df = yf.download(ticker, period=period, progress=False)
                if df.empty:
                    st.error("No data returned.")
                else:
                    st.line_chart(df["Close"])
                    st.caption(f"Last 5 trading days — {ticker}")
                    st.dataframe(df.tail(5)[["Open", "High", "Low", "Close", "Volume"]])

if st.session_state.logged_in:
    render_dashboard()
else:
    render_login()
