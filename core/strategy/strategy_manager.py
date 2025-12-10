# core/strategy/strategy_manager.py
from typing import Dict, List, Any, TYPE_CHECKING
import logging
import time

if TYPE_CHECKING:
    from core.strategy.base_strategy import BaseStrategy # For type hinting

logger = logging.getLogger("STRATMGR")

class StrategyManager:
    """
    Manages the lifecycle and execution of all active trading strategies.
    Maps symbols to their respective strategy instances.
    """
    def __init__(self, snapshot_registry: Dict[str, Any], poll_interval: int):
        self.snapshot_registry = snapshot_registry
        self.poll_interval = poll_interval
        # Structure: {'StanStrategy': {'NVDA': StanStrategyInstance, ...}, 'FujimotoStrategy': {...}}
        self.strategies: Dict[str, Dict[str, 'BaseStrategy']] = {}
        logger.info("StrategyManager initialized.")

    def add_strategy(self, name: str, symbol: str, instance: Any):
        """Registers a new strategy instance for a specific symbol under a strategy name."""
        if name not in self.strategies:
            self.strategies[name] = {}
        # Ensure the instance conforms to the BaseStrategy interface if possible
        self.strategies[name][symbol] = instance 
        logger.debug(f"[{name}] Strategy registered for {symbol}.")

    def run_all_strategies(self):
        """Executes the run_strategy method for every active strategy instance."""
        start_time = time.time()
        
        for strat_name, symbol_map in self.strategies.items():
            for symbol, strategy in symbol_map.items():
                try:
                    # The strategy uses its self.snapshot_registry access to get the latest price
                    strategy.run_strategy() 
                except Exception as e:
                    logger.error(f"[{strat_name}/{symbol}] Error running strategy: {e}", exc_info=True)
                    
        end_time = time.time()
        # Only log strategy runtime at DEBUG level
        logger.debug(f"[MGR] All strategies executed in {(end_time - start_time) * 1000:.2f}ms.")
