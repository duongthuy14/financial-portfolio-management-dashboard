import yfinance as yf
from datetime import date
#Transform company name to ticker to be user-friendly
def resolve_stock_ticker(user_input):
    """
    Robustly converts user input into a valid stock ticker.
    Supports: "AAPL", "apple", "Microsoft Corp", "Google"
    """
    # 1. Clean the input
    query = user_input.strip()

    # 2. Check if the input is already a Ticker (1-5 uppercase letters)
    # Most stock tickers follow this pattern.
    if query.isupper() and 1 <= len(query) <= 5:
        try:
            # We "ping" the ticker to see if it has a price (validity check)
            check = yf.Ticker(query)
            if check.fast_info['lastPrice'] > 0:
                return query
        except:
            pass # Not a valid ticker, proceed to search

    # 3. Behavioral Search: Use Yahoo's search engine to find the best match
    try:
        # We search for the string and filter for 'EQUITY' (Stocks)
        search = yf.Search(query, max_results=5)

        for result in search.quotes:
            # We only want actual stocks (Equity), not ETFs or Futures for this task
            if result.get('quoteType') == 'EQUITY':
                return result['symbol']

    except Exception as e:
        print(f"Connection error during search: {e}")

    return None
#User-profile class
class UserProfile:
    def __init__(self, name, dob_str, risk_level, savings_goal, strategy="classical"):
        self.name = name
        self.dob = date.fromisoformat(dob_str) # Format: "1995-01-01"
        self.risk_level = risk_level # 1-5
        self.savings_goal = savings_goal
        self.strategy = strategy # "buffett", "graham", "classical", or customized

    @property
    def age(self):
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

    def get_target_weights(self):
        """Returns the % targets for Fundamentals, Commodities, and Derivatives."""
        if self.strategy == "buffett":
            return {"Fundamentals": 90, "Commodities": 0, "Fixed Income": 10}

        elif self.strategy == "graham":
            return {"Fundamentals": 50, "Fixed Income": 50, "Commodities": 0}

        # Default: Classical (Age-based)
        equity_target = max(100 - self.age, 20)
        return {"Fundamentals": equity_target, "Fixed Income": 100 - equity_target}

    def is_derivative_allowed(self):
        """Financial Rationale: Derivatives are restricted for low risk levels."""
        return self.risk_level >= 4

from abc import ABC, abstractmethod

# 1. CUSTOM EXCEPTIONS
class InsufficientFundsError(Exception):
    pass

class InsufficientSharesError(Exception):
    pass

# 2. BASE CLASS
class Asset(ABC):
    def __init__(self, ticker: str, current_price: float):
        self.ticker = ticker
        self.current_price = current_price

    @abstractmethod
    def get_asset_type(self) -> str:
        pass

# 3. SUBCLASS
class Stock(Asset):
    def __init__(self, ticker: str, current_price: float, sector: str):
        super().__init__(ticker, current_price)
        self.sector = sector

    def get_asset_type(self):
        return "Stock"

class Bond(Asset):
    def __init__(self, ticker: str, current_price: float, coupon_rate: float):
        super().__init__(ticker, current_price)
        self.coupon_rate = coupon_rate

    def get_asset_type(self):
        return "Bond"

# 4. POSITION
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

# 5. PORTFOLIO
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
        print(f"SUCCEEDED: Bought {quantity} units of {asset.ticker}")

    def sell_asset(self, ticker: str, quantity: int):
        if ticker not in self.positions or self.positions[ticker].quantity < quantity:
            raise InsufficientSharesError(f"Trade failed: Not enough shares of {ticker} to sell.")

        pos = self.positions[ticker]
        revenue = quantity * pos.asset.current_price
        self.cash_balance += revenue
        pos.quantity -= quantity

        print(f"SUCCEEDED: Sold {quantity} units of {ticker}")

        if pos.quantity == 0:
            del self.positions[ticker]

    def get_portfolio_weights(self):
        total_value = self.cash_balance + sum(pos.market_value() for pos in self.positions.values())
        weights = {}
        for ticker, pos in self.positions.items():
            weights[ticker] = pos.market_value() / total_value
        weights['Cash'] = self.cash_balance / total_value
        return weights
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
        """
        Reconciled Derivative Parent Class.
        The Position class will handle quantity and avg_buy_price.
        """
        # 1. Initialize robust Parent (Asset)
        # This automatically fetches the contract's current_price using yfinance
        super().__init__(ticker)

        self.underlying_ticker = underlying_ticker

        # 2. Get contract details (Expiry, Strike, etc.)
        try:
            self.contract_info = yf.Ticker(ticker).info
            self.multiplier = self.contract_info.get('multiplier', 100) # Standard is 100 for options
        except:
            self.multiplier = 100 # Default fallback

    def get_asset_type(self) -> str:
        return "Derivative"

    def get_risk_profile(self):
        """Used by UserProfile to flag high-risk behavior."""
        return f"High-Leverage Derivative on {self.underlying_ticker} (Multiplier: {self.multiplier}x)"
