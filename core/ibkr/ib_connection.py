import logging
import threading
import time
from ib_insync import IB


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

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def start(self):
        logging.info("[IB] Starting core IB connection...")

        self._connect_blocking()
        self._hb_thread.start()
        self._main_loop()  # Event loop lives in main thread

    def stop(self):
        logging.info("[IB] Stopping IB connection...")
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
            logging.info(f"[IB] Connecting to {self.host}:{self.port} (clientId={self.client_id})")
            self.ib.connect(self.host, self.port, clientId=self.client_id)

            if self.ib.isConnected():
                self.connected = True
                logging.info("[IB] Connected successfully.")
            else:
                raise RuntimeError("IB connection returned false")

        except Exception as e:
            logging.error(f"[IB] Connection failed: {e}")
            self.connected = False

    def _attempt_reconnect(self):
        self._schedule_reconnect = True

    # ---------------------------------------------------------
    # Heartbeat Thread (cannot call API)
    # ---------------------------------------------------------
    def _heartbeat_loop(self):
        logging.info("[IB] Heartbeat thread started.")
        while not self._stop:
            try:
                if not self.ib.isConnected():
                    logging.warning("[IB] Heartbeat detected disconnect.")
                    self._attempt_reconnect()
                else:
                    logging.debug("[IB] Heartbeat OK.")
            except Exception as e:
                logging.error(f"[IB] Heartbeat exception: {e}")
                self._attempt_reconnect()

            time.sleep(5)

    # ---------------------------------------------------------
    # Main Thread Loop (must run IB event loop)
    # ---------------------------------------------------------
    def _main_loop(self):
        logging.info("[IB] Entering main event loop.")

        while not self._stop:
            # Handle scheduled reconnect
            if self._schedule_reconnect:
                self._schedule_reconnect = False
                logging.info("[IB] Reconnecting...")

                try:
                    self.ib.disconnect()
                except Exception:
                    pass

                time.sleep(1)
                self._connect_blocking()

            # ---- SAFE EVENT LOOP ----
            try:
                self.ib.sleep(1)

            except ConnectionError as e:
                logging.error(f"[IB] Socket disconnect: {e}")
                self.connected = False
                self._attempt_reconnect()

            except Exception as e:
                logging.error(f"[IB] Unexpected main-loop exception: {e}")
                self.connected = False
                self._attempt_reconnect()

