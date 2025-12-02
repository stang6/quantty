# main.py
import logging
from core.ibkr.ib_connection import IBConnection
from core.data.tsla_ingestion import TslaIngestion
from core.data.aapl_ingestion import AaplIngestion


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def main() -> None:
    # Create IB connection wrapper
    ib_conn = IBConnection(host="127.0.0.1", port=4002, client_id=1)

    # Create TSLA ingestion (subscription will be created on first run_step)
    tsla_ingestor = TslaIngestion(
        ib=ib_conn.ib,
        poll_interval_sec=5,
        output_path="data/tsla_realtime_ticks.csv",
    )

    aapl_ingestor = AaplIngestion(
        ib=ib_conn.ib,
        poll_interval_sec=5,
        output_path="data/aapl_realtime_ticks.csv",
    )

    # Start IB connection and pass run_step as the loop hook
    #ib_conn.start(loop_hook=tsla_ingestor.run_step)

    # multiple symbols
    def combined_loop():
        tsla_ingestor.run_step()
        aapl_ingestor.run_step()

    ib_conn.start(loop_hook=combined_loop)


if __name__ == "__main__":
    main()

