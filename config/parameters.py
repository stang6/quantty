
# ============================================
# config/parameters.py (Cleaned and Optimized for Event-Driven Risk Logic)
# ============================================

# --- FINANCIAL & RISK MANAGEMENT (MODULE C) ---
ARC_CAPITAL = 100000.0         # Total Allowable Risk Capital
# IMPORTANT: MAX_RISK_PER_TRADE is now a PERCENTAGE (1.5% of allocated capital)
MAX_RISK_PER_TRADE_PCT = 0.015 # Max loss per trade (1.5% based on your $1500/$100k)
MAX_TOTAL_DRAWDOWN_PCT = 0.15  # System stop loss (15% of ARC)

# === CAPITAL ALLOCATION SETTINGS ===
LONG_TERM_CAPITAL_RATIO = 0.80 # 80% capital for long-term (Module B)
SHORT_TERM_CAPITAL_RATIO = 0.20 # 20% capital for short-term (Module D)

# --- MODULE A: TREND FILTER ---
SMA_PERIOD = 200               # Period for long-term Simple Moving Average
SMA_SLOPE_WINDOW = 20          # Number of bars to calculate SMA slope
SLOPE_THRESHOLD = 0.001        # Minimum slope value

# --- MODULE B: SIGNAL GENERATION ---
RSI_PERIOD = 14
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VOLUME_PERIOD = 50             # Period for Volume Moving Average

# --- MODULE C: STOP LOSS & EXECUTION ---
TICK_ADJUSTMENT = 0.01         # Price adjustment for Limit Order slippage/retry (1 cent)
ATR_PERIOD = 14                # ATR period for volatility calculation (Daily Bars)
ATR_MULTIPLIER = 3.0           # Trailing stop distance multiplier (3 * ATR)

# === MODULE D (TSLA SHORT-TERM) SETTINGS ===
TSLA_TICKER = 'TSLA'
TSLA_SHORT_TERM_RSI_OVERSOLD = 10 # RSI threshold for 5-min buy signal
TSLA_SHORT_TERM_RSI_PERIOD = 14


# --- IB 連線參數 ---
IB_HOST = '127.0.0.1'
IB_PORT = 4002                 # Paper Trading Port (usually 4002 or 7497)
IB_CLIENT_ID = 50

