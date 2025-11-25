
# ============================================
# core_logic/module_C_execution.py (ib_insync 最終版本)
# ============================================
import numpy as np
import datetime
import time
import logging

# --- 導入 IB 相關函式 ---
from ib_insync import IB, Contract, MarketOrder, LimitOrder, Stock

# --- 導入系統參數 ---
from config.parameters import *
from config.market_holidays import load_us_market_holidays

# --- 常量初始化 ---
US_HOLIDAYS = load_us_market_holidays()

def calculate_position_size(entry_price, stop_loss_price, available_funds=ARC_CAPITAL):
    """Calculates shares based on MAX_RISK_PER_TRADE ($1500)."""

    risk_per_share = entry_price - stop_loss_price

    if risk_per_share <= 0:
        logging.error(f"Invalid SL: RPS is {risk_per_share}. Check technical SL calculation.")
        return 0

    calculated_shares = MAX_RISK_PER_TRADE / risk_per_share
    required_capital = calculated_shares * entry_price

    if required_capital > available_funds:
        final_shares = np.floor(available_funds / entry_price)
        logging.warning("Scaling down position size due to insufficient funds.")
    else:
        final_shares = np.floor(calculated_shares)

    return int(final_shares)

def check_for_mandatory_liquidation():
    """Checks if liquidation is mandatory (Friday close or day before market holiday)."""
    today = datetime.datetime.now().date()

    # 1. Check for Friday close (Friday is 4)
    if today.weekday() == 4:
        return True

    # 2. Check for upcoming major holiday
    for i in range(1, 4): # Check up to 3 days ahead to cover weekends
        next_day = today + datetime.timedelta(days=i)

        if next_day in US_HOLIDAYS:
            return True

        if next_day.weekday() in [5, 6]: # Saturday (5) or Sunday (6)
            break

    return False

# 修正：參數從 app 改為 ib: IB
def execute_liquidation(ib: IB, open_positions):
    """Sells all open positions if mandatory liquidation is required."""
    if check_for_mandatory_liquidation():
        logging.info("MANDATORY LIQUIDATION TRIGGERED: Selling all open positions.")
        # 在實際的 ib_insync 實作中，您會在這裡執行 ib.placeOrder(contract, MarketOrder('SELL', ...))
        # 為了測試，我們只記錄
        return True
    return False

def check_total_drawdown(current_pnl, initial_capital=ARC_CAPITAL):
    """Checks if the 15% Max Total Drawdown has been breached."""
    current_value = initial_capital + current_pnl
    drawdown_pct = (initial_capital - current_value) / initial_capital
    if drawdown_pct >= MAX_TOTAL_DRAWDOWN_PCT:
        return True
    return False

def check_trailing_stop(current_price, highest_price_reached, latest_atr):
    """Checks the ATR-based trailing stop condition."""

    trailing_distance = latest_atr * ATR_MULTIPLIER
    trailing_stop_price = highest_price_reached - trailing_distance

    if current_price <= trailing_stop_price:
        logging.info(f"TRAILING STOP HIT: Current price {current_price} <= floor {trailing_stop_price}.")
        return True # Trigger immediate MKT Sell Order

    return False

# 修正：參數從 app 改為 ib: IB
def manage_limit_order_lifecycle(ib: IB, ticker: str, shares: int, limit_price: float):
    """
    Handles the execution of a Limit Order, managing the Time-In-Force (TIF) and retry logic.

    This function implements the 'Xin Jin Precision' discipline: LMT order with
    TIF, automatic cancellation if stale, and retrying up to MAX_RETRY_COUNT.

    :param ib: The ib_insync instance. <--- 修正後的參數
    :param ticker: The stock symbol.
    :param shares: The calculated position size.
    :param limit_price: The price to place the limit order at.
    :return: True if the order is filled, False otherwise.
    """

    order_filled = False
    retry_count = 0

    # 建立合約 (ib_insync 的寫法)
    contract = Stock(ticker, 'SMART', 'USD')
    # 確保合約是可交易的
    ib.qualifyContracts(contract)

    while retry_count < MAX_RETRY_COUNT and not order_filled:
        logging.info(f"Attempt {retry_count + 1}/{MAX_RETRY_COUNT}: Placing LMT order for {shares} shares of {ticker} at {limit_price:.2f}.")

        # 這裡的邏輯需要完全重寫為 ib_insync 的同步/異步模式
        # 由於我們只進行啟動測試，這裡使用 Placeholder

        # Placeholder for placing the actual Limit Order with TIF (Time In Force)
        # order = LimitOrder('BUY', shares, limit_price, tif='GTC')
        # trade = ib.placeOrder(contract, order)

        # 為了避免 blocking 導致 daemon 失敗，我們使用 ib.sleep() 模擬等待
        ib.sleep(TIF_SECONDS)

        # Placeholder for checking order status
        status = "PENDING" # 假設狀態為 PENDING

        # 實際邏輯應該是：
        # if trade.orderStatus.status == "Filled":
        #    order_filled = True

        if status == "FILLED":
            order_filled = True
            logging.info(f"LMT Order FILLED successfully.")
            break
        elif status == "PENDING" or status == "SUBMITTED":
            # 取消訂單 (ib_insync 寫法)
            # ib.cancelOrder(trade.order)
            logging.warning("LMT Order cancelled due to TIF expiration (Simulated).")

        # Prepare for retry: Adjust price slightly more aggressive
        limit_price += TICK_ADJUSTMENT
        retry_count += 1

    return order_filled

# --- 額外的風控函式 (保持不變) ---
def check_total_drawdown(current_pnl, initial_capital=ARC_CAPITAL):
    """Checks if the 15% Max Total Drawdown has been breached."""
    current_value = initial_capital + current_pnl
    drawdown_pct = (initial_capital - current_value) / initial_capital
    if drawdown_pct >= MAX_TOTAL_DRAWDOWN_PCT:
        return True
    return False
