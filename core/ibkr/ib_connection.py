import threading
import time
from ib_insync import IB
from core.logging.logger import get_logger
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
        self._loop_hook = loop_hook
        logger.info("[IB] Starting core IB connection...")

        self._connect_blocking()
        self._hb_thread.start()

        # Must run event loop in main thread
        self._main_loop()  # Event loop lives in main thread

    def stop(self):
        logger.info("[IB] Stopping IB connection...")
        self._stop = True
        try:
            self.ib.disconnect()
        except Exception:
            pass

    # ---------------------------------------------------------
    # Internal logic: connect + reconnect
    # ---------------------------------------------------------
    def _connect_blocking(self):
        """Synchronously connect in the main thread."""
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
    # Heartbeat Thread (cannot call API)
    # ---------------------------------------------------------
    def _heartbeat_loop(self):
        logger.info("[IB] Heartbeat thread started.")
        while not self._stop:
            try:
                if not self.ib.isConnected():
                    logger.warning("[IB] Heartbeat detected disconnect.")
                    self._attempt_reconnect()
                else:
                    logger.debug("[IB] Heartbeat OK.")
            except Exception as e:
                logger.error(f"[IB] Heartbeat exception: {e}")
                self._attempt_reconnect()

            time.sleep(5)

    # ---------------------------------------------------------
    # Main Thread Loop (must run IB event loop)
    # ---------------------------------------------------------
    def _main_loop(self):
        logger.info("[IB] Entering main event loop.")

        while not self._stop:
            # Handle scheduled reconnect
            if self._schedule_reconnect:
                self._schedule_reconnect = False
                logger.info("[IB] Reconnecting...")

                try:
                    self.ib.disconnect()
                except Exception:
                    pass

                time.sleep(1)
                self._connect_blocking()

            # User-defined hook (for example TSLA ingestion)
            if self._loop_hook:
                try:
                    self._loop_hook()
                except Exception as e:
                    logger.error("[IB] Loop hook error: %s", e, exc_info=True)

            # Required to pump IB API events
            try:
                self.ib.sleep(1)

            except Exception as e:
                logger.error("[IB] Main-loop connection exception: %s", e)
                self.connected = False
                self._attempt_reconnect()

