# --- FINANCIAL & RISK MANAGEMENT (MODULE C) ---
ARC_CAPITAL = 100000.0      # Allowable Risk Capital for testing
MAX_RISK_PER_TRADE = 1500.0 # Max loss per trade ($100k * 1.5%)
MAX_TOTAL_DRAWDOWN_PCT = 0.15 # System stop loss (15% of ARC)

# === NEW: CAPITAL ALLOCATION SETTINGS ===
LONG_TERM_CAPITAL_RATIO = 0.80  # 80% capital for long-term (Module B)
SHORT_TERM_CAPITAL_RATIO = 0.20 # 20% capital for short-term (Module D)

# --- MODULE A: TREND FILTER ---
SMA_PERIOD = 200            # Period for long-term Simple Moving Average
SMA_SLOPE_WINDOW = 20       # Number of bars to calculate SMA slope via linear regression
SLOPE_THRESHOLD = 0.001     # Minimum slope value to be considered 'rising'

# --- MODULE B: SIGNAL GENERATION ---
RSI_PERIOD = 14
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VOLUME_PERIOD = 50          # Period for Volume Moving Average

# === NEW: MODULE D (TSLA SHORT-TERM) SETTINGS ===
TSLA_TICKER = 'TSLA'
TSLA_SHORT_TERM_RSI_OVERSOLD = 10 # RSI threshold for 5-min buy signal
TSLA_SHORT_TERM_RSI_PERIOD = 14
TSLA_SHORT_TERM_MAX_POS_SIZE_RATIO = 0.05 # Max risk per trade (e.g., 5% of the 20% short-term capital)

# --- MODULE C: EXECUTION & TRAILING STOP ---
TIF_SECONDS = 300           # Time-In-Force: 5 minutes for Limit Order retry
MAX_RETRY_COUNT = 3         # Max attempts to fill a limit order
TICK_ADJUSTMENT = 0.01      # Price adjustment per retry attempt (e.g., 1 cent)
ATR_PERIOD = 14             # ATR period for volatility calculation (Daily Bars)
ATR_MULTIPLIER = 3          # Trailing stop distance multiplier (3 * ATR)


# --- IB 連線參數 ---
IB_HOST = '127.0.0.1'       # 本地 IP
IB_PORT = 4002              # 模擬盤端口
IB_CLIENT_ID = 50           # 客戶端 ID


