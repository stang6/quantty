# core/data/aapl_ingestion.py
import logging
import math
from datetime import datetime, timezone

from ib_insync import Stock
from core.data.ingestion_base import IngestionBase
from core.storage.writers import CSVWriter


class AaplIngestion(IngestionBase):
    """
    AAPL realtime ingestion.
    """

    def __init__(self, ib, poll_interval_sec=5, output_path="data/aapl_realtime_ticks.csv"):
        super().__init__(poll_interval_sec)
        self.ib = ib
        self.writer = CSVWriter(output_path)
        self._ticker = None

    def ensure_subscription(self) -> None:
        if self._ticker is not None:
            return

        contract = Stock("AAPL", "SMART", "USD")
        self._ticker = self.ib.reqMktData(contract, "", False, False)
        logging.info("AAPL: Subscribed to realtime market data")

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

            self.writer.write({
                "ts_utc": ts,
                "bid": bid,
                "ask": ask,
                "last": last,
                "volume": volume,
            })

            logging.info(
                "AAPL: Snapshot ts=%s bid=%.2f ask=%.2f last=%.2f vol=%d",
                ts, bid, ask, last, volume
            )

        except Exception as e:
            logging.error("AAPL: Ingestion error: %s", e, exc_info=True)

