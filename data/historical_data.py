# ============================================
# data/historical_data.py (Final Version with Ticker Loading)
# ============================================
import pandas as pd
import logging
import os
from ib_insync import IB, Contract, Stock, util
from typing import List

def load_tickers_from_file(file_path: str = 'config/tickers.txt') -> List[str]:
    """
    Loads a list of stock tickers from a file, ignoring comments and empty lines.

    :param file_path: Path to the ticker list file.
    :return: List of clean ticker symbols.
    """
    tickers = []
    try:
        # Construct the full path relative to the quantty directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, file_path)

        with open(full_path, 'r') as f:
            for line in f:
                # Remove leading/trailing whitespace and split by comment marker (#)
                ticker = line.strip().split('#')[0]
                if ticker:
                    tickers.append(ticker.upper())
        logging.info(f"Successfully loaded {len(tickers)} tickers from {file_path}.")
    except FileNotFoundError:
        # This will be handled in main.py, but good to log here too
        logging.critical(f"Ticker file not found at {file_path}. Cannot start trading system.")
    except Exception as e:
        logging.critical(f"Error loading tickers: {e}")
        
    return tickers

def create_stock_contract(ticker: str) -> Contract:
    """Helper function to create a standard US Stock Contract object."""
    # ib_insync simplifies contract creation
    return Stock(ticker, 'SMART', 'USD')

def request_historical_data_ibinsync(ib: IB, ticker: str, duration_str: str = "2 Y") -> pd.DataFrame:
    """
    Requests historical daily bar data via ib_insync.

    :param ib: The connected IB instance.
    :param ticker: Stock ticker (e.g., 'TSLA').
    :param duration_str: Data time length (e.g., '730 D' for 2 years of Daily bars).
    :return: DataFrame containing historical price data.
    """
    logging.info(f"Requesting historical data for {ticker}...")

    contract = create_stock_contract(ticker)

    # Synchronous request to wait for data return
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='', # '' means now
        durationStr=duration_str,
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1
    )

    if not bars:
        logging.error(f"Failed to retrieve historical data for {ticker}.")
        return pd.DataFrame()

    # Convert Bars to DataFrame
    data_df = util.df(bars)

    # Clean up and format
    data_df.set_index('date', inplace=True)
    data_df.index = pd.to_datetime(data_df.index)
    data_df = data_df[['open', 'high', 'low', 'close', 'volume']] # Ensure consistent column names

    logging.info(f"Successfully retrieved {len(data_df)} bars for {ticker}.")
    return data_df
