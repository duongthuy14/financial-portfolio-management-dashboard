import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import json
import os
from datetime import date
from abc import ABC, abstractmethod
import appdirs  # Để fix cache trên Streamlit Cloud

# Fix cache directory cho yfinance trên Streamlit Cloud
appdirs.user_cache_dir = lambda *args, **kwargs: "/tmp"

# =====================================================================
# PART 1: LOGIC CODE
# =====================================================================

def resolve_stock_ticker(user_input):
    query = user_input.strip().upper()
    if not query:
        return None

    # Cách 1: Kiểm tra trực tiếp ticker
    try:
        t = yf.Ticker(query)
        price = t.fast_info.get("lastPrice", 0)
        if price > 0:
            return query
    except Exception:
        pass

    # Cách 2: Không dùng yf.Search nữa (đã deprecated) → fallback đơn giản
    # Thử một số suffix phổ biến nếu cần (có thể mở rộng sau)
    for suffix in ["", ".L", "=F", ".NS", ".BO"]:
        test = query + suffix
        try:
            t = yf.Ticker(test)
            if t.fast_info.get("lastPrice", 0) > 0:
                return test
        except:
            continue

    return None


class UserProfile:
    def __init__(self, name, dob_str, risk_level, savings_goal, strategy="classical"):
        self.name = name.strip()
        self.dob = date.fromisoformat(dob_str.strip())
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
        if self.strategy == "graham":
            return {"Stocks": 50, "Fixed Income": 50, "Commodities": 0}
        equity = max(100 - self.age, 20)
        return {"Stocks": equity, "Fixed Income": 100 - equity, "Commodities": 0}

    def is_derivative_allowed(self):
        return self.risk_level >= 4


class InsufficientFundsError(Exception): pass
class InsufficientSharesError(Exception): pass


class Asset(ABC):
    def __init__(self, ticker: str, current_price: float):
        self.ticker = ticker.upper()
        self.current_price = float(current_price)

    @abstractmethod
    def get_asset_type(self) -> str: pass


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


class EquityFund(Asset):  # Không kế thừa Stock nữa để tránh lỗi super()
    def __init__(self, ticker: str, current_price: float):
        super().__init__(ticker, current_price)
        try:
            info = yf.Ticker(ticker).info
            self.expense_ratio = info.get("expenseRatio", 0.0)
            self.fund_family = info.get("fundFamily", "Unknown")
            self.category = info.get("category", "Equity Fund")
        except:
            self.expense_ratio = 0.0
            self.fund_family = "Unknown"
            self.category = "Equity Fund"

    def get_asset_type(self):
        return "Equity Fund"


class Commodities(Asset):
    def __init__(self, ticker: str, current_price: float):
        super().__init__(ticker, current_price)
        try:
            self.full_name = yf.Ticker(ticker).info.get("shortName", ticker)
        except:
            self.full_name = ticker

    def get_asset_type(self):
        return "Commodity"


class Derivatives(Asset):
    def __init__(self, ticker: str, current_price: float, underlying: str = "Unknown"):
        super().__init__(ticker, current_price)
        self.underlying = underlying
        try:
            info = yf.Ticker(ticker).info
            self.multiplier = info.get("multiplier", 100)
        except:
            self.multiplier = 100

    def get_asset_type(self):
        return "Derivative"


class Position:
    def __init__(self, asset: Asset, quantity: int, avg_buy_price: float):
        self.asset = asset
        self.quantity = quantity
        self.avg_buy_price = avg_buy_price

    def market_value(self) -> float:
        return self.quantity * self.asset.current_price

    def pnl(self) -> float:
        return (self.asset.current_price - self.avg_buy_price) * self.quantity

    def update_position(self, extra_qty: int, price: float):
        total = self.quantity * self.avg_buy_price + extra_qty * price
        self.quantity += extra_qty
        self.avg_buy_price = total / self.quantity


class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash_balance = float(initial_cash)
        self.positions = {}  # ticker -> Position

    def buy(self, asset: Asset, quantity: int):
        cost = asset.current_price * quantity
        if cost > self.cash_balance:
            raise InsufficientFundsError(f"Required ${cost:,.2f} — only ${self.cash_balance:,.2f} available")
        self.cash_balance -= cost
        t = asset.ticker
        if t in self.positions:
            self.positions[t].update_position(quantity, asset.current_price)
        else:
            self.positions[t] = Position(asset, quantity, asset.current_price)

    def sell_asset(self, ticker: str, quantity: int):
        if ticker not in self.positions or self.positions[ticker].quantity < quantity:
            raise InsufficientSharesError(f"Not enough {ticker} shares")
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
        w = {t: p.market_value() / total for t, p in self.positions.items()}
        w["Cash"] = self.cash_balance / total
        return w


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
            json.dump(users, f, indent=2)
    except:
        pass  # im lặng trên cloud


def get_live_price(ticker: str) -> float:
    try:
        return float(yf.Ticker(ticker).fast_info["lastPrice"])
    except Exception:
        return 0.0


# =====================================================================
# STREAMLIT UI
# =====================================================================

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = None


