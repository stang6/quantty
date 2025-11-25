# ============================================
# main.py — FINAL VERSION for ib_insync 0.9.86 (NO timer, NO schedule)
# ============================================

import os
import sys
import logging
import time
import threading
from typing import List, Dict
import pandas as pd
from datetime import datetime

from config.parameters import IB_HOST, IB_PORT, IB_CLIENT_ID, TSLA_TICKER
from utils.system_logging import setup_logging

from ib_insync import IB, util

from core_logic.module_A_filter import check_long_term_filter
from core_logic import module_B_signals
from core_logic import module_C_execution
from core_logic import module_D_execution
from data.historical_data import create_stock_contract, load_tickers_from_file


DATA_DIR = "historical_data"


# -------------------------------------------------
# CSV UTILITIES
# -------------------------------------------------
def save_historical_data_to_csv(df, ticker):
    if df.empty:
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    path = f"{DATA_DIR}/{ticker}_1day.csv"
    df.to_csv(path, index=True)
    logging.info(f"Saved: {path}")


def load_historical_data_from_csv(ticker):
    path = f"{DATA_DIR}/{ticker}_1day.csv"
    if not os.path.exists(path):
        logging.warning(f"{ticker}: missing CSV")
        return pd.DataFrame()

    try:
        df = pd.read_csv(path, index_col="date", parse_dates=True)
    except:
        logging.error(f"{ticker}: CSV corrupted, deleting")
        try:
            os.remove(path)
        except:
            pass
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    cols = ["open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in cols):
        return pd.DataFrame()

    df = df[cols]
    df.drop_duplicates(inplace=True)
    return df


# ===================================================
# MAIN DAEMON
# ===================================================
class QuantDaemon:

    def __init__(self, ib: IB):
        self.ib = ib
        self.tickers = load_tickers_from_file()
        self.contracts = [create_stock_contract(t) for t in self.tickers]

        self.approved_tickers = []
        self.pending_signals = {}

        logging.info("QuantDaemon initialized")

    # ----------------------------------------------------
    # THREAD-BASED HEARTBEAT (NO TIMER / NO SCHEDULE)
    # ----------------------------------------------------
    def start_heartbeat_thread(self):
        thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        thread.start()
        logging.info("Heartbeat thread started")

    def _heartbeat_loop(self):
        last_daily = None
        last_exec = 0
        last_tsla = 0

        while True:
            now = datetime.now()

            # Daily job at 05:00
            if now.hour == 5 and now.minute == 0:
                if last_daily != now.date():
                    self.run_daily_analysis()
                    last_daily = now.date()

            # Execution heartbeat every 60 sec
            if time.time() - last_exec >= 60:
                self.run_execution_monitor()
                last_exec = time.time()

            # TSLA 5-min check
            if time.time() - last_tsla >= 300:
                self.run_min5_analysis()
                last_tsla = time.time()

            time.sleep(1)

    # ----------------------------------------------------
    def start(self):
        logging.info("Subscribing live data...")
        for c in self.contracts:
            try:
                self.ib.reqMktData(c, "", snapshot=False, regulatorySnapshot=False)
            except Exception as e:
                logging.error(f"Failed subscribe {c.symbol}: {e}")

        logging.info("Running initial daily analysis...")
        self.run_daily_analysis()

        # Start heartbeat thread
        self.start_heartbeat_thread()

    # ----------------------------------------------------
    # DAILY ANALYSIS
    # ----------------------------------------------------
    def run_daily_analysis(self):
        logging.warning("--- DAILY ANALYSIS ---")
        self.approved_tickers = []
        today = datetime.now().date()

        for contract in self.contracts:
            ticker = contract.symbol
            df = load_historical_data_from_csv(ticker)

            need_dl = False
            if df.empty:
                duration = "2 Y"
                need_dl = True
            else:
                last_day = df.index.max().date()
                if last_day < today:
                    duration = "2 D"
                    need_dl = True
                else:
                    duration = None

            if need_dl:
                bars = self.ib.reqHistoricalData(
                    contract, "", duration, "1 day", "TRADES", True, 1
                )
                if not bars:
                    continue

                newdf = util.df(bars).set_index("date")
                newdf.index = pd.to_datetime(newdf.index)
                newdf = newdf[["open", "high", "low", "close", "volume"]]

                if not df.empty:
                    df = pd.concat([df, newdf[newdf.index > df.index.max()]])
                else:
                    df = newdf

                df.drop_duplicates(inplace=True)
                save_historical_data_to_csv(df, ticker)

            if len(df) < 200:
                continue

            if check_long_term_filter(df):
                self.approved_tickers.append(ticker)
                sig = module_B_signals.generate_signals(ticker, df, True)
                if sig:
                    self.pending_signals[ticker] = sig

        logging.warning(f"Daily Done: approved={self.approved_tickers}, pending={list(self.pending_signals)}")

    # ----------------------------------------------------
    # MODULE D
    # ----------------------------------------------------
    def run_min5_analysis(self):
        if TSLA_TICKER not in self.approved_tickers:
            return
        contract = next((c for c in self.contracts if c.symbol == TSLA_TICKER), None)
        if not contract:
            return

        sig = module_D_execution.run_tsla_min5_analysis(self.ib, contract)
        if sig:
            self.pending_signals[TSLA_TICKER] = sig

    # ----------------------------------------------------
    # MODULE C
    # ----------------------------------------------------
    def run_execution_monitor(self):
        module_C_execution.check_for_mandatory_liquidation(self.ib)

        finished = module_C_execution.manage_limit_order_lifecycle(
            self.ib, self.contracts, self.pending_signals
        )
        for ticker in finished:
            self.pending_signals.pop(ticker, None)


# ===================================================
# MAIN
# ===================================================
def main():
    setup_logging()
    logging.info("--- QUANTTY STARTUP ---")

    ib = IB()

    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)

        daemon = QuantDaemon(ib)
        daemon.start()

        logging.info("Starting IB event loop...")
        ib.run()

    except KeyboardInterrupt:
        logging.info("Ctrl+C received, shutting down")
    except Exception as e:
        logging.critical(f"FATAL ERROR: {e}", exc_info=True)
    finally:
        if ib.isConnected():
            ib.disconnect()
        logging.info("Shutdown complete")


if __name__ == "__main__":
    main()

