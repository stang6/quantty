
# ============================================
# main.py (ib_insync version) - 最終修正版
# ============================================

import os
import sys
import logging
import time
from datetime import datetime, timedelta

# data to store
DATA_DIR = 'historical_data'

# configs from config.parameters
from config.parameters import IB_HOST, IB_PORT, IB_CLIENT_ID
from utils.system_logging import setup_logging
from ib_insync import IB, util

# core logic modules
from core_logic.module_A_filter import check_long_term_filter
from core_logic.module_B_signals import calculate_indicators, generate_buy_signal # 修正導入: 使用 generate_buy_signal
from core_logic.module_C_execution import manage_limit_order_lifecycle, check_for_mandatory_liquidation
from data.historical_data import request_historical_data_ibinsync


def run_trading_system(ib: IB):

    # 1. hold and sync for the initialization
    ib.waitOnUpdate(timeout=5)

    # 2. get account info
    account_summary = ib.accountSummary()

    if account_summary:
        account_id = account_summary[0].account
        currency = account_summary[0].currency
        logging.info(f"✅ Connection successful! Account: {account_id}, Currency: {currency}")
    else:
        logging.warning("⚠️ Connected, but failed to retrieve account summary data. Check TWS/Gateway logs.")

    # 3. to-trade list
    TICKERS_TO_TRADE = ['TSLA', 'NVDA'] # 假設 BAR_SIZE_SETTING = '1 day'

    # 4. get data and run strategy
    logging.info("Starting historical data requests for Module A/B analysis (2 years of daily bars)...")

    potential_signals = []

    for ticker in TICKERS_TO_TRADE:
        data_df = request_historical_data_ibinsync(ib, ticker, duration_str="2 Y") # 確保使用 "2 Y"

        if data_df.empty:
            logging.error(f"Data retrieval failed or returned empty for {ticker}. Skipping.")
            continue

        logging.info(f"Successfully retrieved {len(data_df)} bars for {ticker}.")

        # VVVV--- 數據儲存邏輯 ---VVVV
        try:
            # 1. 檢查並創建儲存目錄
            # 不需要 global DATA_DIR，因為 DATA_DIR 已經在模組級別定義
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
                logging.info(f"Created data directory: {DATA_DIR}")

            # 2. 定義檔案名稱 (假設 BAR_SIZE_SETTING 是 '1 day')
            file_name = f"{ticker}_1day.csv"
            save_path = os.path.join(DATA_DIR, file_name)

            # 3. 儲存 DataFrame 到 CSV 檔案
            data_df.to_csv(save_path)
            logging.info(f"💾 Historical data saved to {save_path}")

        except Exception as e:
            logging.error(f"Error saving historical data for {ticker}: {e}")
        # ^^^^--- 數據儲存邏輯結束 ---^^^^

        # 4. 執行 Module A (趨勢過濾)
        is_trend_up = check_long_term_filter(data_df)

        if is_trend_up:
            logging.info(f"Module A PASS: {ticker} meets long-term trend criteria.")

            # 5. 執行 Module B (訊號計算與生成)
            data_df = calculate_indicators(data_df)

            # 假設 generate_buy_signal 存在
            if generate_buy_signal(data_df, is_trend_up): # 使用正確的函式名稱
                # ... (訊號處理邏輯，例如加入 potential_signals) ...
                potential_signals.append(ticker)
                logging.warning(f"Module B SIGNAL: BUY signal generated for {ticker}.")
            else:
                logging.info(f"Module B NO SIGNAL: {ticker} passed trend but no buy signal detected.")
        else:
            logging.info(f"Module A FAIL: {ticker} does not meet trend criteria.")

    logging.info(f"Module A/B Analysis Complete. Found {len(potential_signals)} trade signals: {potential_signals}")


    # 5. 實時交易/監控迴圈
    logging.info("System running. Entering real-time monitoring loop.")

    while ib.isConnected():

        # 檢查是否需要強制平倉 (週末/節假日)
        # if check_for_mandatory_liquidation():
        #    ib.disconnect()
        #    break

        logging.debug("System heart beat: Checking open positions and market status...")
        ib.sleep(60) # 每 60 秒檢查一次

    logging.info("System shut down due to disconnection or logic break.")


def main():
    setup_logging()
    logging.info("--- QUANTTY SYSTEM STARTUP ---")

    ib = IB()

    try:
        logging.info(f"Attempting connection to {IB_HOST}:{IB_PORT} with Client ID {IB_CLIENT_ID}...")

        # ib_insync 連線
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)

        logging.info("IB Connection established.")

        # 啟動主邏輯
        run_trading_system(ib)

    except Exception as e:
        # 捕獲所有異常 (包括連線失敗)
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