def render_login():
    st.title("📊 Investment Portfolio Dashboard")
    st.subheader("Create Investor Profile")

    users = load_users()

    with st.form("profile_form"):
        name = st.text_input("Name", "").strip()
        dob = st.text_input("DOB (YYYY-MM-DD)", "2000-01-01")
        risk = st.slider("Risk Level (1-5)", 1, 5, 3)
        goal = st.number_input("Savings Goal ($)", 0.0, value=10000.0, step=1000.0)
        cash = st.number_input("Initial Cash ($)", 0.0, value=10000.0, step=1000.0)
        strategy = st.selectbox("Strategy", ["classical", "buffett", "graham"])

        if st.form_submit_button("Start", type="primary"):
            if not name:
                st.error("Please enter name")
                st.stop()
            try:
                date.fromisoformat(dob)
            except:
                st.error("Invalid date format — use YYYY-MM-DD")
                st.stop()
            if cash > goal:
                st.error("Initial cash cannot exceed goal")
                st.stop()

            st.session_state.user = UserProfile(name, dob, risk, goal, strategy)
            st.session_state.portfolio = Portfolio(cash)
            st.session_state.logged_in = True

            users[name] = dob
            save_users(users)

            st.success(f"Welcome, {name}!")
            st.rerun()


def render_dashboard():
    user = st.session_state.user
    port = st.session_state.portfolio

    st.sidebar.title("Menu")
    st.sidebar.markdown(f"**{user.name}** ({user.age} y/o)")
    st.sidebar.markdown(f"**Strategy:** {user.strategy.title()}")
    st.sidebar.markdown("---")

    pages = ["Portfolio Overview", "Trade (Buy/Sell)", "Allocation Pie", "Price History"]
    page = st.sidebar.radio("Select", pages)

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if page == "Portfolio Overview":
        st.header("Portfolio Overview")
        st.metric("Cash", f"${port.cash_balance:,.2f}")

        if not port.positions:
            st.info("Portfolio is empty")
        else:
            rows = []
            total = port.cash_balance
            for t, pos in port.positions.items():
                p = get_live_price(t)
                if p > 0:
                    pos.asset.current_price = p
                mv = pos.market_value()
                total += mv
                rows.append({
                    "Ticker": t,
                    "Qty": pos.quantity,
                    "Avg Cost": f"${pos.avg_buy_price:,.2f}",
                    "Price": f"${p:,.2f}",
                    "P/L": f"{pos.pnl():+,.2f}",
                    "Value": f"${mv:,.2f}"
                })
            st.dataframe(rows, use_container_width=True)
            st.metric("Total Value", f"${total:,.2f}")

        st.subheader("Target Allocation")
        for k, v in user.get_target_weights().items():
            st.write(f"• **{k}**: {v}%")

    elif page == "Trade (Buy/Sell)":
        st.header("Trade")

        tab1, tab2 = st.tabs(["Buy", "Sell"])

        with tab1:
            ticker_str = st.text_input("Ticker", key="buy_t").strip().upper()
            qty = st.number_input("Quantity", min_value=1, step=1, key="buy_q")
            cls = st.selectbox("Class", ["Stock", "Bond", "Equity Fund", "Commodity", "Derivative"])

            if st.button("Buy", type="primary"):
                tk = resolve_stock_ticker(ticker_str)
                if not tk:
                    st.error("Ticker not found")
                    st.stop()
                price = get_live_price(tk)
                if price <= 0:
                    st.error("Price unavailable")
                    st.stop()
                if cls == "Derivative" and not user.is_derivative_allowed():
                    st.error("Derivatives not allowed at your risk level")
                    st.stop()

                if cls == "Stock":
                    asset = Stock(tk, price)
                elif cls == "Bond":
                    asset = Bond(tk, price)
                elif cls == "Equity Fund":
                    asset = EquityFund(tk, price)
                elif cls == "Commodity":
                    asset = Commodities(tk, price)
                else:
                    asset = Derivatives(tk, price)

                try:
                    port.buy(asset, qty)
                    st.success(f"Bought {qty} {tk}")
                except InsufficientFundsError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Buy failed: {e}")

        with tab2:
            ticker_sell = st.text_input("Ticker to sell", key="sell_t").strip().upper()
            qty_sell = st.number_input("Quantity", min_value=1, step=1, key="sell_q")

            if st.button("Sell", type="primary"):
                tk = resolve_stock_ticker(ticker_sell)
                if not tk:
                    st.error("Invalid ticker")
                else:
                    try:
                        port.sell_asset(tk, qty_sell)
                        st.success(f"Sold {qty_sell} {tk}")
                    except InsufficientSharesError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Sell failed: {e}")

    elif page == "Allocation Pie":
        st.header("Portfolio Allocation")
        weights = port.get_portfolio_weights()
        active = {k: v for k, v in weights.items() if v > 0.005}

        if len(active) < 2:
            st.info("Not enough data for chart")
        else:
            fig, ax = plt.subplots(figsize=(7, 7))
            ax.pie(active.values(), labels=active.keys(), autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
            st.pyplot(fig)

    elif page == "Price History":
        st.header("Historical Price")
        sym = st.text_input("Ticker", "AAPL").strip().upper()
        per = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"])

        if st.button("Load"):
            tk = resolve_stock_ticker(sym)
            if not tk:
                st.error("Ticker not found")
            else:
                with st.spinner("Loading..."):
                    df = yf.download(tk, period=per, progress=False)
                if df.empty:
                    st.error("No data")
                else:
                    st.line_chart(df["Close"])
                    st.dataframe(df.tail(6))


# Router
if st.session_state.logged_in:
    render_dashboard()
else:
    render_login()
