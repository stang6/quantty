# core/data/aapl_ingestion.py
import math
from datetime import datetime, timezone

from ib_insync import Stock
from core.data.ingestion_base import IngestionBase
from core.storage.writers import CSVWriter
from core.logging.logger import get_logger
logger = get_logger("AAPL")


class AaplIngestion(IngestionBase):
    def __init__(self, ib, poll_interval_sec=5, output_path="data/aapl_realtime_ticks.csv", snapshot_registry=None, wma_price: float = 0.0):
        super().__init__(poll_interval_sec, wma_price)
        self.ib = ib
        self.writer = CSVWriter(output_path)
        self._ticker = None
        self.snapshot_registry = snapshot_registry
        self.symbol = "AAPL"

    def ensure_subscription(self):
        if self._ticker is not None:
            return
        contract = Stock("AAPL", "SMART", "USD")
        self._ticker = self.ib.reqMktData(contract, "", False, False)
        logger.info("AAPL: Subscribed to realtime market data")

    def write_snapshot(self):
        try:
            t = self._ticker
            if t is None:
                return

            bid = float(t.bid or 0.0)
            ask = float(t.ask or 0.0)
            last = float(t.last or 0.0)

            raw_volume = t.volume
            try:
                volume = int(raw_volume)
            except Exception:
                volume = 0

            ts = datetime.now(timezone.utc).isoformat()

            self.writer.write({
                "ts_utc": ts,
                "bid": bid,
                "ask": ask,
                "last": last,
                "volume": volume,
            })

            # dashboard feed
            if self.snapshot_registry is not None:
                self.snapshot_registry[self.symbol] = {
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "volume": volume,
                    "ts": ts,
                }

            logger.debug(
                "%s: Snapshot ts=%s bid=%.2f ask=%.2f last=%.2f vol=%d",
                self.symbol, ts, bid, ask, last, volume
            )

        except Exception as e:
            logger.error("%s: Ingestion error: %s", self.symbol, e, exc_info=True)

