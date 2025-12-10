# core/strategy/strategy_base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class StrategyBase(ABC):
    """
    Abstract base class for all trading strategies.
    Each strategy is responsible for monitoring one symbol.
    """
    def __init__(self, symbol: str, stage_registry: Dict[str, Any], snapshot_registry: Dict[str, Any]):
        self.symbol = symbol
        self.stage_registry = stage_registry
        self.snapshot_registry = snapshot_registry
        
    @abstractmethod
    def run_strategy(self):
        """
        Executed periodically to check strategy conditions.
        """
        pass
