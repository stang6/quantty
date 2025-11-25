# ============================================
# core_logic/module_B_signals.py (Updated with DUMMY TEST SIGNAL)
# ============================================

import logging
import pandas as pd
from config.parameters import * # Import all parameters
from typing import List, Dict, Optional


def generate_signals(filtered_symbols: List[str], current_prices: Dict) -> List[Dict]:
    """
    Calculate RSI/MACD indicators and generate Buy/Sell signals (Module B).

    :param filtered_symbols: List of symbols filtered by Module A (long-term trend).
    :param current_prices: Latest prices for the stocks.
    :return: List containing signals (e.g., [{'symbol': 'TSLA', 'action': 'BUY', 'price': 180.50}])
    """
    logging.info("Module B: Calculating indicators and generating signals...")

    # For initial testing, return a sample signal (Placeholder logic)
    if 'TSLA' in filtered_symbols:
        return [{'symbol': 'TSLA', 'action': 'BUY', 'price': 180.50}]

    return []


def calculate_indicators(data_df):
    """Calculates all necessary indicators (RSI, MACD, ATR, Volume MA)."""

    # 1. RSI Calculation
    delta = data_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
    RS = gain / loss
    data_df['RSI'] = 100 - (100 / (1 + RS))

    # 2. MACD Calculation
    data_df['EMA_Fast'] = data_df['close'].ewm(span=MACD_FAST, adjust=False).mean()
    data_df['EMA_Slow'] = data_df['close'].ewm(span=MACD_SLOW, adjust=False).mean()
    data_df['MACD'] = data_df['EMA_Fast'] - data_df['EMA_Slow']
    data_df['Signal_Line'] = data_df['MACD'].ewm(span=MACD_SIGNAL, adjust=False).mean()

    # 3. Volume Confirmation
    data_df['Volume_MA'] = data_df['volume'].rolling(window=VOLUME_PERIOD).mean() # Corrected: used 'volume' column

    # 4. ATR Calculation (Needed for Trailing Stop)
    # True Range calculation: Max([H-L], |H-PC|, |L-PC|)
    data_df['H-L'] = data_df['high'] - data_df['low']
    data_df['H-PC'] = abs(data_df['high'] - data_df['close'].shift(1))
    data_df['L-PC'] = abs(data_df['low'] - data_df['close'].shift(1))
    data_df['TR'] = data_df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    data_df['ATR'] = data_df['TR'].rolling(window=ATR_PERIOD).mean()

    return data_df

def generate_buy_signal(data_df, is_trend_up):
    """Generates the final buy signal based on multi-factor confirmation."""

    # --- START OF DUMMY TEST LOGIC (TO BE REMOVED AFTER TESTING) ---
    # This logic forces a BUY signal for all tickers that passed the trend filter (Module A).
    if is_trend_up:
        logging.warning("TEST OVERRIDE: Forcing BUY signal for current ticker (to test Module C execution).")
        return True
    # --- END OF DUMMY TEST LOGIC ---


    if not is_trend_up or data_df.empty:
        return False

    latest = data_df.iloc[-1]

    # Condition 1: RSI Oversold/Rebound Check
    rsi_current_rebound = latest['RSI'] > RSI_OVERSOLD

    # Condition 2: MACD Momentum Activation (Cross Up)
    macd_cross_up = latest['MACD'] > latest['Signal_Line'] and \
                    data_df.iloc[-2]['MACD'] <= data_df.iloc[-2]['Signal_Line']

    # Condition 3: Volume Confirmation
    volume_confirmation = latest['volume'] > latest['Volume_MA'] # Final check: volume confirmation

    # Final Combined Signal
    if rsi_current_rebound and macd_cross_up and volume_confirmation:
        return True

    return False
