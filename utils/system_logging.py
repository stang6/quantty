import logging
import logging.handlers

def setup_logging(log_filename='trading_system.log', error_filename='error.log'):
    """Sets up dual-file logging for the trading system."""
    
    # 1. Base Configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(module)s - %(message)s'
    )
    
    # 2. Add Info/Warning Handler (Main Log)
    info_handler = logging.handlers.RotatingFileHandler(
        log_filename, maxBytes=10*1024*1024, backupCount=5
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s'))
    logging.getLogger('').addHandler(info_handler)
    
    # 3. Add Error Handler (Urgent Review)
    error_handler = logging.FileHandler(error_filename)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s'))
    logging.getLogger('').addHandler(error_handler)
    
    logging.info("System Logging Initialized.")
