
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
    query = user_input.strip()
    if query.isupper() and 1 <= len(query) <= 5:
        try:
            check = yf.Ticker(query)
            if check.fast_info['lastPrice'] > 0:
                return query
        except:
            pass
    try:
        search = yf.Search(query, max_results=5)
        for result in search.quotes:
            if result.get('quoteType') == 'EQUITY':
                return result['symbol']
    except Exception:
        pass
    return None

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
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

    def get_target_weights(self):
        if self.strategy == "buffett":
            return {"Fundamentals": 90, "Commodities": 0, "Fixed Income": 10}
        elif self.strategy == "graham":
            return {"Fundamentals": 50, "Fixed Income": 50, "Commodities": 0}

        equity_target = max(100 - self.age, 20)
        return {"Fundamentals": equity_target, "Fixed Income": 100 - equity_target}

    def is_derivative_allowed(self):
        return self.risk_level >= 4

class InsufficientFundsError(Exception): pass
class InsufficientSharesError(Exception): pass

class Asset(ABC):
    def __init__(self, ticker: str, current_price: float):
        self.ticker = ticker
        self.current_price = current_price
    @abstractmethod
    def get_asset_type(self) -> str: pass

class Stock(Asset):
    def __init__(self, ticker: str, current_price: float, sector: str):
        super().__init__(ticker, current_price)
        self.sector = sector
    def get_asset_type(self): return "Stock"

class Bond(Asset):
    def __init__(self, ticker: str, current_price: float, coupon_rate: float):
        super().__init__(ticker, current_price)
        self.coupon_rate = coupon_rate
    def get_asset_type(self): return "Bond"

class EquityFund(Stock):
    def __init__(self, ticker, sector="Financial Services"):
        # 1. Initialize the robust Stock parent (which calls Asset)
        # This automatically fetches current_price using yfinance
        super().__init__(ticker, sector)

        # 2. Use yfinance to get Fund-specific metadata
        # We use yf.Ticker(ticker) to get the info dictionary
        ticker_info = yf.Ticker(ticker).info

        self.expense_ratio = ticker_info.get('expenseRatio', 0)
        self.fund_family = ticker_info.get('fundFamily', 'Unknown')
        self.category = ticker_info.get('category', 'Equity Fund')

    def get_asset_type(self):
        """Overrides the parent to identify as a Fund for reporting."""
        return "Equity Fund"

    def get_annual_cost(self, current_market_value):
        """
        Calculates the dollar amount lost to fees per year.
        Note: market_value is now managed by the Position class.
        """
        return current_market_value * self.expense_ratio

    def get_risk_profile(self):
        """Returns a behavioral description for the Portfolio evaluation."""
        return f"Diversified Equity Exposure ({self.category}) managed by {self.fund_family}"
    
class Commodities(Asset):
    def __init__(self, ticker):
        """
        In the robust system, the Asset only needs the ticker.
        Position handles the quantity and purchase math.
        """
        # 1. Initialize robust Parent (Asset)
        # This automatically fetches current_price using yfinance
        super().__init__(ticker)

        # 2. Commodity-specific info
        # We can fetch the long name (e.g., "Gold June 24") for better reporting
        try:
            self.full_name = yf.Ticker(ticker).info.get('shortName', ticker)
        except:
            self.full_name = ticker

    def get_asset_type(self) -> str:
        return "Commodity"

    def get_risk_profile(self):
        """Behavioral insight for the UserProfile evaluation."""
        return f"Inflation Hedge / Hard Asset ({self.full_name})"

class Derivatives(Asset):
    def __init__(self, ticker, underlying_ticker):
        super().__init__(ticker) # Fixed missing current_price arg based on logic provided, simplified handling below
        self.underlying_ticker = underlying_ticker
        try:
            self.contract_info = yf.Ticker(ticker).info
            self.multiplier = self.contract_info.get('multiplier', 100)
        except:
            self.multiplier = 100
    def get_asset_type(self) -> str: return "Derivative"

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
        total_cost = (self.quantity * self.avg_buy_price) + (extra_qty * price)
        self.quantity += extra_qty
        self.avg_buy_price = total_cost / self.quantity

