# ============================================
# main.py (FINAL REFACTOR: Event-Driven Architecture)
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
from utils.system_logging import setup_logging
from ib_insync import IB, util, Contract, Stock

# core logic modules
from core_logic.module_A_filter import check_long_term_filter
from core_logic import module_B_signals
from core_logic import module_C_execution
from core_logic import module_D_execution
from data.historical_data import create_stock_contract, load_tickers_from_file


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
    """Loads historical data from CSV cache if available. Safe & fault-tolerant."""
    HISTORICAL_DATA_DIR = DATA_DIR
    file_path = os.path.join(HISTORICAL_DATA_DIR, f"{ticker}_1day.csv")

    # --- Case 1: File does not exist ---
    if not os.path.exists(file_path):
        logging.warning(f"{ticker}: Cache file missing. Will download full 2Y history.")
        return pd.DataFrame()

    try:
        # Try reading CSV
        data_df = pd.read_csv(file_path, index_col='date', parse_dates=True)
    except Exception as e:
        logging.error(f"{ticker}: Failed to load CSV ({e}). Deleting corrupted file and re-downloading.")
        try:
            os.remove(file_path)
        except:
            pass
        return pd.DataFrame()

    # --- Case 2: Empty DataFrame or invalid index ---
    if data_df.empty:
        logging.warning(f"{ticker}: CSV exists but is empty. Re-downloading full history.")
        return pd.DataFrame()

    # --- Case 3: Check required columns are present ---
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in data_df.columns for col in expected_cols):
        logging.error(f"{ticker}: CSV missing required OHLCV columns. Re-downloading.")
        return pd.DataFrame()

    # --- Case 4: Check for NaT index (corrupted date) ---
    try:
        last_date = data_df.index.max()
        if pd.isna(last_date):
            logging.error(f"{ticker}: CSV has NaT timestamps. Re-downloading.")
            return pd.DataFrame()
    except Exception as e:
        logging.error(f"{ticker}: CSV index corrupted ({e}). Re-downloading.")
        return pd.DataFrame()

    # --- Case 5: Normal cleanup ---
    # Drop duplicates & ensure column ordering
    data_df = data_df[expected_cols]
    data_df.drop_duplicates(inplace=True)

    logging.info(f"Loaded {len(data_df)} valid bars for {ticker} from local cache.")
    return data_df

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
        
    def _schedule_tasks(self):
        """Define and Schedule ALL Tasks (This is the non-blocking part)."""

        # Task A: Daily Analysis (Module A/B, Cache Update)
        self.ib.schedule(
            time(hour=5, minute=0),
            self.run_daily_analysis
        )

        # Task B: Short-term Analysis (Module D: TSLA 5-min)
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
        logging.info("All periodic tasks scheduled.")


    def start(self):
        """
        Starts the trading system setup: initial subscriptions, initial analysis, and scheduling.
        This method must return to allow the main ib.run() to take over.
        """

        # 1. Subscribe to Live Market Data (Non-blocking)
        self._subscribe_live_market_data()

        # 2. Initialization: Run Module A/B once to get initial data and trend status
        logging.info("CHECKPOINT 1: Starting initial data sync and analysis (BLOCKING)...")
        self.run_daily_analysis()
        logging.info(f"CHECKPOINT 2: Initial analysis finished. Approved: {len(self.approved_tickers)}, Pending Signals: {len(self.pending_signals)}")

        # 3. Define and Schedule Tasks (The actual event loop)
        self._schedule_tasks()
        
        # REMOVED: self.ib.run() -> Moved to main()


    def _subscribe_live_market_data(self):
        """Subscribe to continuous market data for all contracts (for Module C stop check)."""
        logging.info(f"Subscribing to live market data for {len(self.contracts)} contracts...")
        for contract in self.contracts:
            # Snapshot=False ensures a continuous stream, which is stored in ib.tickerOf(contract)
            self.ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)

        # Also subscribe to account updates and open orders for Module C
        self.ib.reqAccountUpdates(True) 
        self.ib.reqAllOpenOrders()

    def run_daily_analysis(self):
        logging.warning("--- RUNNING DAILY ANALYSIS (Module A/B: Check Cache) ---")
        self.approved_tickers = []
        self.long_term_signals = {}
        today = datetime.now().date()
    
        for contract in self.contracts:
            ticker = contract.symbol

            # Safe load with corruption detection
            data_df = load_historical_data_from_csv(ticker)
    
            # Determine if we need to download full or incremental data
            if data_df.empty:
                duration_str = "2 Y"
                logging.info(f"{ticker}: No valid cache found. Downloading full 2Y history.")
            else:
                try:
                    last_day = data_df.index.max().date()
                    if last_day < today:
                        duration_str = "2 D"  # small incremental update
                        logging.info(f"{ticker}: Cache stale ({last_day}). Fetching 2D update.")
                    else:
                        logging.info(f"{ticker}: Cache up-to-date. Skipping download.")
                        # Proceed to signal analysis
                        pass
                except Exception as e:
                    logging.error(f"{ticker}: Cache index corrupted: {e}. Re-downloading full 2Y.")
                    duration_str = "2 Y"
                    data_df = pd.DataFrame()
    
            # --- Download missing or stale data ---
            if data_df.empty or duration_str != "skip":
                bars = self.ib.reqHistoricalData(
                    contract, endDateTime='', durationStr=duration_str, barSizeSetting='1 day',
                    whatToShow='TRADES', useRTH=True, formatDate=1
                )

                if not bars:
                    logging.error(f"{ticker}: Historical data download failed.")
                    continue
    
                logging.info(f"Received {len(bars)} bars for {ticker}.")

                new_df = util.df(bars).set_index('date')
                new_df.index = pd.to_datetime(new_df.index)
                new_df = new_df[['open','high','low','close','volume']]

                if not data_df.empty:
                    data_df = pd.concat([data_df, new_df[new_df.index > data_df.index.max()]])
                else:
                    data_df = new_df

                data_df.drop_duplicates(inplace=True)
                save_historical_data_to_csv(data_df, ticker)

            # --- Module A/B filtering ---
            if len(data_df) < 200:   # need enough bars for SMA/RSI
                logging.warning(f"{ticker}: Not enough data for long-term analysis.")
                continue

            is_trend_up = check_long_term_filter(data_df)
            if is_trend_up:
                self.approved_tickers.append(ticker)
                sig = module_B_signals.generate_signals(ticker, data_df, is_trend_up)
                if sig:
                    self.pending_signals[ticker] = sig

        logging.warning(f"Daily Analysis Complete. Approved: {self.approved_tickers}, Pending: {list(self.pending_signals.keys())}")

    def run_daily_analysis(self):
        """
        Task A: Runs Module A/B (Trend and Long-term signal) using Caching/Incremental Update.
        """
        logging.warning("--- RUNNING DAILY ANALYSIS (Module A/B: Check Cache) ---")
        self.approved_tickers = []
        self.long_term_signals = {} # Clear for fresh run
        today = datetime.now().date()

        for contract in self.contracts:
            ticker = contract.symbol
            data_df = load_historical_data_from_csv(ticker)

            # --- 1. Data Retrieval Logic (Caching + Incremental Update) ---
            if data_df.empty or data_df.index.max().date() < today:

                # If cache is missing OR stale, we request the required data
                duration_str = "2 Y" if data_df.empty else "2 D"

                logging.info(f"Cache {('stale' if not data_df.empty else 'missing')} for {ticker}. Requesting {duration_str} data (BLOCKING).")

                bars = self.ib.reqHistoricalData(
                    contract, endDateTime='', durationStr=duration_str, barSizeSetting='1 day',
                    whatToShow='TRADES', useRTH=True, formatDate=1
                )

                if not bars:
                    logging.error(f"Historical data download failed for {ticker}.")
                    continue
                
                logging.info(f"Received {len(bars)} bars for {ticker}. Processing data.") # <-- NEW CHECKPOINT

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

            if len(data_df) < 500:
                logging.warning(f"Not enough data for {ticker} to run Module A/B analysis.")
                continue

            is_trend_up = check_long_term_filter(data_df)

            if is_trend_up:
                self.approved_tickers.append(ticker)

                signal = module_B_signals.generate_signals(ticker, data_df, is_trend_up)

                if signal:
                    self.pending_signals[ticker] = signal

        logging.warning(f"Daily Analysis Complete. Approved tickers: {self.approved_tickers}. Pending long-term signals: {list(self.pending_signals.keys())}")


    def run_min5_analysis(self):
        """
        Task B: Runs Module D (TSLA 5-min signal).
        """
        if TSLA_TICKER not in self.approved_tickers:
            logging.info(f"Module D disabled: {TSLA_TICKER} failed Module A trend check.")
            return

        tsla_contract = next((c for c in self.contracts if c.symbol == TSLA_TICKER), None)
        if not tsla_contract: return

        signal = module_D_execution.run_tsla_min5_analysis(self.ib, tsla_contract)

        if signal:
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
        # IMPORTANT: Setting log level to DEBUG to see all diagnostics during this final test
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        logging.info("IB Connection established.")

        daemon = QuantDaemon(ib)
        daemon.start() # Runs the setup and initial analysis (BLOCKING section)

        logging.info("Starting IB main event loop (ib.run()).")
        ib.run() # <--- Starts the non-blocking main loop

    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt. Shutting down system.")
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
