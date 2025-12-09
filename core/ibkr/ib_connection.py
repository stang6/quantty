#core/ibkr/ib_connection.py
import threading
import time
import signal
import logging
from ib_insync import IB
from core.logging.logger import get_logger

# set ib_insync as DEBUG level
logging.getLogger('ib_insync').setLevel(logging.DEBUG)

logger = get_logger("IB")


class IBConnection:
    def __init__(self, host="127.0.0.1", port=4002, client_id=1):
        self.host = host
        self.port = port
        self.client_id = client_id

        self.ib = IB()
        self.connected = False

        # Flags
        self._stop = False
        self._schedule_reconnect = False

        # Heartbeat thread
        self._hb_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )

        # Optional hook executed on every main loop iteration
        self._loop_hook = None

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def start(self, loop_hook=None):
        """
        Start IB connection and main event loop.
        """
        self._loop_hook = loop_hook
        logger.info("[IB] Starting core IB connection...")

        # Register OS shutdown signals
        self._register_signal_handlers()

        # Connect synchronously
        #self._connect_blocking() --> move to main.py
        if not self.ib.isConnected():
            logger.error("[IB] Start called without an established connection. Exiting.")
            return

        # Start heartbeat monitor
        self._hb_thread.start()

        # Run event loop in main thread
        self._main_loop()

    def stop(self):
        """
        Gracefully shut down IB connection and all threads.
        """
        logger.info("[IB] Shutting down gracefully...")
        self._stop = True

        try:
            self.ib.disconnect()
        except Exception:
            pass

        logger.info("[IB] Shutdown complete.")

    # ---------------------------------------------------------
    # Signal handling
    # ---------------------------------------------------------
    def _register_signal_handlers(self):
        """
        Capture Ctrl+C (SIGINT) and system shutdown (SIGTERM).
        """
        def handler(signum, frame):
            logger.info(f"[IB] Signal {signum} received — triggering shutdown")
            self.stop()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    # ---------------------------------------------------------
    # Internal logic: connect + reconnect
    # ---------------------------------------------------------
    #def _connect_blocking(self):
    def connect_blocking(self):
        try:
            logger.info(f"[IB] Connecting to {self.host}:{self.port} (clientId={self.client_id})")
            self.ib.connect(self.host, self.port, clientId=self.client_id)

            if self.ib.isConnected():
                self.connected = True
                logger.info("[IB] Connected successfully.")
            else:
                raise RuntimeError("IB connection returned false")

        except Exception as e:
            logger.error(f"[IB] Connection failed: {e}")
            self.connected = False

    def _attempt_reconnect(self):
        self._schedule_reconnect = True

    # ---------------------------------------------------------
    # Heartbeat Thread
    # ---------------------------------------------------------
    def _heartbeat_loop(self):
        logger.info("[IB] Heartbeat thread started.")
        while not self._stop:
            try:
                if not self.ib.isConnected():
                    logger.warning("[IB] Heartbeat detected disconnect.")
                    self._attempt_reconnect()
            except Exception as e:
                logger.error(f"[IB] Heartbeat exception: {e}")
                self._attempt_reconnect()

            time.sleep(5)

        logger.info("[IB] Heartbeat thread exit.")

    # ---------------------------------------------------------
    # Main event loop
    # ---------------------------------------------------------
    def _main_loop(self):
        logger.info("[IB] Entering main event loop.")

        while not self._stop:
            # Reconnect handling
            if self._schedule_reconnect:
                self._schedule_reconnect = False
                logger.info("[IB] Reconnecting...")

                try:
                    self.ib.disconnect()
                except Exception:
                    pass

                time.sleep(1)
                self._connect_blocking()

            # User-defined hook (ingestors / strategies)
            if self._loop_hook:
                try:
                    self._loop_hook()
                except Exception as e:
                    logger.error("[IB] Loop hook error: %s", e, exc_info=True)

            # Required for IB API event loop
            try:
                self.ib.sleep(1)
            except Exception as e:
                logger.error("[IB] Main-loop exception: %s", e)
                self.connected = False
                self._attempt_reconnect()

        logger.info("[IB] Main loop exit.")

