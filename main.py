# main.py
import os
import time
from pathlib import Path

from core.ibkr.ib_connection import IBConnection
from core.data.tsla_ingestion import TslaIngestion
from core.data.aapl_ingestion import AaplIngestion
from core.data.historical_ingestion import run_blocking_ingestion
from core.monitor.dashboard import Dashboard
from core.config.loader import Config
from core.logging.logger import get_logger

logger = get_logger("MAIN")


# ---------------------------------------------------------
# Helper: Ensure required directories exist
# ---------------------------------------------------------
def ensure_directories():
    required_dirs = ["data", "logs", "historical_data"] 
    for d in required_dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info(f"[MAIN] Ensured required directories: {required_dirs}")


# ---------------------------------------------------------
# Main Launcher
# ---------------------------------------------------------
def main():
    logger.info("=== Starting Quantty MVP Launcher ===")

    # ensure folders exist
    ensure_directories()

    # ------------------------------------
    # Load configuration
    # ------------------------------------
    cfg = Config.load()
    logger.info("[MAIN] Loaded config from config/config.yaml")

    host = cfg["ib"]["host"]
    port = cfg["ib"]["port"]
    client_id = cfg["ib"]["client_id"]

    # Config Ingestion and Realtime
    poll_interval = cfg["ingestion"]["poll_interval"]
    symbols = cfg["ingestion"]["symbols"]
    output_dir = cfg["ingestion"]["output_dir"]
    
    # Config Historical Data
    hist_cfg = cfg["historical_data"]

    # shared registry for dashboard
    snapshot_registry = {}

    # dashboard
    dashboard = Dashboard(snapshot_registry, refresh_sec=1)
    logger.info("[MAIN] Dashboard initialized.")

    # IB connection
    ib_conn = IBConnection(host=host, port=port, client_id=client_id)
    logger.info("[MAIN] IB connection object created.")

    # ------------------------------------
    # ib connect manually
    # ------------------------------------
    logger.info("[MAIN] Attempting initial connection (BLOCKING)...")
    
    ib_conn.connect_blocking()

    if not ib_conn.ib.isConnected():
        logger.error("[MAIN] Fatal error: Could not establish initial IB connection. Exiting.")
        return # quit if failed to connect
    
    # ------------------------------------
    # Blocking Initialization For Historical Data
    # ------------------------------------
    logger.info("=== BLOCKING INIT: Starting Historical Data Check & Download ===")
    
    # Block before all data being downloaded
    for sym in symbols:
        # 4. send IB instance and hist_cfg to the blocking function
        success = run_blocking_ingestion(ib_conn.ib, sym, hist_cfg) 
        if not success:
            logger.error(f"[MAIN] Fatal error: Failed to download historical data for {sym}. Exiting.")
            # quit safely if failed to download
            ib_conn.stop() 
            return 
    
    logger.info("=== BLOCKING INIT COMPLETE. Proceeding to Realtime Loop. ===")
    # ------------------------------------

    # ------------------------------------
    # Build ingestion pipeline (Realtime)
    # ------------------------------------
    ingestors = []

    for sym in symbols:
        out_path = f"{output_dir}/{sym.lower()}_realtime_ticks.csv"

        if sym == "TSLA":
            ing = TslaIngestion(
                ib=ib_conn.ib,
                poll_interval_sec=poll_interval,
                output_path=out_path,
                snapshot_registry=snapshot_registry,
            )
        elif sym == "AAPL":
            ing = AaplIngestion(
                ib=ib_conn.ib,
                poll_interval_sec=poll_interval,
                output_path=out_path,
                snapshot_registry=snapshot_registry,
            )
        else:
            logger.warning(f"[MAIN] Unsupported symbol '{sym}', skipped.")
            continue

        ingestors.append(ing)

    logger.info(f"[MAIN] Ingestors initialized for: {symbols}")

    # ------------------------------------
    # Main Loop Hook
    # ------------------------------------
    def combined_loop():
        for ing in ingestors:
            ing.run_step()

        # render dashboard
        dashboard.render_once()

    # ------------------------------------
    # Start IB loop
    # ------------------------------------
    try:
        logger.info("[MAIN] Launching IB event loop...")
        # start to normal IB loop (non-blocking)
        ib_conn.start(loop_hook=combined_loop)

    finally:
        logger.info("[MAIN] Cleanup before exit...")
        ib_conn.stop()
        logger.info("[MAIN] Shutdown complete.")
        logger.info("=== Quantty MVP Exit ===")


if __name__ == "__main__":
    main()
