
# ============================================
# main.py (Final version with Module D Parallel Integration)
# ============================================

import os
import sys
import logging
import time
from typing import List, Dict, Tuple
import pandas as pd
from datetime import datetime, timedelta

# Data directory
DATA_DIR = 'historical_data'

# configs from config.parameters
from config.parameters import IB_HOST, IB_PORT, IB_CLIENT_ID, TSLA_TICKER
from utils.system_logging import setup_logging
from ib_insync import IB, util, Contract, Stock

# core logic modules
from core_logic.module_A_filter import check_long_term_filter
from core_logic.module_B_signals import calculate_indicators, generate_buy_signal
from core_logic.module_C_execution import manage_limit_order_lifecycle, check_for_mandatory_liquidation
from core_logic import module_D_execution # NEW: Import Module D
from data.historical_data import request_historical_data_ibinsync, load_tickers_from_file

def save_historical_data_to_csv(data_df: pd.DataFrame, ticker: str):
    # Saves the historical DataFrame to a CSV file in the designated directory.
    import pandas as pd
    if data_df.empty:
        logging.warning(f"Attempted to save empty DataFrame for {ticker}. Skipping save.")
        return

    HISTORICAL_DATA_DIR = DATA_DIR
    os.makedirs(HISTORICAL_DATA_DIR, exist_ok=True)
    file_path = os.path.join(HISTORICAL_DATA_DIR, f"{ticker}_1day.csv")

    try:
        data_df.to_csv(file_path, index=True)
        logging.info(f"Historical data successfully saved to {file_path}")
    except Exception as e:
        logging.error(f"Failed to save data for {ticker} to {file_path}: {e}")

# NEW FUNCTION: Handles the Module A/B analysis (Daily Bars)
def run_module_ab_analysis(ib: IB, contracts_to_monitor: List[Contract]) -> Tuple[List[str], List[str]]:
    """
    Runs Module A (Stage 2 trend filter) and Module B (Long-term signal).
    Returns: (long_term_signals, approved_tickers)
    """
    long_term_signals: List[str] = []
    approved_tickers: List[str] = [] # Tickers that passed Module A (Stage 2)

    logging.info("Starting historical data requests for Module A/B analysis (2 years of daily bars)...")

    for contract in contracts_to_monitor:
        ticker = contract.symbol

        # NOTE: Fetching 2 years / 1 day bar size
        data_df = request_historical_data_ibinsync(ib, ticker, duration_str="2 Y")

        if data_df.empty:
            logging.error(f"Data retrieval failed or returned empty for {ticker}. Skipping.")
            continue

        save_historical_data_to_csv(data_df, ticker)

        # 1. Execute Module A (Trend filter - Stage 2 Check)
        is_trend_up = check_long_term_filter(data_df)

        if is_trend_up:
            # Module A PASS: Ticker is Stage 2 Approved
            approved_tickers.append(ticker)
            logging.info(f"Module A PASS: {ticker} meets long-term trend criteria.")

            # 2. Execute Module B (Signal calculation and generation)
            data_df = calculate_indicators(data_df)

            if generate_buy_signal(data_df, is_trend_up):
                long_term_signals.append(ticker)
                logging.warning(f"Module B SIGNAL: BUY signal generated for {ticker}.")
            else:
                logging.info(f"Module B NO SIGNAL: {ticker} passed trend but no buy signal detected.")
        else:
            logging.info(f"Module A FAIL: {ticker} does not meet trend criteria.")

    logging.info(f"Module A/B Analysis Complete. Found {len(long_term_signals)} long-term signals.")
    return long_term_signals, approved_tickers

