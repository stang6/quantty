# core/data/tsla_ingestion.py
import time
import logging
import math
from pathlib import Path
from datetime import datetime, timezone

from ib_insync import Stock
from core.storage.writers import CSVWriter


class TslaIngestion:
    """
    Subscribe to TSLA realtime market data and,
    every N seconds, write a snapshot (bid/ask/last/volume).

    This covers:
    - Issue #4: realtime subscription for TSLA
    - Issue #5: 5-second ingestion loop
    - Issue #6: decouple writer (CSVWriter)
    """

    def __init__(
        self,
        ib,
        poll_interval_sec: int = 5,
        output_path: str = "data/tsla_realtime_ticks.csv",
    ):
        self.ib = ib
        self.poll_interval_sec = poll_interval_sec
        self._next_run_ts = time.time()
        self._ticker = None

        # Use new CSVWriter (replaces manual CSV logic)
        self.writer = CSVWriter(output_path)

    # -----------------------------
    # Public: called from IB main loop
    # -----------------------------
    def run_step(self) -> None:
        self._ensure_subscription()

        now = time.time()
        if now < self._next_run_ts:
            return

        self._next_run_ts = now + self.poll_interval_sec
        self._write_snapshot()

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _ensure_subscription(self) -> None:
        if self._ticker is not None:
            return

        contract = Stock("TSLA", "SMART", "USD")
        self._ticker = self.ib.reqMktData(contract, "", False, False)
        logging.info("TSLA: Subscribed to realtime market data for TSLA")

    def _write_snapshot(self) -> None:
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

            # --------------------------
            # Key change: use writer
            # --------------------------
            self.writer.write({
                "ts_utc": ts,
                "bid": bid,
                "ask": ask,
                "last": last,
                "volume": volume,
            })

            logging.info(
                "TSLA: Snapshot ts=%s bid=%.2f ask=%.2f last=%.2f vol=%d",
                ts, bid, ask, last, volume
            )

        except Exception as e:
            logging.error("TSLA: Ingestion error: %s", e, exc_info=True)