# HÀM TEST ĐỂ CHẠY THỬ VÀ DEMO
def test_portfolio():
    print("--- 1. KHỞI TẠO DANH MỤC ($10,000) ---")
    my_port = Portfolio(initial_cash=10000.0)

    # Tạo các tài sản
    aapl = Stock("AAPL", 150.0, "Technology")
    tsla = Stock("TSLA", 200.0, "Automotive")
    vnbond = Bond("VNBOND", 100.0, 5.5)

    print("\n--- 2. MUA TÀI SẢN ---")
    my_port.buy(aapl, 10)  # Tốn 1500, dư 8500
    my_port.buy(tsla, 20)  # Tốn 4000, dư 4500

    print("\n--- 3. MUA TRUNG BÌNH GIÁ (DCA) ---")
    aapl.current_price = 140.0 # AAPL rớt giá
    my_port.buy(aapl, 10)  # Tốn 1400. AAPL qty = 20, Giá TB = (150*10 + 140*10)/20 = 145.0

    print("\n--- 4. BÁN TÀI SẢN ---")
    my_port.sell_asset("TSLA", 5) # Thu về 5 * 200 = 1000 (Dư 4100)

    print("\n--- 5. BẮT LỖI (EXCEPTION HANDLING) ---")
    try:
        my_port.buy(tsla, 100) # Cần 20,000 nhưng ví ko đủ
    except InsufficientFundsError as e:
        print(f"BẮT LỖI MUA: {e}")

    try:
        my_port.sell_asset("AAPL", 50) # Chỉ có 20 cổ phiếu
    except InsufficientSharesError as e:
        print(f"BẮT LỖI BÁN: {e}")

    print("\n--- 6. XEM TỶ TRỌNG DANH MỤC ---")
    weights = my_port.get_portfolio_weights()
    for ticker, weight in weights.items():
        print(f"{ticker}: {weight * 100:.2f}%")

# Chạy hàm test
if __name__ == "__main__":
    test_portfolio()
import yfinance as yf
import matplotlib.pyplot as plt

# ==========================================
# PORTFOLIO OPERATIONS
# ==========================================

def get_live_price(ticker):
    """Get real-time asset price from yfinance to pass into Logic Object"""
    try:
        return float(yf.Ticker(ticker).fast_info['lastPrice'])
    except Exception:
        return 0.0

def buy_asset(portfolio, user_profile):
    raw_ticker = input("Enter the asset ticker to buy (e.g., AAPL, TSLA): ")
    ticker = resolve_stock_ticker(raw_ticker) # Logic team's normalization function

    if not ticker:
        print("Error: Invalid asset ticker or not found.")
        return

    print("\nSelect asset classification for system risk analysis:")
    print("1. Stock  |  2. Bond  |  3. Derivative")
    asset_type = input("Selection (1-3): ")

    # Integrate risk control logic from UserProfile
    if asset_type == '3' and not user_profile.is_derivative_allowed():
        print("SYSTEM WARNING: Profile's risk tolerance is insufficient for Derivative trading.")
        return

    try:
        quantity = int(input("Enter quantity to buy: "))
    except ValueError:
        print("Error: Quantity must be an integer.")
        return

    price = get_live_price(ticker)
    if price == 0.0:
        print("Error: Unable to fetch live market price.")
        return

    # Initialize asset object based on Logic team's classes
    if asset_type == '1':
        asset = Stock(ticker, price, "General Market")
    elif asset_type == '2':
        asset = Bond(ticker, price, 5.0) # Assuming 5% coupon_rate
    elif asset_type == '3':
        asset = Derivatives(ticker, "Index")
        asset.current_price = price # Inherited attribute
    else:
        asset = Stock(ticker, price, "General Market")

    # Exception handling defined by Logic team
    try:
        portfolio.buy(asset, quantity)
        # Success message should be printed from logic's buy() function
    except InsufficientFundsError as e:
        print(f"\n[!] TRANSACTION DENIED (Insufficient Funds): {e}")
    except Exception as e:
        print(f"\n[!] UNKNOWN ERROR: {e}")

