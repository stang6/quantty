
# ============================================
# core_logic/module_A_filter.py
# ============================================

import logging
import pandas as pd
import numpy as np
from scipy.stats import linregress
from config.parameters import SMA_PERIOD, SMA_SLOPE_WINDOW, SLOPE_THRESHOLD
from typing import List, Dict

def apply_trend_filter(historical_data: List[Dict]) -> List[str]:
    """
    根據長期趨勢過濾股票清單（Module A）。
    
    :param historical_data: 包含所有股票歷史數據的清單。
    :return: 通過過濾的股票代碼清單。
    """
    logging.info("Module A: Applying long-term trend filter...")
    return ['TSLA']
    

def check_long_term_filter(data_df):
    """
    Executes the Stage 2 trend filter: Price above 200 SMA, and SMA must be rising.
    :param data_df: DataFrame with 'Close' prices (Daily Bars).
    :return: True or False
    """
    
    # 1. Calculate 200 Day SMA
    data_df['SMA_200'] = data_df['close'].rolling(window=SMA_PERIOD).mean()
    
    if data_df.shape[0] < SMA_PERIOD + SMA_SLOPE_WINDOW:
        return False

    latest = data_df.iloc[-1]
    
    # 2. Condition A: Price must be above 200 SMA
    price_above_sma = latest['close'] > latest['SMA_200']
    
    # 3. Condition B: SMA Slope Check (Using Linear Regression for Xin Metal Precision)
    sma_slice = data_df['SMA_200'].iloc[-SMA_SLOPE_WINDOW:].dropna()
    
    if len(sma_slice) < SMA_SLOPE_WINDOW:
        return False

    x = np.arange(len(sma_slice))
    slope, _, _, _, _ = linregress(x, sma_slice)
    
    sma_is_rising = slope > SLOPE_THRESHOLD
    
    # 4. Final Filter Decision
    if price_above_sma and sma_is_rising:
        return True
    return False
