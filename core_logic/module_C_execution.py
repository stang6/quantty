
# ============================================
# core_logic/module_C_execution.py (Updated with Capital Allocation)
# ============================================

import logging
from ib_insync import IB, Contract, Order, Trade, util, LimitOrder, MarketOrder
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import pandas as pd

# NEW: Import capital parameters
from config.parameters import (
    ARC_CAPITAL,
    LONG_TERM_CAPITAL_RATIO,
    SHORT_TERM_CAPITAL_RATIO,
    MAX_RISK_PER_TRADE
)

# Global dictionary to track active trades and their entry prices/internal stop levels
# {ticker: {'entry_trade': Trade object, 'position': float, 'entry_price': float, 'internal_stop': float, 'signal_type': str}}
ACTIVE_TRADES: Dict[str, Dict] = {}

# --- Helper Functions ---

def check_open_orders(ib: IB, contract: Contract) -> bool:
    # Check if there is any pending order for the given contract.
    open_orders = ib.reqOpenOrders()

    # Check if the list contains any order for the specific contract
    for order in open_orders:
        if order.contract.symbol == contract.symbol:
            return True

    return False

def get_current_position(ib: IB, contract: Contract) -> float:
    # Get the current position size for a contract. Returns 0.0 if no position is found.
    try:
        all_positions = ib.positions()

        for pos in all_positions:
            if pos.contract.symbol == contract.symbol:
                return pos.position

        return 0.0
    except Exception as e:
        logging.error(f"Error checking position for {contract.symbol}: {e}")
        return 0.0

# NEW FUNCTION: Calculate position quantity based on risk and capital allocation
def calculate_order_quantity(ticker: str, signal_type: str, current_price: float, risk_per_share: float) -> float:
    """
    Calculates the order quantity based on capital allocation and risk per trade.
    risk_per_share: The dollar amount of loss per share (Entry Price - Stop Price).
    """
    if risk_per_share <= 0:
        logging.error(f"Cannot calculate quantity for {ticker}: Risk per share is zero or negative.")
        return 0.0

    # 1. Determine maximum available capital based on signal type
    if signal_type == 'LONG':
        capital_ratio = LONG_TERM_CAPITAL_RATIO
    elif signal_type == 'SHORT':
        capital_ratio = SHORT_TERM_CAPITAL_RATIO
    else:
        logging.error(f"Invalid signal type '{signal_type}' for {ticker}. Using LONG capital ratio.")
        capital_ratio = LONG_TERM_CAPITAL_RATIO

    # Total maximum capital allocated to this strategy group
    max_group_capital = ARC_CAPITAL * capital_ratio

    # 2. Determine Max Quantity based on MAX_RISK_PER_TRADE
    # Max shares = MAX_RISK_PER_TRADE / Risk per share (Dollar amount of max loss)
    max_quantity_by_risk = MAX_RISK_PER_TRADE / risk_per_share

    # 3. Determine Max Quantity based on Max Group Capital (Ensuring we don't overspend)
    # This check is less about risk and more about position size limits in this context.
    # For now, we will focus on the risk-based calculation (2) unless you define
    # a separate max position size relative to the allocated capital.

    # Final Quantity: Use the risk-based quantity
    final_quantity = int(max_quantity_by_risk)

    if final_quantity <= 0:
        logging.warning(f"Quantity for {ticker} is 0. Risk per share ({risk_per_share:.2f}) might be too low or too high.")
        return 0.0

    logging.info(f"Capital Allocation: {signal_type} group max capital: ${max_group_capital:.2f}. Calculated final quantity for {ticker}: {final_quantity} shares.")
    return float(final_quantity)


def place_entry_order(
    ib: IB,
    contract: Contract,
    action: str, # 'BUY' or 'SELL'
    quantity: float,
    limit_price: float,
) -> Trade:
    # Places a simple Limit Order for entry. No linked orders.

    parent_order = LimitOrder(
        action=action,
        totalQuantity=quantity,
        lmtPrice=limit_price,
        transmit=True # Transmit immediately
    )

    trade = ib.placeOrder(contract, parent_order)

    logging.info(f"Limit Entry Order placed for {contract.symbol} @ {limit_price}.")

    # Store the initial trade object temporarily
    return trade

def liquidate_position(ib: IB, contract: Contract, position_size: float, action: str):
    # Places a Market Order to close the current position.

    exit_order = MarketOrder(
        action=action,
        totalQuantity=abs(position_size),
        transmit=True
    )

    trade = ib.placeOrder(contract, exit_order)
    logging.critical(f"STOP LOSS TRIGGERED: Placing Market Order to {action} {abs(position_size)} shares of {contract.symbol} to close position.")
    return trade

# --- Core Execution Logic ---

def check_for_mandatory_liquidation(ib: IB):
    # A placeholder function to check if the system needs to liquidate all positions
    current_date = ib.reqCurrentTime().date()
    # Example: Mandatory liquidation before US Thanksgiving (2025-11-27 is Thursday)
    thanksgiving = datetime(2025, 11, 27).date()

    if current_date.weekday() in [0, 1, 2]: # Mon, Tue, Wed
        if thanksgiving - current_date < timedelta(days=3): # If less than 3 days away
            logging.info(f"Liquidation check: Holiday {thanksgiving} detected soon. Review positions for mandatory exit.")
            # Full liquidation implementation omitted for now, but the check is running.
        else:
            logging.debug("Liquidation check: All clear.")
    pass