def sell_asset(portfolio):
    raw_ticker = input("Enter the asset ticker to sell: ")
    ticker = resolve_stock_ticker(raw_ticker)

    if not ticker:
         print("Error: Invalid asset ticker.")
         return

    try:
        quantity = int(input("Enter quantity to sell: "))
    except ValueError:
        print("Error: Quantity must be an integer.")
        return

    try:
        portfolio.sell_asset(ticker, quantity)
    except InsufficientSharesError as e:
        print(f"\n[!] TRANSACTION DENIED (Insufficient Shares): {e}")
    except Exception as e:
        print(f"\n[!] UNKNOWN ERROR: {e}")

def view_portfolio_text(portfolio, user_profile):
    """Person 2 prepares text data for display"""
    print("\n--- CURRENT PORTFOLIO DETAILS ---")
    print(f"Cash Balance: ${portfolio.cash_balance:,.2f}")

    if not portfolio.positions:
        print("Portfolio is empty. No assets purchased yet.")
        return

    total_value = portfolio.cash_balance
    print(f"{'TICKER':<10} | {'QUANTITY':<10} | {'AVG PRICE':<10} | {'CURRENT PRICE':<15} | {'P&L ($)':<10}")
    print("-" * 70)

    for ticker, pos in portfolio.positions.items():
        # Update to latest price before reporting
        live_price = get_live_price(ticker)
        if live_price > 0:
            pos.asset.current_price = live_price

        mkt_val = pos.market_value()
        pnl = pos.pnl()
        total_value += mkt_val

        print(f"{ticker:<10} | {pos.quantity:<10} | ${pos.avg_buy_price:<9.2f} | ${pos.asset.current_price:<14.2f} | ${pnl:<9.2f}")

    print("-" * 70)
    print(f"Total Portfolio Value (NAV): ${total_value:,.2f}")

    # Strategy Recommendation Feature
    target_weights = user_profile.get_target_weights()
    print(f"\nRecommended allocation based on '{user_profile.strategy}' strategy:")
    for asset_class, weight in target_weights.items():
        print(f"- {asset_class}: {weight}%")


# ==========================================
# VISUALIZATION / DASHBOARD
# ==========================================

def plot_portfolio_allocation(portfolio):
    weights = portfolio.get_portfolio_weights()

    # Filter out assets with 0 allocation
    filtered_weights = {k: v for k, v in weights.items() if v > 0}

    if not filtered_weights:
        print("No allocation data available to plot.")
        return

    labels = list(filtered_weights.keys())
    sizes = list(filtered_weights.values())

    plt.figure(figsize=(8, 6))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=plt.cm.Paired.colors)
    plt.title("Portfolio Asset Allocation")
    plt.axis('equal')
    plt.show()

def plot_asset_price_chart():
    raw_ticker = input("Enter asset ticker for chart (e.g., AAPL): ")
    ticker = resolve_stock_ticker(raw_ticker)
    if not ticker:
        print("Invalid asset ticker.")
        return

    print(f"Downloading 6-month historical data for {ticker}...")
    data = yf.download(ticker, period="6mo", progress=False)

    if data.empty:
        print("No price data found for this ticker.")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(data.index, data['Close'], label=f"Closing Price {ticker}", color='blue')
    plt.title(f"Historical Price Chart - {ticker} (Last 6 Months)")
    plt.xlabel("Time")
    plt.ylabel("Price (USD)")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.show()


# ==========================================
# USER INTERFACE (CLI)
# ==========================================

