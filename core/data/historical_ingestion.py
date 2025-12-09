import os
import logging
from typing import Dict
from ib_insync import IB, Stock, util
from core.logging.logger import get_logger

logger = get_logger("HISTRX") # Historical Data Receiver

def run_blocking_ingestion(ib: IB, symbol: str, hist_cfg: Dict) -> bool:
    """
    Execute a blocking historical data request for Stage Analysis (Weekly Bars).
    This function will BLOCK the main thread until data is received or connection fails.
    """
    
    # 1. Define Contract and File Path
    contract = Stock(symbol, "SMART", "USD")
    
    # file name configuration
    filename = f"{symbol}_{hist_cfg['bar_size'].replace(' ', '')}_{hist_cfg['duration'].replace(' ', '')}.csv"
    file_path = f"historical_data/{filename}"
    
    # Check if data already exists to avoid redundant requests
    if os.path.exists(file_path):
        logger.info(f"[{symbol}] Historical data cache found at {file_path}. Skipping request.")
        return True

    # read configs
    duration = hist_cfg['duration']
    bar_size = hist_cfg['bar_size']
    what_to_show = hist_cfg['what_to_show']
    use_rth = hist_cfg['use_rth']
    
    logger.info(f"[{symbol}] Requesting {duration} {bar_size} historical data (BLOCKING)...")

    # 2. Qualify Contract and Request Data
    try:
        ib.qualifyContracts(contract) 
        
        # BLOCKING call
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=use_rth,
            formatDate=1
        )
        
    except Exception as e:
        logger.error(f"[{symbol}] Historical data request FAILED: {e}", exc_info=True)
        return False

    # 3. Process and Save
    if bars:
        logger.info(f"[{symbol}] Received {len(bars)} weekly bars. Saving to CSV.")
        df = util.df(bars)
        df.columns = [c.lower() for c in df.columns]
        
        df.to_csv(file_path, index=False)
        return True
    else:
        logger.warning(f"[{symbol}] Received 0 bars. Check symbol or IB permission.")
        return False