# UPDATED: potential_signals now is a Dict[str, str] = {ticker: 'LONG'/'SHORT'}
def manage_limit_order_lifecycle(ib: IB, contracts_to_monitor: List[Contract], potential_signals: Dict[str, str]):
    # The heart of Module C. It manages:
    # 1. Placing new orders if signals are detected (with capital allocation).
    # 2. Monitoring open orders (filling/canceling).
    # 3. Managing existing positions (Internal Stop Loss).

    # NOTE: The stop loss logic (0.95 multiplier) is currently hardcoded and should be
    # calculated dynamically based on ATR or the strategy's risk rules in a later step.

    # A. Strategy Execution (Placing NEW Orders)
    for ticker, signal_type in potential_signals.items():
        contract = next((c for c in contracts_to_monitor if c.symbol == ticker), None)
        if contract is None:
            continue

        position = get_current_position(ib, contract)
        is_order_pending = check_open_orders(ib, contract)

        # Only place a new order if there is a signal, no position, and no open order
        if position == 0.0 and not is_order_pending:

            # Get latest market data synchronously using ib.reqTickers()
            try:
                ticker_data = ib.reqTickers(contract)
                if not ticker_data or ticker_data[0].last is None:
                    logging.error(f"Failed to get current price for {ticker}. Skipping order.")
                    continue

                limit_price = ticker_data[0].last # Use the last traded price for the limit price

            except Exception as e:
                logging.error(f"Error fetching ticker data for {ticker}: {e}")
                continue

            if limit_price is not None:

                # IMPORTANT: Calculate risk per share for the entry trade
                # We use the hardcoded 5% stop loss for simplicity in this version
                # Long position risk per share = Entry Price - Stop Price
                entry_stop_level = limit_price * 0.95
                risk_per_share = limit_price - entry_stop_level

                # --- NEW: Calculate Quantity using Capital Allocation ---
                quantity = calculate_order_quantity(ticker, signal_type, limit_price, risk_per_share)
                # ----------------------------------------------------

                if quantity == 0.0:
                    logging.warning(f"Order quantity calculated as 0 for {ticker}. Skipping order placement.")
                    continue

                # Place the limit entry order
                new_trade = place_entry_order(ib, contract, 'BUY', quantity, limit_price)

                # IMPORTANT: Store internal stop level and signal type
                ACTIVE_TRADES[ticker] = {
                    'entry_trade': new_trade,
                    'position': quantity,
                    'entry_price': limit_price,
                    'internal_stop': entry_stop_level, # Already calculated above
                    'signal_type': signal_type # NEW: Store signal type
                }
                logging.warning(f"Strategy: Placing NEW {signal_type} order for {ticker} ({quantity} shares). Internal Stop set @ {entry_stop_level:.2f}")

    # B. Manage Open Orders (Filling/Cancellation)
    trades_to_remove = []
    for ticker, trade_info in list(ACTIVE_TRADES.items()):
        trade = trade_info['entry_trade']

        # 1. Check if the limit order was filled
        if trade.orderStatus.status == 'Filled':
            # Update entry price and stop level based on actual fill price
            actual_entry_price = trade.orderStatus.avgFillPrice
            trade_info['entry_price'] = actual_entry_price

            # Recalculate stop based on actual fill price (using 5% for now)
            trade_info['internal_stop'] = actual_entry_price * 0.95

            logging.info(f"Order filled for {trade.contract.symbol}! Position taken. Entry Price: {actual_entry_price:.2f}. Internal Stop updated to {trade_info['internal_stop']:.2f}")

        elif trade.orderStatus.status in ['Cancelled', 'ApiCancelled']:
            logging.warning(f"Order for {trade.contract.symbol} was cancelled. Removing from active trades.")
            trades_to_remove.append(ticker)

    # Remove cancelled trades
    for ticker in trades_to_remove:
        del ACTIVE_TRADES[ticker]

    # C. Manage Existing Positions (Internal Stop Loss Monitoring)
    for ticker, trade_info in list(ACTIVE_TRADES.items()):
        contract = trade_info['entry_trade'].contract
        position = get_current_position(ib, contract)

        # Only proceed if we actually hold a position
        if abs(position) > 0.0:

            # Use reqTickers for current price check
            try:
                market_data = ib.reqTickers(contract)
                current_price = market_data[0].last if market_data and market_data[0].last else None
            except Exception as e:
                logging.error(f"Error fetching live ticker data for {ticker} for stop check: {e}")
                continue

            if current_price is None:
                logging.error(f"Cannot get market data for {ticker} to check stop loss.")
                continue

            internal_stop = trade_info['internal_stop']

            # Check for Stop Loss Trigger (assuming 'BUY' for simplicity)
            if position > 0 and current_price < internal_stop:
                # Stop triggered! Liquidate the long position with a SELL market order
                liquidate_position(ib, contract, position, 'SELL')
                # Remove from active trades
                del ACTIVE_TRADES[ticker]

            elif position < 0 and current_price > internal_stop:
                # Stop triggered! Liquidate the short position with a BUY market order
                # NOTE: This part is for general risk management; current strategies are BUY only.
                liquidate_position(ib, contract, position, 'BUY')
                # Remove from active trades
                del ACTIVE_TRADES[ticker]

            # Log status
            logging.debug(f"Position check for {ticker}: Price {current_price:.2f}, Stop @ {internal_stop:.2f}")
    pass
