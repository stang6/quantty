# ============================================
# core_logic/module_B_signals.py (Cleaned and Stop-Loss Added)
# ============================================

import logging
import pandas as pd

from config.parameters import *
from typing import List, Dict, Optional, Tuple
import numpy as np

# Helper function to check if a Pandas Series contains enough non-NaN data
def is_data_sufficient(data_series: pd.Series, required_count: int) -> bool:
    """Checks if a series has enough non-NaN values for calculation."""
    return data_series.dropna().shape[0] >= required_count

def calculate_indicators(data_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates all necessary indicators (RSI, MACD, ATR, Volume MA)."""

    # Make a copy to avoid SettingWithCopyWarning
    df = data_df.copy()

    # 1. RSI Calculation
    # Note: Using standard pandas EWMA calculation.
    if is_data_sufficient(df['close'], RSI_PERIOD):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
        RS = gain / loss
        df['RSI'] = 100 - (100 / (1 + RS))
    else:
        df['RSI'] = np.nan

    # 2. MACD Calculation
    if is_data_sufficient(df['close'], MACD_SLOW):
        df['EMA_Fast'] = df['close'].ewm(span=MACD_FAST, adjust=False).mean()
        df['EMA_Slow'] = df['close'].ewm(span=MACD_SLOW, adjust=False).mean()
        df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
        df['Signal_Line'] = df['MACD'].ewm(span=MACD_SIGNAL, adjust=False).mean()
    else:
        df[['MACD', 'Signal_Line']] = np.nan

    # 3. Volume Confirmation
    if is_data_sufficient(df['volume'], VOLUME_PERIOD):
        df['Volume_MA'] = df['volume'].rolling(window=VOLUME_PERIOD).mean()
    else:
        df['Volume_MA'] = np.nan

    # 4. ATR Calculation (Needed for Trailing Stop)
    # True Range calculation: Max([H-L], |H-PC|, |L-PC|)
    if is_data_sufficient(df['close'], ATR_PERIOD + 1):
        df['H-L'] = df['high'] - df['low']
        df['H-PC'] = abs(df['high'] - df['close'].shift(1))
        df['L-PC'] = abs(df['low'] - df['close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=ATR_PERIOD).mean()
    else:
        df['ATR'] = np.nan

    return df


def generate_buy_signal(data_df: pd.DataFrame, is_trend_up: bool) -> bool:
    """Generates the final buy signal based on multi-factor confirmation."""

    if not is_trend_up or data_df.empty or data_df.iloc[-1].isnull().any():
        return False

    latest = data_df.iloc[-1]
    
    # Ensure all required indicators have valid values
    if pd.isna(latest['RSI']) or pd.isna(latest['MACD']) or pd.isna(latest['Volume_MA']):
        return False

    # Condition 1: RSI Oversold/Rebound Check
    rsi_current_rebound = latest['RSI'] > RSI_OVERSOLD

    # Condition 2: MACD Momentum Activation (Cross Up)
    # Must check the previous bar to confirm the cross
    if len(data_df) < 2: return False
    prev = data_df.iloc[-2]
    
    macd_cross_up = latest['MACD'] > latest['Signal_Line'] and \
                    prev['MACD'] <= prev['Signal_Line']

    # Condition 3: Volume Confirmation
    volume_confirmation = latest['volume'] > latest['Volume_MA'] 

    # Final Combined Signal
    if rsi_current_rebound and macd_cross_up and volume_confirmation:
        return True

    return False


def generate_signals(ticker: str, data_df: pd.DataFrame, is_trend_up: bool) -> Optional[Dict]:
    """
    Calculate indicators and generate Buy/Sell signals (Module B).
    
    :param ticker: The symbol being analyzed.
    :param data_df: Daily historical data.
    :param is_trend_up: Result from Module A filter.
    :return: A signal dictionary or None.
    """
    if data_df.empty:
        return None

    # 1. Calculate Indicators
    try:
        data_df = calculate_indicators(data_df)
    except Exception as e:
        logging.error(f"Module B: Error calculating indicators for {ticker}: {e}")
        return None

    # 2. Generate Buy Signal
    if generate_buy_signal(data_df, is_trend_up):
        latest = data_df.iloc[-1]
        
        # 3. Calculate Stop Loss Level (Using ATR for Module B Long-term strategy)
        if pd.isna(latest['ATR']):
            logging.warning(f"Module B: ATR is NaN for {ticker}. Cannot set stop loss.")
            return None

        # Stop Loss = Today's Close - (ATR * Multiplier)
        trailing_stop_level = latest['close'] - latest['ATR'] * ATR_MULTIPLIER
        
        signal = {
            'symbol': ticker, 
            'action': 'BUY', 
            'price': latest['close'], # Use the closing price as the limit price reference
            'stop_level': trailing_stop_level, 
            'signal_source': 'Module B'
        }
        logging.warning(f"Module B Signal: BUY for {ticker}. Stop @ {trailing_stop_level:.2f}.")
        return signal

    return None

