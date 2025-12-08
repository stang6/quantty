# core/monitor/dashboard.py
import os
import time
from datetime import datetime

from core.logging.logger import get_logger

logger = get_logger("DASHBOARD")


class Dashboard:
    """
    Terminal dashboard showing realtime snapshots for all symbols.
    Does NOT flicker. Uses ANSI cursor save/restore and fixed widths.
    """

    def __init__(self, snapshot_registry, refresh_sec=1):
        self.snapshot_registry = snapshot_registry
        self.refresh_sec = refresh_sec

        # fixed column width design
        self.columns = [
            ("Symbol", 8),
            ("Bid", 10),
            ("Ask", 10),
            ("Last", 10),
            ("Volume", 12),
            ("Updated (UTC)", 24),
        ]

        # state tracking
        self._initialized = False

    # -------------------------------
    # ANSI helpers
    # -------------------------------
    def _clear_screen(self):
        print("\033[2J\033[H", end="")  # clear + home

    def _move_cursor_top(self):
        print("\033[H", end="")  # move to top-left

    # -------------------------------
    # Rendering helpers
    # -------------------------------
    def _render_header(self):
        row = ""
        for name, width in self.columns:
            row += name.ljust(width)
        print(row)
        print("-" * sum(w for _, w in self.columns))

    def _render_row(self, symbol, snap):
        """
        snap = {
            "bid": float,
            "ask": float,
            "last": float,
            "volume": int,
            "ts": "2025-12-05T..."
        }
        """
        if snap is None:
            # not ready
            print(
                symbol.ljust(8)
                + "n/a".ljust(10)
                + "n/a".ljust(10)
                + "n/a".ljust(10)
                + "n/a".ljust(12)
                + "-".ljust(24)
            )
            return

        bid = f"{snap['bid']:.2f}"
        ask = f"{snap['ask']:.2f}"
        last = f"{snap['last']:.2f}"
        vol = str(snap["volume"])
        ts = snap["ts"]

        row = (
            symbol.ljust(8)
            + bid.ljust(10)
            + ask.ljust(10)
            + last.ljust(10)
            + vol.ljust(12)
            + ts.ljust(24)
        )
        print(row)

    # -------------------------------
    # Public API
    # -------------------------------
    def render_once(self):
        """
        Called by main loop every refresh_sec seconds.
        """
        if not self._initialized:
            self._clear_screen()
            self._initialized = True
        else:
            self._move_cursor_top()

        print("QUANTTY — REALTIME DASHBOARD")
        print(f"Last update: {datetime.utcnow().isoformat()}\n")

        # header
        self._render_header()

        # body
        for symbol, snap in self.snapshot_registry.items():
            self._render_row(symbol, snap)

        print("\n(Press Ctrl+C to stop)")


