# core/strategy/base_strategy.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies in Quantty."""
    
    def __init__(self, symbol: str, snapshot_registry: Dict[str, Any]):
        """
        Initializes the base strategy.
        
        Args:
            symbol: The specific symbol this strategy instance is monitoring.
            snapshot_registry: The shared dictionary containing real-time market data snapshots.
        """
        self.symbol = symbol
        self.snapshot_registry = snapshot_registry
        
    @abstractmethod
    def run_strategy(self):
        """
        The core execution method, called on every loop cycle.
        Implement the entry/exit logic here using data from snapshot_registry.
        """
        pass
