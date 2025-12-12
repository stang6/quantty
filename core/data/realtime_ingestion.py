# core/data/realtime_ingestion.py (FINAL FIXED VERSION with Data Integration Logic)
import time
from typing import List, Dict, Any, TYPE_CHECKING
import logging
from datetime import datetime, timezone # Added for timestamping

# Required for contract creation
from core.ibkr.contract_factory import ContractFactory 
from core.logging.logger import get_logger
# NEW IMPORTS
from core.strategy.strategy_manager import StrategyManager 
from core.strategy.base_strategy import BaseStrategy 
from core.strategy.stage2_breakdown_strategy import Stage2BreakdownStrategy # Concrete example

# Type Checking for imports
if TYPE_CHECKING:
    from core.ibkr.ib_connection import IBConnection
    from core.monitor.dashboard import Dashboard


logger = get_logger("RTINGEST")

class RealtimeIngestion:
    
    def __init__(self, conn: 'IBConnection', symbols: List[str], poll_interval: int, 
                 dashboard: 'Dashboard', strategy_allocations: Dict[str, List[str]]):
        """
        Initializes the multi-symbol RealtimeIngestion system.
        """
        self.conn = conn
        self.symbols = symbols
        self.poll_interval = poll_interval
        self.dashboard = dashboard
        self.strategy_allocations = strategy_allocations
        
        self.contract_factory = ContractFactory()
        self.ib_app = conn.ib # Low-level IB application instance
        # req_id_map is kept but not strictly necessary since we let ib_insync manage IDs
        self.req_id_map: Dict[str, int] = {} 
        
        # 20251210 - 13:33 just for testing
        # --- TEST OVERRIDE START: Temporarily set a high WMA for TSLA to force a sell alert ---
        # Note: In the new architecture, WMA is handled by StageAnalyzer/Strategies, 
        # but the remark is kept for context.
        # --- TEST OVERRIDE END ---
        # 20251210 - 13:33 just for testing
        
        # --- Strategy Management Initialization ---
        self.strategy_manager = self._initialize_strategies()
        # ----------------------------------------
        
        self._request_market_data()
        
        logger.info(f"RealtimeIngestion initialized for {len(self.symbols)} symbol(s).")


    def _initialize_strategies(self) -> StrategyManager:
        """Initializes and registers all active strategy instances based on allocation map."""
        manager = StrategyManager(
            # Pass the registry that holds the real-time data
            snapshot_registry=self.dashboard.snapshot_registry, 
            poll_interval=self.poll_interval
        )
        
        # Iterating through the allocation map to instantiate strategies
        for name, symbols in self.strategy_allocations.items():
            if not symbols:
                continue
                
            if name == "StanStrategy":
                # StanStrategy (e.g., Stage 1/2): Long-term trend following
                # We defer StanStrategy implementation for now, but log the allocation
                logger.info(f"[{name}] Found 1 symbols. Strategy instance creation deferred.")
                
            elif name == "FujimotoStrategy":
                # FujimotoStrategy (e.g., Stage 2): Short-term swing/breakdown
                for symbol in symbols:
                    # NOTE: We are reusing Stage2BreakdownStrategy as the concrete example 
                    # for the Fujimoto strategy type in this MVP architecture.
                    strategy_instance = Stage2BreakdownStrategy(
                        symbol=symbol,
                        snapshot_registry=self.dashboard.snapshot_registry
                    )
                    manager.add_strategy(name, symbol, strategy_instance)
                    
        return manager


    def _request_market_data(self):
        """
        Requests real-time market data for all unique symbols.
        Relies on ib_insync to automatically manage Request IDs (reqId).
        """
        if not self.ib_app.isConnected():
             logger.warning("[RTINGEST] Cannot request market data: IB connection not active.")
             return
             
        # FIX: The simplest way is the best way. Let IB/ib_insync manage IDs.
        for symbol in self.symbols:
            contract = self.contract_factory.create_stock_contract(symbol, "SMART")
            
            # Request market data, letting ib_insync assign the reqId.
            self.ib_app.reqMktData(contract=contract, genericTickList="", 
                                   snapshot=False, regulatorySnapshot=False, mktDataOptions=[])
            
            logger.info(f"[{symbol}] Requested market data.")


    def _process_market_data(self):
        """
        Retrieves the latest Ticker objects from ib_insync and updates the local snapshot registry.
        """
        # Get all actively monitored Tickers from ib_insync's internal list
        active_tickers = self.ib_app.tickers()
        
        current_time_utc = datetime.now(timezone.utc).isoformat(timespec='seconds')
        
        for ticker in active_tickers:
            symbol = ticker.contract.symbol
            
            # Check if we are monitoring this symbol
            if symbol in self.dashboard.snapshot_registry:
                # Retrieve the existing snapshot (contains WMA/Stage)
                snap = self.dashboard.snapshot_registry[symbol]
                
                # We only update if the ticker has received a valid bid/ask/last price,
                # indicated by a non-empty time field (time/bidGmt/askGmt).
                # Checking for ticker.time (last trade time) is often sufficient.
                if not ticker.time:
                    # If ticker has no data, skip updating (keep the current state, e.g., '0.00' from init)
                    continue

                # --- Update real-time price fields ---
                # Use 'last' price if available, otherwise use mid-point or bid/ask
                last_price = ticker.last if ticker.last is not None else 0.0
                
                # Update the snapshot dictionary with live data
                snap.update({
                    # IB's Ticker attributes are Bid/Ask/Last
                    'bid': ticker.bid if ticker.bid is not None and ticker.bid > 0 else 0.0,
                    'ask': ticker.ask if ticker.ask is not None and ticker.ask > 0 else 0.0,
                    'last': last_price,
                    'volume': ticker.volume if ticker.volume is not None else 0,
                    # We use the current system time for update, as Ticker.time might be sparse
                    'ts': current_time_utc,
                })
                
                # Optional: Log a message when data first starts flowing (or every few updates)
                if last_price > 0.0 and snap.get('last') == 0.0:
                    logger.info(f"[{symbol}] Starting real-time data flow.")


    def run_step(self):
        """
        The main hook logic executed periodically by the IB event loop.
        Handles data processing, strategy execution, and dashboard rendering.
        """
        # 1. Data Processing: Explicitly pull data from IB Tickers and populate the registry
        self._process_market_data()
        
        # 2. Strategy Execution
        self.strategy_manager.run_all_strategies()
        
        # 3. Dashboard Rendering
        self.dashboard.render_once()
        
    
    def start_loop(self):
        """
        Starts the IB event loop and registers the run_step hook.
        This method is called by main.py.
        """
        if not self.ib_app.isConnected():
            logger.critical("Cannot start loop: IB connection is not established.")
            return

        logger.info(f"[RTINGEST] Launching IB event loop with {self.poll_interval} second interval hook...")
        
        # Start the IB event loop using the wrapper, passing the hook and interval
        self.conn.start(loop_hook=self.run_step, interval=self.poll_interval)
