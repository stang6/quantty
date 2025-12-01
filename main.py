# main.py
import logging
from core.ibkr.ib_connection import IBConnection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def main():
    ib = IBConnection(host="127.0.0.1", port=4002, client_id=1)
    ib.start()

if __name__ == "__main__":
    main()

