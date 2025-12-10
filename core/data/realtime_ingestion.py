# core/data/realtime_ingestion.py (HEAVILY REFACTORED)
import time
from typing import List, Dict, Any, TYPE_CHECKING
import logging

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
        self.req_id_map: Dict[str, int] = {} # Map symbol to IB reqId
        
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
                logger.info(f"[{name}] Found {len(symbols)} symbols. Strategy instance creation deferred.")
                
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
        """Requests real-time market data for all unique symbols."""
        if not self.ib_app.isConnected():
             logger.warning("[RTINGEST] Cannot request market data: IB connection not active.")
             return
             
        current_req_id = self.ib_app.nextValidId # Get the next available ID
        
        for symbol in self.symbols:
            contract = self.contract_factory.create_stock_contract(symbol, "SMART")
            req_id = current_req_id
            self.req_id_map[symbol] = req_id
            
            # Request market data (snapshot=False for streaming data)
            self.ib_app.reqMktData(reqId=req_id, contract=contract, genericTickList="", 
                                   snapshot=False, regulatorySnapshot=False, mktDataOptions=[])
            
            logger.info(f"[{symbol}] Requested market data with reqId {req_id}.")
            
            current_req_id += 1 

        self.ib_app.nextValidId = current_req_id # Update the internal ID tracker

    
    def run_step(self):
        """
        The main hook logic executed periodically by the IB event loop.
        Handles data processing, strategy execution, and dashboard rendering.
        """
        # 1. Data is implicitly updated in the IB client's handlers which populates self.dashboard.snapshot_registry
        
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