def run_dashboard():
    print("==================================================")
    print("       INVESTMENT PORTFOLIO DASHBOARD             ")
    print("==================================================")

    # 1. Collect initialization data for UserProfile & Portfolio
    print("\n[USER PROFILE SETUP]")
    name = input("Enter investor name: ")
    dob = input("Enter date of birth (YYYY-MM-DD): ")

    try:
        risk = int(input("Assess your risk tolerance (1-5): "))
        goal = float(input("Desired profit/savings goal ($): "))
        cash = float(input("Enter initial cash balance for investment ($): "))
    except ValueError:
        print("Input format error. System will use default values (Risk: 3, Goal: 10000, Cash: 10000).")
        risk, goal, cash = 3, 10000.0, 10000.0

    print("Choose a strategy (enter: buffett / graham / classical):")
    strategy = input().strip().lower()
    if strategy not in ['buffett', 'graham', 'classical']:
        strategy = 'classical'

    # Initialize Objects
    user = UserProfile(name, dob, risk, goal, strategy)
    portfolio = Portfolio(cash)

    print(f"\n-> Profile created for {user.name} ({user.age} years old) with {user.strategy} strategy.")

    # 2. Main Menu Loop
    while True:
        print("\n" + "="*40)
        print("                MAIN MENU                 ")
        print("="*40)
        print("1. Buy Asset")
        print("2. Sell Asset")
        print("3. View Asset List (Text)")
        print("4. View Portfolio Allocation (Pie Chart)")
        print("5. View Historical Price Chart (Line Chart)")
        print("6. Exit System")
        print("="*40)

        choice = input("Please select a function (1-6): ")

        if choice == '1':
            buy_asset(portfolio, user)
        elif choice == '2':
            sell_asset(portfolio)
        elif choice == '3':
            view_portfolio_text(portfolio, user)
        elif choice == '4':
            plot_portfolio_allocation(portfolio)
        elif choice == '5':
            plot_asset_price_chart()
        elif choice == '6':
            print("Exited the Dashboard system. Happy investing!")
            break
        else:
            print("Invalid selection, please enter a number from 1 to 6.")

# Execution Command for the Dashboard
if __name__ == "__main__":
    # Just call this function in the last cell to run the entire program
    run_dashboard()
import yfinance as yf
import matplotlib.pyplot as plt
import json
import os
from datetime import date

# ==========================================
# SIMPLE USER STORAGE (FIX LOGIN)
# ==========================================

USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)


# ==========================================
# PORTFOLIO OPERATIONS
# ==========================================

def get_live_price(ticker):
    try:
        return float(yf.Ticker(ticker).fast_info['lastPrice'])
    except Exception:
        return 0.0


def buy_asset(portfolio, user_profile):

    raw_ticker = input("Enter the asset ticker to buy (e.g., AAPL, TSLA): ")
    ticker = resolve_stock_ticker(raw_ticker)

    if not ticker:
        print("Error: Invalid asset ticker or not found.")
        return

    print("\nSelect asset classification for system risk analysis:")
    print("1. Stock  |  2. Bond  |  3. Derivative")
    asset_type = input("Selection (1-3): ")

    if asset_type == '3' and not user_profile.is_derivative_allowed():
        print("SYSTEM WARNING: Profile's risk tolerance is insufficient for Derivative trading.")
        return

    try:
        quantity = int(input("Enter quantity to buy: "))
    except ValueError:
        print("Error: Quantity must be an integer.")
        return

    price = get_live_price(ticker)

    if price == 0.0:
        print("Error: Unable to fetch live market price.")
        return

    if asset_type == '1':
        asset = Stock(ticker, price, "General Market")

    elif asset_type == '2':
        asset = Bond(ticker, price, 5.0)

    elif asset_type == '3':
        asset = Derivatives(ticker, "Index")
        asset.current_price = price

    else:
        asset = Stock(ticker, price, "General Market")

    try:
        portfolio.buy(asset, quantity)

    except InsufficientFundsError as e:
        print(f"\n[!] TRANSACTION DENIED (Insufficient Funds): {e}")

    except Exception as e:
        print(f"\n[!] UNKNOWN ERROR: {e}")


def sell_asset(portfolio):

    raw_ticker = input("Enter the asset ticker to sell: ")
    ticker = resolve_stock_ticker(raw_ticker)

    if not ticker:
        print("Error: Invalid asset ticker.")
        return

    try:
        quantity = int(input("Enter quantity to sell: "))
    except ValueError:
        print("Error: Quantity must be an integer.")
        return

    try:
        portfolio.sell_asset(ticker, quantity)

    except InsufficientSharesError as e:
        print(f"\n[!] TRANSACTION DENIED (Insufficient Shares): {e}")

    except Exception as e:
        print(f"\n[!] UNKNOWN ERROR: {e}")


def view_portfolio_text(portfolio, user_profile):

    print("\n--- CURRENT PORTFOLIO DETAILS ---")
    print(f"Cash Balance: ${portfolio.cash_balance:,.2f}")

    if not portfolio.positions:
        print("Portfolio is empty. No assets purchased yet.")
        return

    total_value = portfolio.cash_balance

    print(f"{'TICKER':<10} | {'QUANTITY':<10} | {'AVG PRICE':<10} | {'CURRENT PRICE':<15} | {'P&L ($)':<10}")
    print("-" * 70)

    for ticker, pos in portfolio.positions.items():

        live_price = get_live_price(ticker)

        if live_price > 0:
            pos.asset.current_price = live_price

        mkt_val = pos.market_value()
        pnl = pos.pnl()

        total_value += mkt_val

        print(f"{ticker:<10} | {pos.quantity:<10} | ${pos.avg_buy_price:<9.2f} | ${pos.asset.current_price:<14.2f} | ${pnl:<9.2f}")

    print("-" * 70)
    print(f"Total Portfolio Value (NAV): ${total_value:,.2f}")

    target_weights = user_profile.get_target_weights()

    print(f"\nRecommended allocation based on '{user_profile.strategy}' strategy:")

    for asset_class, weight in target_weights.items():
        print(f"- {asset_class}: {weight}%")


