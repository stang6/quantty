
# ============================================
# core_logic/module_C_execution.py (REFACTORED for Event-Driven and Internal Stop)
# ============================================

import logging
from ib_insync import IB, Contract, Order, Trade, util, LimitOrder, MarketOrder
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd
import math

# Import parameters
from config.parameters import (
    ARC_CAPITAL,
    LONG_TERM_CAPITAL_RATIO,
    SHORT_TERM_CAPITAL_RATIO,
    MAX_RISK_PER_TRADE_PCT,
    TICK_ADJUSTMENT
)

#from config.market_holidays import load_us_market_holidays
from utils.market_calendar import load_us_market_holidays # New import path

# Global storage for the internal stop level of open positions
# since IBKR does not store this in its position data.
# {ticker: {'entry_price': float, 'internal_stop': float, 'signal_source': str}}
INTERNAL_STOP_TRACKER: Dict[str, Dict] = {}


# --- Helper Functions ---

def get_contract_from_ticker(ib: IB, contracts: List[Contract], ticker: str) -> Optional[Contract]:
    """Retrieves the Contract object from the list."""
    return next((c for c in contracts if c.symbol == ticker), None)

def get_current_price(ib: IB, contract: Contract) -> Optional[float]:
    """
    Retrieves the current market price (last trade) from IB's Ticker cache (Non-blocking).

    FIX: Replaced ib.reqTickers() with the efficient ib.tickerOf()
    """
    ticker = ib.tickerOf(contract)
    # Check if ticker object exists and if the last price is available and not NaN
    if ticker and ticker.last is not None and not math.isnan(ticker.last):
        return ticker.last
    return None

def get_current_position(ib: IB, contract: Contract) -> float:
    """Get the current position size for a contract. Returns 0.0 if no position is found."""
    try:
        # FIX: Directly use ib.positions() to get the actual current position
        positions = ib.positions()

        for pos in positions:
            if pos.contract.symbol == contract.symbol:
                return pos.position

        return 0.0
    except Exception as e:
        logging.error(f"Error checking position for {contract.symbol}: {e}")
        return 0.0

# --- Core Risk and Order Logic ---

def calculate_order_quantity(
    ticker: str,
    signal_source: str,
    entry_price: float,
    stop_level: float
) -> float:
    """Calculates the order quantity based on capital allocation and risk per trade percentage."""

    if entry_price <= stop_level:
        logging.error(f"Risk calc failed: Entry Price ({entry_price:.2f}) must be higher than Stop Level ({stop_level:.2f}) for a BUY trade.")
        return 0.0

    # 1. Determine maximum available capital based on signal source
    if signal_source == 'Module B':
        capital_pool = ARC_CAPITAL * LONG_TERM_CAPITAL_RATIO
    elif signal_source == 'Module D':
        capital_pool = ARC_CAPITAL * SHORT_TERM_CAPITAL_RATIO
    else:
        capital_pool = ARC_CAPITAL * LONG_TERM_CAPITAL_RATIO

    # 2. Calculate Max Loss Amount ($)
    max_trade_risk_amount = capital_pool * MAX_RISK_PER_TRADE_PCT

    # 3. Calculate Risk per Share ($)
    risk_per_share = entry_price - stop_level

    if risk_per_share <= 0:
        return 0.0

    # 4. Calculate Quantity and round down to integer
    final_quantity = int(max_trade_risk_amount / risk_per_share)

    if final_quantity <= 0:
        logging.warning(f"Quantity for {ticker} is 0. Risk/Share: ${risk_per_share:.2f}, Max Risk: ${max_trade_risk_amount:.2f}")
        return 0.0

    logging.info(f"Risk Check: {signal_source} pool: ${capital_pool:.2f}. Max Risk: ${max_trade_risk_amount:.2f}. Risk/Share: ${risk_per_share:.2f}. Final Qty: {final_quantity} shares.")
    return float(final_quantity)


def place_entry_order(
    ib: IB,
    contract: Contract,
    action: str,
    quantity: float,
    limit_price: float,
) -> Optional[Trade]:
    """Places a simple Limit Order for entry."""

    parent_order = LimitOrder(
        action=action,
        totalQuantity=quantity,
        lmtPrice=limit_price,
        transmit=True
    )

    try:
        trade = ib.placeOrder(contract, parent_order)
        logging.info(f"Limit Entry Order placed for {contract.symbol} ({quantity}) @ {limit_price:.2f}.")
        return trade
    except Exception as e:
        logging.error(f"Error placing entry order for {contract.symbol}: {e}")
        return None

def liquidate_position(ib: IB, contract: Contract, position_size: float, action: str):
    """
    Places a Limit Order to close the current position (Internal Stop Loss execution).
    """

    current_price = get_current_price(ib, contract)

    if current_price is None:
        logging.critical(f"STOP CHECK: Cannot get price for {contract.symbol}. Liquidating with Market Order.")
        exit_order = MarketOrder(action=action, totalQuantity=abs(position_size), transmit=True)
        trade = ib.placeOrder(contract, exit_order)
        logging.critical(f"STOP LOSS EXECUTED (MARKET): {trade.contract.symbol}")
        return trade

    # Use a slightly aggressive limit price to ensure quick fill
    if action == 'SELL':
        limit_price = current_price - TICK_ADJUSTMENT
    else: # BUY to close
        limit_price = current_price + TICK_ADJUSTMENT

    exit_order = LimitOrder(
        action=action,
        totalQuantity=abs(position_size),
        lmtPrice=limit_price,
        transmit=True
    )

    trade = ib.placeOrder(contract, exit_order)
    logging.critical(f"STOP LOSS TRIGGERED: Placing Limit Order to {action} {abs(position_size)} shares of {contract.symbol} @ {limit_price:.2f}.")
    return trade


