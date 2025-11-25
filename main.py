
# ============================================
# main.py (REFACTORED: Event-Driven Architecture with Data Caching)
# ============================================

import os
import sys
import logging
import time
from typing import List, Dict, Tuple, Optional
import pandas as pd
from datetime import datetime, time, timedelta

# Data directory
DATA_DIR = 'historical_data'

# configs from config.parameters
from config.parameters import IB_HOST, IB_PORT, IB_CLIENT_ID, TSLA_TICKER
from utils.system_logging import setup_logging # Assuming this utility exists
from ib_insync import IB, util, Contract, Stock

# core logic modules
from core_logic.module_A_filter import check_long_term_filter
from core_logic import module_B_signals
from core_logic import module_C_execution
from core_logic import module_D_execution
from data.historical_data import create_stock_contract, load_tickers_from_file # Re-used helpers


# --- Data Caching Helpers ---

def save_historical_data_to_csv(data_df: pd.DataFrame, ticker: str):
    """Saves the historical DataFrame to a CSV file in the designated directory."""
    if data_df.empty:
        logging.warning(f"Attempted to save empty DataFrame for {ticker}. Skipping save.")
        return

    HISTORICAL_DATA_DIR = DATA_DIR
    os.makedirs(HISTORICAL_DATA_DIR, exist_ok=True)
    file_path = os.path.join(HISTORICAL_DATA_DIR, f"{ticker}_1day.csv")

    try:
        # Save with date index
        data_df.to_csv(file_path, index=True)
        logging.info(f"Historical data successfully saved to {file_path}")
    except Exception as e:
        logging.error(f"Failed to save data for {ticker} to {file_path}: {e}")

