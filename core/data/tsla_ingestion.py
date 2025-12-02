# core/data/tsla_ingestion.py
import math
from datetime import datetime, timezone

from ib_insync import Stock
from core.data.ingestion_base import IngestionBase
from core.storage.writers import CSVWriter
from core.logging.logger import get_logger

logger = get_logger("TSLA")

class TslaIngestion(IngestionBase):
    """
    TSLA realtime ingestion.
    Handles subscription + periodic snapshot writing.
    Supports Issue #4, #5, #6, and now fits Issue #7 abstraction.
    """

    def __init__(self, ib, poll_interval_sec=5, output_path="data/tsla_realtime_ticks.csv"):
        super().__init__(poll_interval_sec)
        self.ib = ib
        self.writer = CSVWriter(output_path)
        self._ticker = None

    # ---------------------------------------------------------
    # Required by IngestionBase
    # ---------------------------------------------------------
    def ensure_subscription(self) -> None:
        if self._ticker is not None:
            return

        contract = Stock("TSLA", "SMART", "USD")
        self._ticker = self.ib.reqMktData(contract, "", False, False)
        logger.info("TSLA: Subscribed to realtime market data")

    # ---------------------------------------------------------
    # Required by IngestionBase
    # ---------------------------------------------------------
    def write_snapshot(self) -> None:
        try:
            t = self._ticker
            if t is None:
                return

            bid = float(t.bid or 0.0)
            ask = float(t.ask or 0.0)
            last = float(t.last or 0.0)

            raw_volume = t.volume
            if raw_volume is None or (isinstance(raw_volume, float) and math.isnan(raw_volume)):
                volume = 0
            else:
                volume = int(raw_volume)

            ts = datetime.now(timezone.utc).isoformat()

            # Write using CSVWriter
            self.writer.write({
                "ts_utc": ts,
                "bid": bid,
                "ask": ask,
                "last": last,
                "volume": volume,
            })

            logger.info(
                "TSLA: Snapshot ts=%s bid=%.2f ask=%.2f last=%.2f vol=%d",
                ts, bid, ask, last, volume
            )

        except Exception as e:
            logger.error("TSLA: Ingestion error: %s", e, exc_info=True)

