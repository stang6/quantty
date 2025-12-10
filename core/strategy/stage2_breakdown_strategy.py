# core/strategy/stage2_breakdown_strategy.py
from core.strategy.strategy_base import StrategyBase
from core.logging.logger import get_logger

logger = get_logger("STRATEGY")

class Stage2BreakdownStrategy(StrategyBase):
    """
    Implements the Stan Weinstein Stage 2 breakdown (Sell) alert.
    Condition: Price falls below the 30-WMA.
    """
    def __init__(self, symbol, stage_registry, snapshot_registry):
        super().__init__(symbol, stage_registry, snapshot_registry)
        self.wma_price = stage_registry.get(self.symbol, {}).get('current_wma', 0.0)
        self.current_stage = stage_registry.get(self.symbol, {}).get('current_stage', 'UNKNOWN')
        
        # Only monitor if it's currently in STAGE 2
        self.is_active = "STAGE 2" in self.current_stage
        
        if self.is_active:
            logger.info(f"[{self.symbol}] Stage 2 Breakdown Strategy Activated (WMA: {self.wma_price:.2f})")

    def run_strategy(self):
        if not self.is_active or self.wma_price == 0.0:
            return

        # Get latest snapshot data
        snapshot = self.snapshot_registry.get(self.symbol)
        if not snapshot:
            return

        last_price = snapshot.get("last", 0.0)

        # Retrieve the WMA value from snapshot_registry, which may be the overridden test value
        wma_to_check = snapshot.get("wma", 0.0)

        # Core Stage 2 breakdown alert logic
        if last_price > 0.0 and wma_to_check > 0.0 and last_price < wma_to_check:
        #if last_price > 0.0 and last_price < self.wma_price:
            logger.critical(
                "CRITICAL STAGE BREAKDOWN: [%s] Last Price (%.2f) is BELOW 30-WMA (%.2f)! Stage 2 Sell Signal.",
                self.symbol, last_price, wma_to_check # <--- Use wma_to_check for the log message
            )
