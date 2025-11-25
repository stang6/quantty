# ============================================
# main.py — FINAL VERSION for ib_insync 0.9.86
# Thread heartbeat + Dashboard + Full System
# ============================================

import os
import logging
import time
import threading
from datetime import datetime
import pandas as pd

from ib_insync import IB, util

# === CONFIG ===
from config.parameters import IB_HOST, IB_PORT, IB_CLIENT_ID, TSLA_TICKER
from utils.system_logging import setup_logging

# === CORE LOGIC ===
from core_logic.module_A_filter import check_long_term_filter
from core_logic import module_B_signals
from core_logic import module_C_execution
from core_logic import module_D_execution
from core_logic import module_E_dashboard

# === DATA HELPERS ===
from data.historical_data import create_stock_contract, load_tickers_from_file


DATA_DIR = "historical_data"


# ============================================
# CSV UTILITIES
# ============================================
def save_historical_data_to_csv(df, ticker):
    if df.empty:
        logging.warning(f"{ticker}: Attempted to save empty DataFrame.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    path = f"{DATA_DIR}/{ticker}_1day.csv"

    try:
        df.to_csv(path, index=True)
    except Exception as e:
        logging.error(f"Failed saving CSV for {ticker}: {e}")
        return

    logging.info(f"Saved: {path}")


def load_historical_data_from_csv(ticker):
    path = f"{DATA_DIR}/{ticker}_1day.csv"

    if not os.path.exists(path):
        logging.warning(f"{ticker}: missing CSV")
        return pd.DataFrame()

    try:
        df = pd.read_csv(path, index_col="date", parse_dates=True)
    except Exception:
        logging.error(f"{ticker}: corrupted CSV -> removed")
        try:
            os.remove(path)
        except:
            pass
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    cols = ["open", "high", "low", "close", "volume"]
    for c in cols:
        if c not in df.columns:
            return pd.DataFrame()

    df = df[cols]
    df.drop_duplicates(inplace=True)
    return df


# ============================================
# MAIN DAEMON
# ============================================
class QuantDaemon:

    def __init__(self, ib: IB):
        self.ib = ib

        self.tickers = load_tickers_from_file()
        self.contracts = [create_stock_contract(t) for t in self.tickers]

        self.approved_tickers = []
        self.pending_signals = {}

        logging.info("QuantDaemon initialized.")

        # Dashboard shared state
        module_E_dashboard.shared_state["health"]["status"] = "OK"
        module_E_dashboard.shared_state["health"]["heartbeat"] = 0

    # ============================================
    # HEARTBEAT THREAD
    # ============================================
    def start_heartbeat_thread(self):
        t = threading.Thread(target=self._heartbeat_loop, daemon=True)
        t.start()
        logging.info("Heartbeat thread started.")

    def _heartbeat_loop(self):
        last_daily = None
        last_exec = 0
        last_tsla = 0

        while True:
            # Update dashboard heartbeat
            module_E_dashboard.shared_state["health"]["heartbeat"] += 1

            now = datetime.now()

            # TIME-BASED SCHEDULING
            if now.hour == 5 and now.minute == 0:
                if last_daily != now.date():
                    logging.info("Daily scheduled run triggered.")
                    self.run_daily_analysis()
                    last_daily = now.date()

            # Execution Monitor every 60s
            if time.time() - last_exec >= 60:
                self.run_execution_monitor()
                last_exec = time.time()

            # TSLA 5-min
            if time.time() - last_tsla >= 300:
                self.run_min5_analysis()
                last_tsla = time.time()

            time.sleep(1)

    # ============================================
    def start(self):
        logging.info("Subscribing live market data...")

        for c in self.contracts:
            try:
                self.ib.reqMktData(c, '', snapshot=False, regulatorySnapshot=False)
            except Exception as e:
                logging.error(f"Subscribe failed for {c.symbol}: {e}")

        logging.info("Running FIRST Daily Analysis...")
        self.run_daily_analysis()

        # start dashboard
        module_E_dashboard.start_dashboard()

        # start heartbeat
        self.start_heartbeat_thread()

    # ============================================
    # DAILY ANALYSIS
    # ============================================
    def run_daily_analysis(self):
        logging.warning("--- DAILY ANALYSIS ---")

        self.approved_tickers = []
        today = datetime.now().date()

        for c in self.contracts:
            ticker = c.symbol
            df = load_historical_data_from_csv(ticker)

            download_needed = False

            if df.empty:
                duration = "2 Y"
                download_needed = True
            else:
                last_day = df.index.max().date()
                if last_day < today:
                    duration = "2 D"
                    download_needed = True
                else:
                    duration = None

            if download_needed:
                bars = self.ib.reqHistoricalData(
                    c, "", duration, "1 day",
                    "TRADES", True, 1
                )
                if bars:
                    new = util.df(bars).set_index("date")
                    new.index = pd.to_datetime(new.index)
                    new = new[["open", "high", "low", "close", "volume"]]

                    if not df.empty:
                        df = pd.concat([df, new[new.index > df.index.max()]])
                    else:
                        df = new

                    df.drop_duplicates(inplace=True)
                    save_historical_data_to_csv(df, ticker)
                else:
                    logging.error(f"No bars for {ticker}")
                    continue

            if len(df) < 200:
                continue

            if check_long_term_filter(df):
                self.approved_tickers.append(ticker)

                sig = module_B_signals.generate_signals(ticker, df, True)

                if sig:
                    self.pending_signals[ticker] = sig

        logging.warning(f"Daily Done: Approved={self.approved_tickers}, Pending={list(self.pending_signals)}")

    # ============================================
    # MODULE D — SHORT TERM Trading
    # ============================================
    def run_min5_analysis(self):
        for c in self.contracts:
            symbol = c.symbol

            if symbol not in self.approved_tickers:
                continue

            sig = module_D_execution.run_short_term_strategy(self.ib,c,strategy_name="RSI")
            if sig:
                self.pending_signals[symbol] = sig
                logging.info(f"[Module D] Short-term signal: {sig}")

    # ============================================
    # MODULE C — ORDER EXECUTION MONITOR
    # ============================================
    def run_execution_monitor(self):
        module_C_execution.check_for_mandatory_liquidation(self.ib)

        done = module_C_execution.manage_limit_order_lifecycle(
            self.ib, self.contracts, self.pending_signals)

        for t in done:
            self.pending_signals.pop(t, None)

        self.update_dashboard()


    # ----------------------------------------------------
    # DASHBOARD UPDATER
    # ----------------------------------------------------
    def update_dashboard(self):
        # --- Open Orders ---
        orders = self.ib.openOrders()
        module_E_dashboard.shared_state["orders"] = [
            {
                "id": o.orderId,
                "ticker": o.contract.symbol,
                "action": o.order.action,
                "qty": o.order.totalQuantity,
                "type": o.order.orderType,
                "limit": o.order.lmtPrice,
                "status": self.ib.reqAllOpenOrders().get(o.orderId, "Unknown")
            }
            for o in orders
        ]

        # --- Positions ---
        pos = self.ib.positions()
        module_E_dashboard.shared_state["positions"] = [
            {
                "ticker": p.contract.symbol,
                "qty": p.position,
                "avg_cost": p.avgCost
            }
            for p in pos
        ]

        # --- Fills ---
        fills = self.ib.fills()
        module_E_dashboard.shared_state["fills"] = [
            {
                "ticker": f.contract.symbol,
                "price": f.price,
                "qty": f.execution.shares,
                "time": f.time.strftime("%Y-%m-%d %H:%M:%S")
            }
            for f in fills
        ]

        # --- Pending Signals ---
        module_E_dashboard.shared_state["signals"] = [
            {"ticker": k, "signal": v} for k, v in self.pending_signals.items()
        ]



# ============================================
# MAIN
# ============================================
def main():
    setup_logging()
    logging.info("--- QUANTTY STARTUP ---")

    ib = IB()

    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        logging.info("Connected to IB.")

        daemon = QuantDaemon(ib)
        daemon.start()
        logging.info("Starting IB event loop…")
        ib.run()

    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received.")
    except Exception as e:
        logging.critical(f"FATAL ERROR: {e}", exc_info=True)
    finally:
        if ib.isConnected():
            ib.disconnect()
        logging.info("System Terminated.")


if __name__ == "__main__":
    main()

