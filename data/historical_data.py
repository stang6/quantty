# ============================================
# data/historical_data.py (Helper Functions for Ticker Loading/Contract Creation)
# ============================================
import pandas as pd
import logging
import os
from ib_insync import IB, Contract, Stock, util
from typing import List

def load_tickers_from_file(file_path: str = 'config/tickers.txt') -> List[str]:
    """
    Loads a list of stock tickers from a file, ignoring comments and empty lines.
    """
    tickers = []
    try:
        # Construct the full path relative to the quantty directory
        # The os.path logic provided here is correct for robust path resolution
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
        logging.critical(f"Ticker file not found at {full_path}. Cannot start trading system.")
    except Exception as e:
        logging.critical(f"Error loading tickers: {e}")

    return tickers

def create_stock_contract(ticker: str) -> Contract:
    """Helper function to create a standard US Stock Contract object."""
    # ib_insync simplifies contract creation
    return Stock(ticker, 'SMART', 'USD')

