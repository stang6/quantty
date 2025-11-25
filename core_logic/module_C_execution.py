
# ============================================
# core_logic/module_C_execution.py (Module C FINAL STABLE SKELETON)
# ============================================
import numpy as np
import datetime
import time
import logging
from typing import List

# --- Import IB related functions ---
from ib_insync import IB, Contract, MarketOrder, LimitOrder, Stock, util

# --- Import system parameters ---
# NOTE: Removed explicit import of 'ARC_CAPITAL' etc. and used 'config.parameters.*' for simplicity
from config.parameters import *
from config.market_holidays import load_us_market_holidays

# --- Constant initialization ---
US_HOLIDAYS = load_us_market_holidays()

# Placeholder for future persistent state (e.g., active orders, position details)
GLOBAL_TRADE_STATE = {}

def calculate_position_size(entry_price: float, stop_loss_price: float, available_funds: float = ARC_CAPITAL) -> int:
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

def is_liquidation_mandatory(ib: IB) -> bool:
    """
    Checks if liquidation is mandatory (Friday close or day before market holiday).
    Accepts IB object but is not used yet.
    """
    today = datetime.datetime.now().date()

    # 1. Check for Friday close (Friday is 4)
    if today.weekday() == 4:
        logging.info("Liquidation check: Friday detected.")
        return True

    # 2. Check for upcoming major holiday
    for i in range(1, 4): # Check up to 3 days ahead to cover weekends
        next_day = today + datetime.timedelta(days=i)

        if next_day in US_HOLIDAYS:
            logging.info(f"Liquidation check: Holiday {next_day} detected soon.")
            return True

        if next_day.weekday() in [5, 6]: # Saturday (5) or Sunday (6)
            break

    return False

# NOTE: The main.py will now call the function by its new name: check_for_mandatory_liquidation(ib)
# We need to ensure that the main.py calling function is renamed if we want to use the cleaner 'is_liquidation_mandatory'.
# For now, to match the main.py call, let's rename the function below to match the call in main.py.

# For stability, we keep the original name check_for_mandatory_liquidation
# but implement the logic from the cleaner is_liquidation_mandatory (which we just wrote).
def check_for_mandatory_liquidation(ib: IB) -> bool:
    """
    Checks for conditions requiring immediate forced liquidation.
    NOTE: This is the function called in main.py. It wraps the logic of is_liquidation_mandatory.
    """
    return is_liquidation_mandatory(ib)


def execute_liquidation(ib: IB, open_positions: List[Contract]) -> bool:
    """Sells all open positions if mandatory liquidation is required."""

    # Use the function that matches the main.py call for now
    if check_for_mandatory_liquidation(ib):
        logging.warning("MANDATORY LIQUIDATION TRIGGERED: Selling all open positions (Simulated).")
        # Actual IB execution logic goes here later: ib.placeOrder(contract, MarketOrder('SELL', ...))
        return True
    return False

def check_total_drawdown(current_pnl: float, initial_capital: float = ARC_CAPITAL) -> bool:
    """Checks if the 15% Max Total Drawdown has been breached."""
    current_value = initial_capital + current_pnl
    drawdown_pct = (initial_capital - current_value) / initial_capital
    if drawdown_pct >= MAX_TOTAL_DRAWDOWN_PCT:
        return True
    return False

def check_trailing_stop(current_price: float, highest_price_reached: float, latest_atr: float) -> bool:
    """Checks the ATR-based trailing stop condition."""

    trailing_distance = latest_atr * ATR_MULTIPLIER
    trailing_stop_price = highest_price_reached - trailing_distance

    if current_price <= trailing_stop_price:
        logging.info(f"TRAILING STOP HIT: Current price {current_price} less than or equal to floor {trailing_stop_price}.")
        return True # Trigger immediate MKT Sell Order

    return False

# NOTE: The original version of this function only took a single ticker/shares/price.
# The main.py loop requires a function that manages the *entire* lifecycle,
# not just a single order attempt. We must redefine this function structure
# to match the call in main.py: `manage_limit_order_lifecycle(ib, contracts_to_monitor)`

def manage_limit_order_lifecycle(ib: IB, contracts_to_monitor: List[Contract]) -> None:
    """
    Module C: The core continuous function for managing trade execution.
    It handles placing new limit orders, checking existing order status,
    and updating trailing stop orders.

    :param ib: The connected IB instance.
    :param contracts_to_monitor: The list of Contract objects requested for market data.
    """
    # 1. Check for new BUY signals in GLOBAL_TRADE_STATE (FUTURE STEP)
    # 2. Check status of existing orders (FUTURE STEP)
    # 3. Update stop loss / take profit orders (FUTURE STEP)

    # For now, just ensure the log message prints to confirm stability.
    logging.debug("Module C: Running continuous order and position management check.")
    pass