def run_trading_system(ib: IB):
    # 1. Initialization and Account Info
    ib.waitOnUpdate(timeout=5)
    account_summary = ib.accountSummary()
    if account_summary:
        account_id = account_summary[0].account
        currency = account_summary[0].currency
        logging.info(f"Connection successful! Account: {account_id}, Currency: {currency}")
    else:
        logging.warning("Connected, but failed to retrieve account summary data.")

    # 2. Load Contracts
    TICKERS_TO_TRADE = load_tickers_from_file()
    if not TICKERS_TO_TRADE:
        logging.critical("No tickers found in tickers.txt. Shutting down system.")
        return

    logging.info(f"Loaded {len(TICKERS_TO_TRADE)} tickers for analysis: {TICKERS_TO_TRADE}")
    contracts_to_monitor = [Stock(t, 'SMART', 'USD') for t in TICKERS_TO_TRADE]

    # --- INITIAL SETUP: RUN MODULE A/B ONCE ---
    # Run the full analysis once to get the initial signals and the 'approved' list
    long_term_signals, approved_tickers = run_module_ab_analysis(ib, contracts_to_monitor)

    # 3. Real-time trading / Monitoring loop (Module C - Continuous Management)
    logging.info("System running. Entering real-time monitoring loop.")

    # Request Live Data for all contracts
    if contracts_to_monitor:
        for contract in contracts_to_monitor:
            ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)
        logging.info(f"Requesting live market data for {len(contracts_to_monitor)} contracts.")

    while ib.isConnected():
        # 1. Check for mandatory liquidation (Weekends/Holidays)
        check_for_mandatory_liquidation(ib)

        # 2. Re-run Module A/B to refresh long-term signals and trend status (for continuous management)
        long_term_signals, approved_tickers = run_module_ab_analysis(ib, contracts_to_monitor)


        # 3. Module D (TSLA 5-min analysis - NEW INTEGRATION)
        tsla_contract = next((c for c in contracts_to_monitor if c.symbol == TSLA_TICKER), None)
        short_term_signals_list: List[str] = []

        # --- Stage 2 Risk Control Check ---
        if tsla_contract and TSLA_TICKER in approved_tickers:
            # Only run Module D if TSLA passed Module A (Stage 2) long-term trend check
            short_term_signals_list = module_D_execution.run_tsla_min5_analysis(ib, tsla_contract)

        else:
            if tsla_contract:
                 logging.info(f"Module D disabled for {TSLA_TICKER}: Did NOT pass Module A long-term trend filter (Stage 2).")

        # 4. Consolidate All Signals (Format: {ticker: 'SOURCE'})
        all_signals: Dict[str, str] = {}

        # A. Long-Term Signals
        for ticker in long_term_signals:
            all_signals[ticker] = 'LONG'

        # B. Short-Term Signals (Overwrite if the same ticker is present, but should not happen often)
        for ticker in short_term_signals_list:
            all_signals[ticker] = 'SHORT'

        logging.warning(f"Strategy signals detected ({len(all_signals)} total). Preparing for order execution.")

        # 5. Module C (Execution and Monitoring)
        # Module C now receives a dictionary with the signal type (LONG/SHORT)
        module_C_execution.manage_limit_order_lifecycle(ib, contracts_to_monitor, all_signals)

        # 6. System heartbeat and wait
        logging.debug("System heart beat: Checking open positions and market status.")
        ib.sleep(60) # Check every 60 seconds

    logging.info("System shut down due to disconnection or logic break.")


def main():
    setup_logging()
    logging.info("--- QUANTTY SYSTEM STARTUP ---")

    ib = IB()

    try:
        logging.info(f"Attempting connection to {IB_HOST}:{IB_PORT} with Client ID {IB_CLIENT_ID}...")

        # ib_insync connection
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)

        logging.info("IB Connection established.")

        # Start main logic
        run_trading_system(ib)

    except Exception as e:
        # Capture all exceptions (including connection failures)
        logging.critical(f"UNRECOVERABLE SYSTEM ERROR: {e}", exc_info=True)
    finally:
        if ib.isConnected():
            ib.disconnect()
            logging.info("System shut down cleanly.")
        else:
            logging.warning("Connection lost or never established.")

if __name__ == "__main__":
    util.logToConsole(logging.INFO)
    main()
