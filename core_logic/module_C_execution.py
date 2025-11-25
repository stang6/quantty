
# ============================================
# core_logic/module_C_execution.py (Updated for Internal Stop Management)
# ============================================

import logging
from ib_insync import IB, Contract, Order, Trade, util, LimitOrder, MarketOrder
from typing import List
from datetime import datetime, timedelta
import pandas as pd # Needed for potential PnL calculations or price access

# Global dictionary to track active trades and their entry prices/internal stop levels
# {ticker: {'entry_trade': Trade object, 'position': float, 'entry_price': float, 'internal_stop': float}}
ACTIVE_TRADES = {}

# --- 輔助函式 (Helpers) ---

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
        # ib.positions(contract) returns a list, take the first element (the position object)
        position = ib.positions(contract)[0].position
        return position
    except IndexError:
        return 0.0
    except Exception as e:
        logging.error(f"Error checking position for {contract.symbol}: {e}")
        return 0.0

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

# --- 核心執行邏輯 (Core Execution) ---

def check_for_mandatory_liquidation(ib: IB):
    # A placeholder function to check if the system needs to liquidate all positions
    current_date = ib.reqCurrentTime().date()

    # Example: Mandatory liquidation before US Thanksgiving (2025-11-27 is Thursday)
    if current_date.weekday() in [0, 1, 2]: # Mon, Tue, Wed
        thanksgiving = datetime(2025, 11, 27).date()
        if thanksgiving - current_date < timedelta(days=3): # If less than 3 days away
            logging.info(f"Liquidation check: Holiday {thanksgiving} detected soon. Review positions for mandatory exit.")
            # Full liquidation implementation omitted for now, but the check is running.
        else:
            logging.debug("Liquidation check: All clear.")
    pass

def manage_limit_order_lifecycle(ib: IB, contracts_to_monitor: List[Contract], potential_signals: List[str]):
    # The heart of Module C. It manages:
    # 1. Placing new orders if signals are detected.
    # 2. Monitoring open orders (filling/canceling).
    # 3. Managing existing positions (Internal Stop Loss).


    # A. Strategy Execution (Placing NEW Orders)
    for ticker in potential_signals:
        contract = next((c for c in contracts_to_monitor if c.symbol == ticker), None)
        if contract is None:
            continue

        position = get_current_position(ib, contract)
        is_order_pending = check_open_orders(ib, contract)

        # Only place a new order if there is a signal, no position, and no open order
        if position == 0.0 and not is_order_pending:
            # FIX: Needs actual price and quantity calculation. Using placeholders.
            limit_price = ib.reqMktData(contract).close
            quantity = 100 # Placeholder quantity

            if limit_price is not None:
                # Place the limit entry order
                new_trade = place_entry_order(ib, contract, 'BUY', quantity, limit_price)

                # IMPORTANT: Calculate and store the internal stop loss level immediately
                entry_price = limit_price # For a limit order, this is the intended entry price
                # Example: Set stop loss 5% below entry price
                internal_stop_level = entry_price * 0.95

                ACTIVE_TRADES[ticker] = {
                    'entry_trade': new_trade,
                    'position': quantity,
                    'entry_price': entry_price,
                    'internal_stop': internal_stop_level
                }
                logging.warning(f"Strategy: Placing NEW order for {ticker}. Internal Stop set @ {internal_stop_level:.2f}")


    # B. Manage Open Orders (Filling)
    trades_to_remove = []
    for ticker, trade_info in list(ACTIVE_TRADES.items()): # Iterate over a copy
        trade = trade_info['entry_trade']

        # 1. Check if the limit order was filled
        if trade.orderStatus.status == 'Filled':
            # This logic assumes the entire position was filled in one go
            logging.info(f"Order filled for {trade.contract.symbol}! Position taken. Entry Price: {trade.orderStatus.avgFillPrice:.2f}")

            # Update entry price and stop level based on actual fill price
            actual_entry_price = trade.orderStatus.avgFillPrice
            trade_info['entry_price'] = actual_entry_price
            trade_info['internal_stop'] = actual_entry_price * 0.95 # Recalculate based on fill price

            logging.info(f"Internal Stop updated to {trade_info['internal_stop']:.2f} based on fill price.")

        elif trade.orderStatus.status in ['Cancelled', 'ApiCancelled']:
            logging.warning(f"Order for {trade.contract.symbol} was cancelled. Removing from active trades.")
            trades_to_remove.append(ticker)

        # 2. Add timeout/cancellation logic here if needed (e.g., if order is stale)

    # Remove cancelled trades
    for ticker in trades_to_remove:
        del ACTIVE_TRADES[ticker]


    # C. Manage Existing Positions (Internal Stop Loss Monitoring)
    for ticker, trade_info in list(ACTIVE_TRADES.items()):
        position = get_current_position(ib, trade_info['entry_trade'].contract)

        # Only proceed if we actually hold a position
        if abs(position) > 0.0:
            contract = trade_info['entry_trade'].contract

            # Get the current market price for stop monitoring
            # FIX: We need robust market data handling. Using a simplified approach here.
            market_data = ib.reqMktData(contract, '', False, False)
            ib.sleep(0.5) # Allow time for data update

            current_price = market_data.close if market_data and market_data.close else None

            ib.cancelMktData(contract) # Cancel subscription immediately to avoid data overload

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
                liquidate_position(ib, contract, position, 'BUY')
                # Remove from active trades
                del ACTIVE_TRADES[ticker]

            # Log status
            logging.debug(f"Position check for {ticker}: Price {current_price:.2f}, Stop @ {internal_stop:.2f}")

    pass