def load_historical_data_from_csv(ticker: str) -> pd.DataFrame:
    """Loads historical data from CSV cache if available."""
    HISTORICAL_DATA_DIR = DATA_DIR
    file_path = os.path.join(HISTORICAL_DATA_DIR, f"{ticker}_1day.csv")

    if os.path.exists(file_path):
        try:
            # Load and parse date index correctly
            data_df = pd.read_csv(file_path, index_col='date', parse_dates=True)
            # Ensure consistent column names
            if not all(col in data_df.columns for col in ['open', 'high', 'low', 'close', 'volume']):
                 logging.error(f"CSV for {ticker} missing expected columns. Re-downloading.")
                 return pd.DataFrame()

            data_df = data_df[['open', 'high', 'low', 'close', 'volume']] 
            logging.info(f"Loaded {len(data_df)} bars for {ticker} from local cache.")
            return data_df
        except Exception as e:
            logging.error(f"Failed to load data for {ticker} from CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- QuantDaemon Class (Core Event-Driven Logic) ---

class QuantDaemon:
    
    def __init__(self, ib: IB):
        self.ib = ib
        self.tickers = load_tickers_from_file()
        self.contracts = [create_stock_contract(t) for t in self.tickers]
        
        # Tickers that passed Module A (Trend filter)
        self.approved_tickers: List[str] = [] 
        # Signals to be executed in Module C: {ticker: {'action', 'stop_level', 'signal_source', 'price'}}
        self.pending_signals: Dict[str, Dict] = {} 
        
        logging.info("QuantDaemon initialized.")

    def start(self):
        """Starts the main trading loop and schedules tasks."""
        
        # 1. Subscribe to Live Market Data (Non-blocking)
        self._subscribe_live_market_data()
        
        # 2. Initialization: Run Module A/B once to get initial data and trend status
        self.run_daily_analysis()
        
        # 3. Define and Schedule Tasks (Times are typically in UTC/IBKR time, here using CST for example)
        
        # Task A: Daily Analysis (Module A/B, Cache Update)
        # Runs daily after market close (e.g., 5:00 AM CST)
        self.ib.schedule(
            time(hour=5, minute=0), 
            self.run_daily_analysis
        )
        
        # Task B: Short-term Analysis (Module D: TSLA 5-min)
        # Runs every 5 minutes during trading hours (e.g., starting 21:30 CST)
        # NOTE: We set repeat_interval to 300 (5 minutes) to respect the strategy's timeframe
        self.ib.schedule(
            time(hour=21, minute=30), 
            self.run_min5_analysis, 
            repeat_interval=300 
        )

        # Task C: Execution and Monitoring Heartbeat (Module C)
        # Runs every 60 seconds to check fills, manage orders, and check internal stop loss
        self.ib.schedule(
            time(hour=0, minute=0), 
            self.run_execution_monitor,
            repeat_interval=60
        )
        
        logging.info("Scheduled tasks. Entering event loop (ib.run())...")
        self.ib.run() # Start the non-blocking event loop


    def _subscribe_live_market_data(self):
        """Subscribe to continuous market data for all contracts (for Module C stop check)."""
        logging.info(f"Subscribing to live market data for {len(self.contracts)} contracts...")
        for contract in self.contracts:
            # Snapshot=False ensures a continuous stream, which is stored in ib.tickerOf(contract)
            self.ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)
        
        # Also subscribe to account updates and open orders for Module C
        self.ib.reqAccountUpdates(True, self.ib.wrapper.accounts[0]) # Assuming first account
        self.ib.reqAllOpenOrders()


    def run_daily_analysis(self):
        """
        Task A: Runs Module A/B (Trend and Long-term signal) using Caching/Incremental Update. 
        """
        logging.warning("--- RUNNING DAILY ANALYSIS (Module A/B: Check Cache) ---")
        self.approved_tickers = []
        today = datetime.now().date()
        
        for contract in self.contracts:
            ticker = contract.symbol
            data_df = load_historical_data_from_csv(ticker) 
            
            # --- 1. Data Retrieval Logic (Caching + Incremental Update) ---
            if data_df.empty or data_df.index.max().date() < today:
                
                # If cache is missing OR stale, we request the required data
                # Request 2 Years (Y) for initial setup, or 2 Days (D) for incremental update
                duration_str = "2 Y" if data_df.empty else "2 D"
                
                logging.info(f"Cache {('stale' if not data_df.empty else 'missing')} for {ticker}. Requesting {duration_str} data.")
                
                bars = self.ib.reqHistoricalData(
                    contract, endDateTime='', durationStr=duration_str, barSizeSetting='1 day',
                    whatToShow='TRADES', useRTH=True, formatDate=1
                )
                
                if not bars:
                    logging.error(f"Historical data download failed for {ticker}.")
                    continue
                
                new_df = util.df(bars).set_index('date')
                new_df.index = pd.to_datetime(new_df.index)
                new_df = new_df[['open', 'high', 'low', 'close', 'volume']] 
                
                if not data_df.empty:
                    # Merge existing data with new data (only take new rows)
                    data_df = pd.concat([data_df, new_df[new_df.index > data_df.index.max()]])
                else:
                    data_df = new_df
                
                data_df.drop_duplicates(inplace=True)
                save_historical_data_to_csv(data_df, ticker) 

            else:
                logging.info(f"Cache for {ticker} is up-to-date ({data_df.index.max().date()}). Skipping download.")

            # --- 2. Module A/B Analysis ---
            
            # Must have at least 500 bars for accurate 200 SMA/Slope calc
            if len(data_df) < 500:
                logging.warning(f"Not enough data for {ticker} to run Module A/B analysis.")
                continue
                
            is_trend_up = check_long_term_filter(data_df)

            if is_trend_up:
                self.approved_tickers.append(ticker)
                
                # Module B returns the signal dict with stop_level
                signal = module_B_signals.generate_signals(ticker, data_df, is_trend_up)
                
                if signal:
                    # Store signal dict for Module C execution
                    self.pending_signals[ticker] = signal
            
        logging.warning(f"Daily Analysis Complete. Approved tickers: {self.approved_tickers}. Pending long-term signals: {list(self.pending_signals.keys())}")
        
    
    def run_min5_analysis(self):
        """
        Task B: Runs Module D (TSLA 5-min signal).
        Runs every 5 minutes during market hours, only if TSLA passed Module A trend check.
        """
        if TSLA_TICKER not in self.approved_tickers:
            logging.info(f"Module D disabled: {TSLA_TICKER} failed Module A trend check.")
            return

        tsla_contract = next((c for c in self.contracts if c.symbol == TSLA_TICKER), None)
        if not tsla_contract: return

        # Module D execution is now optimized to request minimal data (3 days)
        signal = module_D_execution.run_tsla_min5_analysis(self.ib, tsla_contract)
        
        if signal:
            # Add/Overwrite signal dict for Module C execution
            self.pending_signals[TSLA_TICKER] = signal
            logging.warning(f"Module D signal added: {TSLA_TICKER}. Total pending: {list(self.pending_signals.keys())}")
            
    
    def run_execution_monitor(self):
        """
        Task C: The system heartbeat. Manages orders and positions (Internal Stop Loss check).
        Runs every 60 seconds (Non-blocking).
        """
        logging.debug("--- RUNNING EXECUTION MONITOR (Module C) ---")

        # 1. Check for mandatory liquidation
        module_C_execution.check_for_mandatory_liquidation(self.ib)

        # 2. Execute orders and monitor positions/stops
        # The function returns tickers that were successfully placed/filled
        successfully_handled_tickers = module_C_execution.manage_limit_order_lifecycle(
            self.ib, 
            self.contracts, 
            self.pending_signals
        )
        
        # 3. Clean up executed signals
        for ticker in successfully_handled_tickers:
            if ticker in self.pending_signals:
                del self.pending_signals[ticker]
        
        logging.debug(f"Pending signals after execution: {list(self.pending_signals.keys())}")


def main():
    setup_logging()
    logging.info("--- QUANTTY SYSTEM STARTUP (Event-Driven) ---")

    ib = IB()

    try:
        logging.info(f"Attempting connection to {IB_HOST}:{IB_PORT} with Client ID {IB_CLIENT_ID}...")
        util.logToConsole(logging.INFO) # Use ib_insync log to console
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        logging.info("IB Connection established.")

        daemon = QuantDaemon(ib)
        daemon.start()

    except Exception as e:
        logging.critical(f"UNRECOVERABLE SYSTEM ERROR: {e}", exc_info=True)
    finally:
        if ib.isConnected():
            ib.disconnect()
            logging.info("System shut down cleanly.")
        else:
            logging.warning("Connection lost or never established.")

if __name__ == "__main__":
    main()

