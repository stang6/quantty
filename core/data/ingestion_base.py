# core/data/ingestion_base.py
import time
import logging
from abc import ABC, abstractmethod


class IngestionBase(ABC):
    """
    Abstract base class for all ingestion modules.
    Every ingestion must implement:
    - ensure_subscription()
    - write_snapshot()
    """

    def __init__(self, poll_interval_sec: int = 5, wma_price: float = 0.0):
        self.poll_interval_sec = poll_interval_sec
        self._next_run_ts = time.time()
        self.wma_price = wma_price

    def run_step(self) -> None:
        """
        Called every ~1s by IBConnection.
        Handles:
        - subscription setup
        - timed snapshot collection
        """
        self.ensure_subscription()

        now = time.time()
        if now < self._next_run_ts:
            return

        self._next_run_ts = now + self.poll_interval_sec
        self.write_snapshot()

    # Must implement
    @abstractmethod
    def ensure_subscription(self) -> None:
        pass

    @abstractmethod
    def write_snapshot(self) -> None:
        pass