class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash_balance = initial_cash
        self.positions = {}

    def buy(self, asset: Asset, quantity: int):
        cost = asset.current_price * quantity
        if cost > self.cash_balance:
            raise InsufficientFundsError(f"Trade failed. Required: ${cost}, Available: ${self.cash_balance}")
        self.cash_balance -= cost
        if asset.ticker in self.positions:
            self.positions[asset.ticker].update_position(quantity, asset.current_price)
        else:
            self.positions[asset.ticker] = Position(asset, quantity, asset.current_price)

    def sell_asset(self, ticker: str, quantity: int):
        if ticker not in self.positions or self.positions[ticker].quantity < quantity:
            raise InsufficientSharesError(f"Trade failed: Not enough shares of {ticker} to sell.")
        pos = self.positions[ticker]
        revenue = quantity * pos.asset.current_price
        self.cash_balance += revenue
        pos.quantity -= quantity
        if pos.quantity == 0:
            del self.positions[ticker]

    def get_portfolio_weights(self):
        total_value = self.cash_balance + sum(pos.market_value() for pos in self.positions.values())
        weights = {}
        for ticker, pos in self.positions.items():
            weights[ticker] = pos.market_value() / total_value
        weights['Cash'] = self.cash_balance / total_value
        return weights

USER_FILE = "users.json"
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def get_live_price(ticker):
    try:
        return float(yf.Ticker(ticker).fast_info['lastPrice'])
    except Exception:
        return 0.0

# =====================================================================
# PART 2: STREAMLIT DASHBOARD UI
# =====================================================================

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

# Khởi tạo Session State để lưu dữ liệu khi trang reload
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = None

def render_login():
    st.title("📊 Investment Portfolio Dashboard")
    st.subheader("Creating investor's profile")

    users = load_users()

    with st.form("setup_form"):
        name = st.text_input("Investor's Name:")
        dob = st.text_input("Date of Birth (YYYY-MM-DD):", value="2000-01-01")
        risk = st.number_input("Risk Tolerance (1-5):", min_value=1, max_value=5, value=3)
        goal = st.number_input("Savings goal ($):", min_value=0.0, value=10000.0)
        cash = st.number_input("Initial amount ($):", min_value=0.0, value=10000.0)
        strategy = st.selectbox("Strategy:", ["classical", "buffett", "graham"])

        submit = st.form_submit_button("Start")

        if submit:
            try:
                date.fromisoformat(dob)
            except ValueError:
                st.error("Date format error. Please use the format YYYY-MM-DD.")
                return

            if cash > goal:
                st.error("Error: Initial amount cannot exceed savings goal.")
                return

            if name not in users:
                users[name] = dob
                save_users(users)
                st.success(f"A new profile for {name} was created.")
            else:
                st.success(f"Welcome back, {name}.")

            # Khởi tạo object logic và lưu vào session state
            st.session_state.user = UserProfile(name, dob, risk, goal, strategy)
            st.session_state.portfolio = Portfolio(cash)
            st.session_state.logged_in = True
            st.rerun()

