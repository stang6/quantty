# ============================================
# core_logic/module_D_execution.py (TSLA 5-min RSI Short-term Strategy)
# ============================================

import logging
import pandas as pd
from typing import List

from ib_insync import IB, Contract, util
from config.parameters import TSLA_TICKER, TSLA_SHORT_TERM_RSI_OVERSOLD, TSLA_SHORT_TERM_RSI_PERIOD

# --- Helper Functions ---

def calculate_min5_rsi(data_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates RSI for the 5-minute data."""
    if data_df.empty:
        return data_df

    # Check if we have enough data points (RSI period requires sufficient bars)
    if len(data_df) > TSLA_SHORT_TERM_RSI_PERIOD:
        # Use ib_insync utility for RSI calculation
        data_df['RSI'] = util.rsi(data_df.close, TSLA_SHORT_TERM_RSI_PERIOD)
    else:
        # Fill with NaN if not enough data to calculate
        data_df['RSI'] = float('nan')

    return data_df

# --- Core Logic ---

def run_tsla_min5_analysis(ib: IB, contract: Contract) -> List[str]:
    """
    Fetches 5-min data for TSLA and checks the RSI < 10 signal.
    Returns: A list of signal tickers (['TSLA'] or []).
    """

    # 1. Request 5-minute historical data
    try:
        logging.info(f"Module D: Requesting {TSLA_TICKER} (5 Min Bar) for RSI Test...")
        # NOTE: durationStr='1 W' is used to get enough 5-min bars without hitting API limits
        min5_bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='1 W',
            barSizeSetting='5 mins',
            whatToShow='TRADES',
            useRTH=True,
        )
    except Exception as e:
        logging.error(f"Module D: Error fetching 5-min data for {TSLA_TICKER}: {e}")
        return []

    if not min5_bars:
        logging.warning(f"Module D: Failed to retrieve 5-min bars for {TSLA_TICKER}.")
        return []

    min5_df = util.df(min5_bars)
    min5_df = calculate_min5_rsi(min5_df)

    # 2. Check RSI Signal
    if not min5_df.empty and 'RSI' in min5_df.columns:
        # Filter out NaN RSI values and get the latest complete row
        valid_df = min5_df.dropna(subset=['RSI'])
        if valid_df.empty:
            logging.info("Module D: Not enough data points for valid RSI calculation.")
            return []

        latest = valid_df.iloc[-1]

        # Rule: 5-min RSI drops below 10, generates a buy signal.
        if latest['RSI'] < TSLA_SHORT_TERM_RSI_OVERSOLD:
            logging.warning(f"MODULE D SHORT-TERM SIGNAL: BUY signal generated for {TSLA_TICKER} (RSI={latest['RSI']:.2f}).")
            return [TSLA_TICKER] # Return the signal ticker

    return []
