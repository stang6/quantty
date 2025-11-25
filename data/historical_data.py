# ============================================
# data/historical_data.py (ib_insync 最終版本)
# ============================================
import pandas as pd
import logging
from ib_insync import IB, Contract, Stock, util

def create_stock_contract(ticker: str) -> Contract:
    """Helper function to create a standard US Stock Contract object."""
    # ib_insync 簡化了合約創建
    return Stock(ticker, 'SMART', 'USD')

def request_historical_data_ibinsync(ib: IB, ticker: str, duration_str: str = "730 D") -> pd.DataFrame:
    """
    Requests historical daily bar data via ib_insync。
    
    :param ib: The connected IB instance.
    :param ticker: Stock ticker (e.g., 'TSLA').
    :param duration_str: Data time length (e.g., '730 D' for 2 years of Daily bars).
    :return: DataFrame containing historical price data.
    """
    logging.info(f"Requesting historical data for {ticker}...")

    contract = create_stock_contract(ticker)
    
    # 這是 ib_insync 的同步請求 (會自動等待數據返回)
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
    
    # 將 Bars 轉換為 DataFrame
    data_df = util.df(bars)
    
    # 清理和格式化
    data_df.set_index('date', inplace=True)
    data_df.index = pd.to_datetime(data_df.index)
    data_df = data_df[['open', 'high', 'low', 'close', 'volume']] # 確保列名一致
    
    logging.info(f"Successfully retrieved {len(data_df)} bars for {ticker}.")
    return data_df
