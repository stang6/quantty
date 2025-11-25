# ============================================
# main.py 
# ============================================

import os
import sys
import logging
import time
from datetime import datetime, timedelta

# Data directory
DATA_DIR = 'historical_data'

# configs from config.parameters
from config.parameters import IB_HOST, IB_PORT, IB_CLIENT_ID
from utils.system_logging import setup_logging
from ib_insync import IB, util, Contract, Stock

# core logic modules
from core_logic.module_A_filter import check_long_term_filter
from core_logic.module_B_signals import calculate_indicators, generate_buy_signal 
from core_logic.module_C_execution import manage_limit_order_lifecycle, check_for_mandatory_liquidation
from data.historical_data import request_historical_data_ibinsync, load_tickers_from_file # Added load_tickers_from_file

def run_trading_system(ib: IB):

    # 1. Hold and sync for the initialization
    ib.waitOnUpdate(timeout=5)

    # 2. Get account info (Simplified for display)
    account_summary = ib.accountSummary()
    if account_summary:
        account_id = account_summary[0].account
        currency = account_summary[0].currency
        logging.info(f"Connection successful! Account: {account_id}, Currency: {currency}")
    else:
        logging.warning("Connected, but failed to retrieve account summary data.")

    # 3. Load to-trade list (Scalable Fix)
    TICKERS_TO_TRADE = load_tickers_from_file()
    if not TICKERS_TO_TRADE:
        logging.critical("No tickers found in tickers.txt. Shutting down system.")
        return # Shut down if no tickers are loaded

    logging.info(f"Loaded {len(TICKERS_TO_TRADE)} tickers for analysis: {TICKERS_TO_TRADE}")

    # 4. Get data and run strategy
    logging.info("Starting historical data requests for Module A/B analysis (2 years of daily bars)...")

    # This list will store contracts that generate buy signals
    potential_signals = [] 
    
    # List to hold all Contract objects for live monitoring
    contracts_to_monitor = []

    for ticker in TICKERS_TO_TRADE:
        # Define contract object and add to the monitor list
        contract = Stock(ticker, 'SMART', 'USD')
        contracts_to_monitor.append(contract)

        data_df = request_historical_data_ibinsync(ib, ticker, duration_str="2 Y")

        if data_df.empty:
            logging.error(f"Data retrieval failed or returned empty for {ticker}. Skipping.")
            continue
        
        # Data saving logic (FIX: Re-enable and ensure correct path)
        file_path = os.path.join(DATA_DIR, f"{ticker}_1day.csv")
        try:
            data_df.to_csv(file_path, index=True) 
            # In code comments, use English only; no Chinese.
            logging.info(f"Historical data successfully saved to {file_path}") # Removed small symbols from print statements in code.
        except Exception as e:
            logging.error(f"Failed to save data for {ticker} to {file_path}: {e}")
        # ----------------------------------------------------------------------

        # 4. Execute Module A (Trend filter)
        is_trend_up = check_long_term_filter(data_df)

        if is_trend_up:
            logging.info(f"Module A PASS: {ticker} meets long-term trend criteria.")

            # 5. Execute Module B (Signal calculation and generation)
            data_df = calculate_indicators(data_df)

            if generate_buy_signal(data_df, is_trend_up):
                # We append the ticker for now, but in Module C we'll use the Contract object
                potential_signals.append(ticker) 
                logging.warning(f"Module B SIGNAL: BUY signal generated for {ticker}.")
            else:
                logging.info(f"Module B NO SIGNAL: {ticker} passed trend but no buy signal detected.")
        else:
            logging.info(f"Module A FAIL: {ticker} does not meet trend criteria.")

    logging.info(f"Module A/B Analysis Complete. Found {len(potential_signals)} trade signals: {potential_signals}")

    # --- Module C: Initial Execution Logic ---
    if potential_signals:
        logging.warning(f"Strategy signals detected for: {potential_signals}. Preparing for order execution.")
        pass 
    # -----------------------------------------


    # 6. Real-time trading / Monitoring loop (Module C - Continuous Management)
    logging.info("System running. Entering real-time monitoring loop.")

    # 2. Request Market Data (FIX for TypeError: iterate over the list)
    if contracts_to_monitor:
        for contract in contracts_to_monitor:
            # Request live data one by one to avoid the 'multiple values' TypeError
            # This is the correct way to request multiple market data streams in ib_insync loops
            ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)
        logging.info(f"Requesting live market data for {len(contracts_to_monitor)} contracts: {TICKERS_TO_TRADE}")

    while ib.isConnected():
        
        # 1. Check for mandatory liquidation (Weekends/Holidays)
        check_for_mandatory_liquidation(ib) 

        # 2. Continuous Order and Position Management (Module C Core)
        if contracts_to_monitor:
            # This function handles placing new orders, checking order status, and updating stop losses.
            manage_limit_order_lifecycle(ib, contracts_to_monitor) 
            logging.debug("Module C: Running continuous order and position management check.")
        
        # 3. System heartbeat and wait
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
