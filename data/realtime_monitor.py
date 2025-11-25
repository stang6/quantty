# data/realtime_monitor.py

from ibapi.client import EClient
from ibapi.contract import Contract
import logging
from data.historical_data import create_stock_contract # Reuse contract creation

# We assume a dedicated thread or asyncio loop handles this monitoring in the IBClientApp

def start_realtime_monitoring(app, ticker: str, monitor_callback_func):
    """
    Starts a subscription for real-time market data (e.g., last price) for monitoring.
    
    :param app: The connected IBClientApp instance.
    :param ticker: Stock ticker to monitor.
    :param monitor_callback_func: A function in Module C to process the price updates.
    """
    logging.info(f"Subscribing to real-time data for {ticker}...")
    
    contract = create_stock_contract(ticker)
    monitor_id = app.nextValidId()
    
    # Request tick-by-tick data (last price) for real-time monitoring
    # Snapshot=False ensures a continuous stream
    app.reqMktData(
        monitor_id, 
        contract, 
        "233", # Generic tick types for Last Price, Size, etc.
        False, # False for continuous updates
        False, # Do not include snapshot
        []
    )
    
    # In the IBClientApp (ib_wrapper.py), the EWrapper.tickPrice method
    # will continuously update the price and call the monitor_callback_func
    
    app.set_monitor_callback(monitor_id, monitor_callback_func)
    logging.info(f"Monitoring started with Request ID: {monitor_id}.")


def stop_realtime_monitoring(app, monitor_id: int):
    """Cancels the market data subscription to free up API resources."""
    logging.info(f"Cancelling real-time data subscription for ID: {monitor_id}.")
    app.cancelMktData(monitor_id)

# Example of how the data flows (internal to ib_wrapper.py):
# def tickPrice(self, reqId, tickType, price, attrib):
#     if tickType == 4: # Last Price
#         # Check if this reqId is associated with a position we are monitoring
#         if reqId in self.monitor_callbacks:
#             # Pass the new price to the Module C stop loss logic
#             self.monitor_callbacks[reqId](price)