def check_for_mandatory_liquidation(ib: IB):
    """Checks for upcoming market holidays for possible mandatory liquidation."""
    today = ib.reqCurrentTime().date()
    holidays = load_us_market_holidays()

    # Check today and the next few days
    for i in range(3):
        check_date = today + timedelta(days=i)
        if check_date in holidays:
            logging.info(f"Mandatory Liquidation Check: Holiday detected on {check_date}. Reviewing all positions for closure.")
            return

    logging.debug("Liquidation check: All clear (No immediate full holidays).")

# --- Core Execution Logic ---

def manage_limit_order_lifecycle(
    ib: IB,
    contracts_to_monitor: List[Contract],
    potential_signals: Dict[str, Dict]
) -> List[str]:
    """
    Manages new orders and existing positions (Internal Stop Loss).
    """

    signals_placed_success = []
    open_trades = ib.trades() # Non-blocking call for all active trades

    # 1. Management of Open Trades (Update INTERNAL_STOP_TRACKER upon fill)
    for trade in open_trades:
        ticker = trade.contract.symbol

        # Check if an entry order has just been filled (status is 'Filled')
        if trade.orderStatus.status == 'Filled' and ticker in potential_signals:

            # Use the actual fill price for the stop calculation
            actual_entry_price = trade.orderStatus.avgFillPrice
            # Get the original signal info before deleting it
            signal_info = potential_signals[ticker]
            strategy_stop_level = signal_info['stop_level']
            signal_source = signal_info['signal_source']

            # Store the data required for Internal Stop check
            INTERNAL_STOP_TRACKER[ticker] = {
                'entry_price': actual_entry_price,
                'internal_stop': strategy_stop_level,
                'signal_source': signal_source
            }
            logging.warning(f"Entry Order filled for {ticker}! Entry Price: {actual_entry_price:.2f}. Internal Stop set @ {strategy_stop_level:.2f}")

            # Signal is now completed (filled) -> signal the daemon to remove it from pending_signals
            signals_placed_success.append(ticker)

        # Handle trades that were cancelled
        elif trade.orderStatus.status in ['Cancelled', 'ApiCancelled'] and ticker in potential_signals:
             logging.warning(f"Pending entry order for {ticker} was cancelled. Removing from signals.")
             signals_placed_success.append(ticker)


    # 2. Strategy Execution (Placing NEW Orders)
    for ticker, signal_info in potential_signals.items():

        # Skip if the signal was just filled/cancelled in Step 1
        if ticker in signals_placed_success:
            continue

        contract = get_contract_from_ticker(ib, contracts_to_monitor, ticker)

        # Skip if a stop is already being tracked (meaning we have a position)
        if contract is None or ticker in INTERNAL_STOP_TRACKER:
            continue

        position = get_current_position(ib, contract)
        # Check if there's any open entry order for this ticker (to prevent duplicate orders)
        is_order_pending = any(t.contract.symbol == ticker and t.isActive() for t in open_trades)

        if abs(position) == 0.0 and not is_order_pending:

            limit_price = signal_info['price']
            strategy_stop_level = signal_info['stop_level']
            signal_source = signal_info['signal_source']

            quantity = calculate_order_quantity(ticker, signal_source, limit_price, strategy_stop_level)

            if quantity == 0.0:
                continue

            # Place the limit entry order
            new_trade = place_entry_order(ib, contract, 'BUY', quantity, limit_price)

            if new_trade is not None:
                # Order placed successfully, wait for fill event (Step 1)
                pass


    # 3. Manage Existing Positions (Internal Stop Loss Monitoring)
    positions = ib.positions()

    for pos in positions:
        ticker = pos.contract.symbol

        # Only check positions that we are currently tracking the stop for
        if ticker in INTERNAL_STOP_TRACKER and abs(pos.position) > 0.0:

            contract = pos.contract
            current_price = get_current_price(ib, contract)

            if current_price is None:
                logging.error(f"Cannot get market data for {ticker} for stop loss check.")
                continue

            internal_stop = INTERNAL_STOP_TRACKER[ticker]['internal_stop']

            # Check for Stop Loss Trigger (Long Position)
            if pos.position > 0 and current_price < internal_stop:
                liquidate_position(ib, contract, pos.position, 'SELL')
                # Remove from internal tracker after liquidation order is placed
                del INTERNAL_STOP_TRACKER[ticker]

            # Check for Stop Loss Trigger (Short Position)
            elif pos.position < 0 and current_price > internal_stop:
                liquidate_position(ib, contract, pos.position, 'BUY')
                del INTERNAL_STOP_TRACKER[ticker]

            else:
                logging.debug(f"Position check for {ticker}: Price {current_price:.2f}, Stop @ {internal_stop:.2f}")

    return signals_placed_success
