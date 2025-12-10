# core/data/realtime_ingestion.py
import math
from datetime import datetime, timezone

from ib_insync import Stock, IB
from core.data.ingestion_base import IngestionBase
from core.storage.writers import CSVWriter
from core.logging.logger import get_logger

# Use a generic logger for the module
MODULE_LOGGER = get_logger("RT_ING")


class RealtimeIngestion(IngestionBase):
    """
    Generic ingestion class for any stock symbol.
    Responsible for connecting to IB and updating the snapshot registry.
    Strategy logic is NOT included here.
    """
    def __init__(self, ib: IB, symbol: str, poll_interval_sec: int, 
                 output_path: str, snapshot_registry: dict, wma_price: float = 0.0):
        
        # IngestionBase.__init__ handles poll_interval_sec and wma_price
        super().__init__(poll_interval_sec, wma_price) 

        # 20251210 - 13:33 just for testing
        # --- TEST OVERRIDE START: Temporarily set a high WMA for TSLA to force a sell alert ---
        ##if symbol == "TSLA":
            # Assuming TSLA current price is around 180-200. Setting WMA higher forces last < wma.
        ##    self.wma_price = 500.0
        ##    MODULE_LOGGER.critical("TSLA WMA OVERRIDE: Set to 500.0 to trigger Stage 2 Sell Signal for testing.")
        # --- TEST OVERRIDE END ---
        # 20251210 - 13:33 just for testing
        
        self.ib = ib
        self.symbol = symbol
        self.writer = CSVWriter(output_path)
        self._ticker = None
        self.snapshot_registry = snapshot_registry
        
        # Use a specific logger for this instance
        self.logger = get_logger(self.symbol) 

    def ensure_subscription(self):
        if self._ticker is not None:
            return
        
        # Contract is defined using the instance symbol
        contract = Stock(self.symbol, "SMART", "USD")
        self._ticker = self.ib.reqMktData(contract, "", False, False)
        self.logger.info("%s: Subscribed to realtime market data", self.symbol)

    def write_snapshot(self):
        try:
            t = self._ticker
            if t is None:
                return

            bid = float(t.bid or 0.0)
            ask = float(t.ask or 0.0)
            last = float(t.last or 0.0)
            
            # Volume handling...
            raw_volume = t.volume
            try:
                volume = int(raw_volume)
            except Exception:
                volume = 0

            ts = datetime.now(timezone.utc).isoformat()

            # Write CSV
            self.writer.write({
                "ts_utc": ts, "bid": bid, "ask": ask, "last": last, 
                "volume": volume
            })

            # Update dashboard snapshot
            if self.snapshot_registry is not None:
                self.snapshot_registry[self.symbol] = {
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "volume": volume,
                    "ts": ts,
                    "wma": self.wma_price,
                }
            
            # logger.debug
            self.logger.debug(
                "%s: Snapshot ts=%s bid=%.2f ask=%.2f last=%.2f vol=%d wma=%.2f",
                self.symbol, ts, bid, ask, last, volume, self.wma_price
            )

        except Exception as e:
            self.logger.error("%s: Ingestion error: %s", self.symbol, e, exc_info=True)