def render_dashboard():
    user = st.session_state.user
    portfolio = st.session_state.portfolio

    st.sidebar.title("Transaction System")
    st.sidebar.markdown(f"**User:** {user.name} ({user.age} years old)")
    st.sidebar.markdown(f"**Strategy:** {user.strategy.capitalize()}")
    st.sidebar.markdown("---")

    menu = ["1. Portfolio watching", "2. Transaction (Buy/Sell)", "3. Asset Allocation", "4. Historical Price Analysis"]
    choice = st.sidebar.radio("Menu:", menu)

    if st.sidebar.button("Log out"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.portfolio = None
        st.rerun()

    if choice.startswith("1"):
        st.header("Current Portfolio")
        st.markdown(f"**Cash balance:** `${portfolio.cash_balance:,.2f}`")

        if not portfolio.positions:
            st.info("Empty porfolio. You are currently not holding any asset")
        else:
            total_value = portfolio.cash_balance
            data = []

            for ticker, pos in portfolio.positions.items():
                live_price = get_live_price(ticker)
                if live_price > 0:
                    pos.asset.current_price = live_price

                mkt_val = pos.market_value()
                pnl = pos.pnl()
                total_value += mkt_val

                data.append({
                    "Ticker": ticker,
                    "Quantity": pos.quantity,
                    "Average cost": f"${pos.avg_buy_price:,.2f}",
                    "Current price": f"${pos.asset.current_price:,.2f}",
                    "Profit/Loss ($)": f"${pnl:,.2f}",
                    "Market value": f"${mkt_val:,.2f}"
                })

            st.table(data)
            st.markdown(f"### Net Asset Value (NAV): **${total_value:,.2f}**")

        st.divider()
        st.subheader("Weights recommended")
        target = user.get_target_weights()
        for k, v in target.items():
            st.write(f"- **{k}:** {v}%")

    elif choice.startswith("2"):
        st.header("Asset Transaction")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Buy Order")
            raw_ticker_buy = st.text_input("Asset ticker (VD: AAPL):")
            asset_type = st.selectbox("Asset class:", ["1. Stock", "2. Bond", "3. Derivative"])
            qty_buy = st.number_input("Amount:", min_value=1, step=1)

            if st.button("Confirm Buy Order", type="primary"):
                ticker = resolve_stock_ticker(raw_ticker_buy)
                if not ticker:
                    st.error("Invalid asset.")
                elif asset_type.startswith("3") and not user.is_derivative_allowed():
                    st.error("WARNING: Risk tolerance level cannot afford derivatives.")
                else:
                    price = get_live_price(ticker)
                    if price == 0.0:
                        st.error("Market price unavailable.")
                    else:
                        if asset_type.startswith("1"):
                            asset = Stock(ticker, price, "Market")
                        elif asset_type.startswith("2"):
                            asset = Bond(ticker, price, 5.0)
                        else:
                            # Tạm gán thuộc tính current_price cho phái sinh
                            asset = Derivatives(ticker, "Index")
                            asset.current_price = price

                        try:
                            portfolio.buy(asset, qty_buy)
                            st.success(f"Succeeded! {qty_buy} {ticker} purchased at ${price:,.2f}.")
                        except InsufficientFundsError as e:
                            st.error(f"Transaction Denied: {e}")

        with col2:
            st.subheader("Sell Order")
            raw_ticker_sell = st.text_input("Asset to sell:")
            qty_sell = st.number_input("Sold Amount:", min_value=1, step=1)

            if st.button("Confirm Sell Order", type="primary"):
                ticker = resolve_stock_ticker(raw_ticker_sell)
                if not ticker:
                    st.error("Invalid asset.")
                else:
                    try:
                        portfolio.sell_asset(ticker, qty_sell)
                        st.success(f"Succeeded! {qty_sell} {ticker} sold.")
                    except InsufficientSharesError as e:
                        st.error(f"Transaction denied: {e}")
                    except Exception as e:
                        st.error(f"System error: {e}")

    elif choice.startswith("3"):
        st.header("Asset Allocation Chart")
        weights = portfolio.get_portfolio_weights()
        filtered_weights = {k: v for k, v in weights.items() if v > 0}

        if not filtered_weights:
            st.info("Unavailable allocation (current portfolio equals 0).")
        else:
            fig, ax = plt.subplots(figsize=(8,6))
            ax.pie(filtered_weights.values(), labels=filtered_weights.keys(), autopct='%1.1f%%', startangle=140, colors=plt.cm.Paired.colors)
            ax.axis('equal')
            st.pyplot(fig)

    elif choice.startswith("4"):
        st.header("Historical Price Analysis")
        raw_ticker = st.text_input("Type ticker to view chart (Example: AAPL, TSLA):")
        if st.button("Accessing data"):
            ticker = resolve_stock_ticker(raw_ticker)
            if not ticker:
                st.error("Invalid asset.")
            else:
                st.info(f"Loading nearest 6-month closing price for {ticker}...")
                data = yf.download(ticker, period="6mo", progress=False)

                if data.empty:
                    st.error("Data not found for this ticker.")
                else:
                    fig, ax = plt.subplots(figsize=(10,5))
                    ax.plot(data.index, data['Close'], label=f"Closing price {ticker}")
                    ax.set_title(f"Historical Price data - {ticker}")
                    ax.set_ylabel("Price (USD)")
                    ax.grid(True, linestyle='--', alpha=0.6)
                    ax.legend()
                    st.pyplot(fig)

# Logic điều khiển luồng hiển thị
if st.session_state.logged_in:
    render_dashboard()
else:
    render_login()
