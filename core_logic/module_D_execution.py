# ============================================
# core_logic/module_D_execution.py (TSLA 5-min RSI Short-term Strategy - Cleaned)
# ============================================

import logging
import pandas as pd
from typing import List, Optional, Dict
import numpy as np
import pandas_ta as ta

from ib_insync import IB, Contract, util
from config.parameters import TSLA_TICKER, TSLA_SHORT_TERM_RSI_OVERSOLD, TSLA_SHORT_TERM_RSI_PERIOD

# --- Helper Functions ---

def calculate_min5_rsi(data_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates RSI for the 5-minute data using pandas-ta."""
    if data_df.empty:
        return data_df

    # Use pandas_ta (confirmed installed)
    if len(data_df) > TSLA_SHORT_TERM_RSI_PERIOD:
        # data_df = data_df.copy() # Avoid SettingWithCopyWarning
        data_df['RSI'] = ta.rsi(data_df.close, length=TSLA_SHORT_TERM_RSI_PERIOD)
    else:
        # Fill with NaN if not enough data to calculate
        data_df['RSI'] = float('nan')

    return data_df

# --- Core Logic ---

def run_tsla_min5_analysis(ib: IB, contract: Contract) -> Optional[Dict]:
    """
    Fetches 5-min data for TSLA and checks the RSI < 10 signal.
    
    Returns: A signal dictionary or None.
    """

    # 1. Request 5-minute historical data (API Abuse Fix)
    try:
        logging.info(f"Module D: Requesting {TSLA_TICKER} (5 Min Bar) for RSI Test...")
        # FIX: durationStr='3 D' is used to get just enough data to calculate 14-period RSI reliably, 
        # but prevents the system from hammering the API every minute for a whole week of data.
        min5_bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='3 D',
            barSizeSetting='5 mins',
            whatToShow='TRADES',
            useRTH=True,
        )
    except Exception as e:
        logging.error(f"Module D: Error fetching 5-min data for {TSLA_TICKER}: {e}")
        return None

    if not min5_bars:
        logging.warning(f"Module D: Failed to retrieve 5-min bars for {TSLA_TICKER}.")
        return None

    min5_df = util.df(min5_bars).set_index('date')
    min5_df.index = pd.to_datetime(min5_df.index)
    min5_df = calculate_min5_rsi(min5_df)

    # 2. Check RSI Signal
    if not min5_df.empty and 'RSI' in min5_df.columns:
        valid_df = min5_df.dropna(subset=['RSI'])
        if valid_df.empty:
            logging.info("Module D: Not enough data points for valid RSI calculation.")
            return None

        latest = valid_df.iloc[-1]

        # Rule: 5-min RSI drops below 10, generates a buy signal.
        if latest['RSI'] < TSLA_SHORT_TERM_RSI_OVERSOLD:
            
            # **Calculate Stop Loss Level (Short-term strategy)**
            # Strategy: Use the Low of the latest 5-min bar as the initial hard stop.
            stop_level = latest['low']
            
            # Use the closing price of the 5-min bar as the entry limit price reference
            entry_price = latest['close']
            
            # Sanity check: ensure entry price is above the stop level for a BUY order
            if entry_price <= stop_level:
                 logging.warning(f"Module D: Entry price {entry_price:.2f} is not above stop {stop_level:.2f}. Signal rejected.")
                 return None

            signal = {
                'symbol': TSLA_TICKER, 
                'action': 'BUY', 
                'price': entry_price,
                'stop_level': stop_level, 
                'signal_source': 'Module D'
            }
            logging.warning(f"MODULE D SHORT-TERM SIGNAL: BUY for {TSLA_TICKER} (RSI={latest['RSI']:.2f}). Stop @ {stop_level:.2f}.")
            return signal 

    return None

