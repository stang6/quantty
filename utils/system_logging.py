import logging
import logging.handlers
import sys # 引入 sys 模組

def setup_logging(log_filename='trading_system.log', error_filename='error.log'):
    """Sets up dual-file logging for the trading system and console output."""

    # 1. Base Configuration (不設定 level，讓處理器決定)
    # 設置根記錄器的最低捕獲級別為 DEBUG，確保所有資訊都能被處理器捕獲
    logging.getLogger('').setLevel(logging.INFO) 

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    # 2. Add Console Handler (Streaming to journalctl)
    # 新增一個 StreamHandler，將所有 INFO 級別的日誌輸出到 stdout/stderr
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG) # 讓 INFO/WARNING 等級的訊息能在 journalctl 中看到
    console_handler.setFormatter(formatter)
    logging.getLogger('').addHandler(console_handler)

    # 3. Add Info/Warning Handler (Main Log File)
    info_handler = logging.handlers.RotatingFileHandler(
        log_filename, maxBytes=10*1024*1024, backupCount=5
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    logging.getLogger('').addHandler(info_handler)

    # 4. Add Error Handler (Urgent Review File)
    error_handler = logging.FileHandler(error_filename)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logging.getLogger('').addHandler(error_handler)
    
    # 注意：我們已經在 main.py 中設定了 ib.util.logToConsole(logging.DEBUG)，
    # 這裡的 console_handler 將會處理您應用程式的日誌。

    logging.info("System Logging Initialized (Console Enabled).")
