# main.py
import time
from core.ibkr.ib_connection import IBConnection
from core.data.tsla_ingestion import TslaIngestion
from core.data.aapl_ingestion import AaplIngestion
from core.config.loader import Config
from core.logging.logger import get_logger

logger = get_logger("main")


def main() -> None:
    # ------------------------------------
    # Load configuration
    # ------------------------------------
    cfg = Config.load()

    host = cfg["ib"]["host"]
    port = cfg["ib"]["port"]
    client_id = cfg["ib"]["client_id"]

    poll_interval = cfg["ingestion"]["poll_interval"]
    symbols = cfg["ingestion"]["symbols"]
    output_dir = cfg["ingestion"]["output_dir"]

    # ------------------------------------
    # Start IB connection
    # ------------------------------------
    ib_conn = IBConnection(host=host, port=port, client_id=client_id)

    # ------------------------------------
    # Dynamically create ingestion objects
    # ------------------------------------
    ingestors = []

    for sym in symbols:
        if sym == "TSLA":
            ingestors.append(
                TslaIngestion(
                    ib=ib_conn.ib,
                    poll_interval_sec=poll_interval,
                    output_path=f"{output_dir}/tsla_realtime_ticks.csv",
                )
            )
        elif sym == "AAPL":
            ingestors.append(
                AaplIngestion(
                    ib=ib_conn.ib,
                    poll_interval_sec=poll_interval,
                    output_path=f"{output_dir}/aapl_realtime_ticks.csv",
                )
            )
        else:
            logger.warning(f"Symbol '{sym}' not supported in main.py")

    # ------------------------------------
    # Combined loop (executed every ~1 sec)
    # ------------------------------------
    def combined_loop():
        for ing in ingestors:
            ing.run_step()

    # ------------------------------------
    # Run IB event loop
    # ------------------------------------
    try:
        ib_conn.start(loop_hook=combined_loop)
    finally:
        logger.info("[MAIN] Cleanup before exit...")
        ib_conn.stop()
        logger.info("[MAIN] Shutdown complete.")


if __name__ == "__main__":
    main()

