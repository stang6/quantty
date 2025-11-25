# ============================================
# module_D_execution.py — Short-Term Strategy Engine
# Supports: RSI, MACD, future strategies
# Config-driven thresholds
# ============================================

import pandas as pd
from ib_insync import util

from config.parameters import (
    SHORT_TERM_DURATION,
    SHORT_TERM_BAR_SIZE,

    # RSI Config
    SHORT_RSI_PERIOD,
    SHORT_RSI_BUY_THRESHOLD,
    SHORT_RSI_SELL_THRESHOLD,

    # MACD Config
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL
)

# ======================================================
# Common Technical Indicators
# ======================================================

def calc_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    hist = macd - signal_line
    return macd, signal_line, hist


# ======================================================
# Strategy Implementations
# ======================================================

def strategy_RSI(df):
    """
    Simple RSI strategy:
      BUY  when RSI < SHORT_RSI_BUY_THRESHOLD
      SELL when RSI > SHORT_RSI_SELL_THRESHOLD
    """
    close = df['close']
    rsi = calc_rsi(close, SHORT_RSI_PERIOD)

    latest_rsi = rsi.iloc[-1]
    latest_price = close.iloc[-1]

    if latest_rsi < SHORT_RSI_BUY_THRESHOLD:
        return {
            "action": "BUY",
            "price": float(latest_price),
            "source": f"RSI<{SHORT_RSI_BUY_THRESHOLD}"
        }

    if latest_rsi > SHORT_RSI_SELL_THRESHOLD:
        return {
            "action": "SELL",
            "price": float(latest_price),
            "source": f"RSI>{SHORT_RSI_SELL_THRESHOLD}"
        }

    return None


def strategy_MACD(df):
    """
    Standard MACD strategy:
      BUY  when MACD crosses above signal
      SELL when MACD crosses below signal
    """
    close = df['close']

    macd, signal, hist = calc_macd(
        close,
        fast=MACD_FAST,
        slow=MACD_SLOW,
        signal=MACD_SIGNAL
    )

    # Check last 2 values for cross signals
    macd_prev, macd_now = macd.iloc[-2], macd.iloc[-1]
    sig_prev, sig_now = signal.iloc[-2], signal.iloc[-1]

    price_now = close.iloc[-1]

    # Golden cross (buy)
    if macd_prev < sig_prev and macd_now > sig_now:
        return {
            "action": "BUY",
            "price": float(price_now),
            "source": "MACD Golden Cross"
        }

    # Death cross (sell)
    if macd_prev > sig_prev and macd_now < sig_now:
        return {
            "action": "SELL",
            "price": float(price_now),
            "source": "MACD Death Cross"
        }

    return None


# ======================================================
# Strategy dispatcher (plug-in system)
# ======================================================

STRATEGY_MAP = {
    "RSI": strategy_RSI,
    "MACD": strategy_MACD,
}


# ======================================================
# Main short-term strategy runner
# ======================================================

def run_short_term_strategy(ib, contract, strategy_name="RSI"):
    """
    Runs a short-term strategy on ANY stock, ANY method.
    Returns:
        dict: {action, price, source} or None
    """

    strategy_fn = STRATEGY_MAP.get(strategy_name)
    if not strategy_fn:
        return None

    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=SHORT_TERM_DURATION,
        barSizeSetting=SHORT_TERM_BAR_SIZE,
        whatToShow="TRADES",
        useRTH=False,
        formatDate=1
    )

    if not bars:
        return None

    df = util.df(bars).set_index("date")
    df.index = pd.to_datetime(df.index)

    # Run the selected strategy
    sig = strategy_fn(df)
    if sig:
        sig["ticker"] = contract.symbol

    return sig