# ==========================================
# VISUALIZATION
# ==========================================

def plot_portfolio_allocation(portfolio):

    weights = portfolio.get_portfolio_weights()

    filtered_weights = {k: v for k, v in weights.items() if v > 0}

    if not filtered_weights:
        print("No allocation data available to plot.")
        return

    labels = list(filtered_weights.keys())
    sizes = list(filtered_weights.values())

    plt.figure(figsize=(8,6))

    plt.pie(
        sizes,
        labels=labels,
        autopct='%1.1f%%',
        startangle=140,
        colors=plt.cm.Paired.colors
    )

    plt.title("Portfolio Asset Allocation")

    plt.axis('equal')

    plt.show()


def plot_asset_price_chart():

    raw_ticker = input("Enter asset ticker for chart (e.g., AAPL): ")

    ticker = resolve_stock_ticker(raw_ticker)

    if not ticker:
        print("Invalid asset ticker.")
        return

    print(f"Downloading 6-month historical data for {ticker}...")

    data = yf.download(ticker, period="6mo", progress=False)

    if data.empty:
        print("No price data found for this ticker.")
        return

    plt.figure(figsize=(10,5))

    plt.plot(data.index, data['Close'], label=f"Closing Price {ticker}")

    plt.title(f"Historical Price Chart - {ticker} (Last 6 Months)")

    plt.xlabel("Time")

    plt.ylabel("Price (USD)")

    plt.grid(True)

    plt.legend()

    plt.show()


# ==========================================
# DASHBOARD
# ==========================================

def run_dashboard():

    print("==================================================")
    print("       INVESTMENT PORTFOLIO DASHBOARD             ")
    print("==================================================")

    print("\n[USER PROFILE SETUP]")

    users = load_users()

    name = input("Enter investor name: ")

    # FIX LOGIN
    if name in users:
        print(f"Welcome back {name}")
        dob = users[name]

    else:

        # FIX DOB ERROR
        while True:

            dob = input("Enter date of birth (YYYY-MM-DD): ")

            try:
                date.fromisoformat(dob)
                break

            except ValueError:
                print("Invalid DOB format. Please use YYYY-MM-DD.")

        users[name] = dob
        save_users(users)

    try:

        risk = int(input("Assess your risk tolerance (1-5): "))

        goal = float(input("Desired profit/savings goal ($): "))

        # FIX LOGIC ERROR
        while True:

            cash = float(input("Enter initial cash balance for investment ($): "))

            if cash <= goal:
                break

            else:
                print("Initial cash cannot exceed goal. Please re-enter.")

    except ValueError:

        print("Input format error. System will use default values.")

        risk, goal, cash = 3, 10000.0, 10000.0

    print("Choose a strategy (enter: buffett / graham / classical):")

    strategy = input().strip().lower()

    if strategy not in ['buffett','graham','classical']:
        strategy = 'classical'

    user = UserProfile(name, dob, risk, goal, strategy)

    portfolio = Portfolio(cash)

    print(f"\n-> Profile created for {user.name} ({user.age} years old) with {user.strategy} strategy.")

    while True:

        print("\n"+"="*40)

        print("MAIN MENU")

        print("="*40)

        print("1. Buy Asset")
        print("2. Sell Asset")
        print("3. View Asset List")
        print("4. View Portfolio Allocation")
        print("5. View Historical Price Chart")
        print("6. Exit System")

        choice = input("Select (1-6): ")

        if choice == '1':
            buy_asset(portfolio, user)

        elif choice == '2':
            sell_asset(portfolio)

        elif choice == '3':
            view_portfolio_text(portfolio, user)

        elif choice == '4':
            plot_portfolio_allocation(portfolio)

        elif choice == '5':
            plot_asset_price_chart()

        elif choice == '6':
            print("Exited Dashboard.")
            break

        else:
            print("Invalid selection.")


if __name__ == "__main__":
    run_dashboard()
