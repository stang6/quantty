# core/config/scan_loader.py (FINAL MODIFIED VERSION)
import yaml
import requests # NEW DEPENDENCY
from typing import Dict, Any, List
import logging
from pathlib import Path

# Use the core logging system
logger = logging.getLogger("MAIN")

class ScanConfig:
    """
    Loads and provides access to the market scan universe and filter criteria
    from config/scan_universe.yaml.
    Includes logic to expand the 'ALL' keyword by downloading the full NASDAQ list.
    """
    FILE_PATH = "config/scan_universe.yaml"
    # The official NASDAQ listed symbols source provided by the user
    NASDAQ_UNIVERSE_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt" 

    @classmethod
    def _load_full_universe(cls) -> List[str]:
        """
        Loads the comprehensive list of NASDAQ symbols by downloading the official file,
        parsing it, and cleaning the list.
        """
        logger.info(f"Downloading full NASDAQ symbol list from {cls.NASDAQ_UNIVERSE_URL}...")
        try:
            response = requests.get(cls.NASDAQ_UNIVERSE_URL, timeout=10)
            response.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)

            symbols = []
            
            # The file is pipe-separated (|) and the first line is the header
            lines = response.text.splitlines()
            
            # Start from index 1 to skip the header row
            for line in lines[1:]: 
                # Lines usually look like: 'A|Active|...' or end with 'FileCreationTime'
                parts = line.split('|')
                
                # We only need the first part (the symbol)
                if len(parts) > 1 and parts[0] != 'FileCreationTime':
                    symbol = parts[0].strip().upper()
                    
                    # Basic hygiene: Ignore symbols that contain a slash or dash, 
                    # as these are often options chains or non-standard contracts.
                    if '/' not in symbol and '-' not in symbol:
                        symbols.append(symbol)

            logger.info(f"Successfully loaded and cleaned {len(symbols)} symbols from NASDAQ.")
            return symbols
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading NASDAQ universe list from URL: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing downloaded NASDAQ universe data: {e}")
            return []


    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Loads the scanning configuration file and processes the symbols list."""
        file = Path(cls.FILE_PATH)
        if not file.exists():
            logger.critical(f"Scan configuration file not found: {cls.FILE_PATH}. Please create it.")
            return {"symbols": [], "filters": {}}

        try:
            with open(file, 'r', encoding='utf-8') as f:
                scan_cfg = yaml.safe_load(f)
            
            logger.info(f"[MAIN] Loaded scan universe and filters from {cls.FILE_PATH}.")
            
            # Simple validation and symbol extraction
            if not isinstance(scan_cfg, dict) or 'symbols' not in scan_cfg or 'filters' not in scan_cfg:
                 logger.error(f"Scan configuration format error in {cls.FILE_PATH}. Missing 'symbols' or 'filters' section.")
                 return {"symbols": [], "filters": {}}

            # --- Symbol Expansion Logic ---
            symbols_from_config = [s.strip().upper() for s in scan_cfg.get('symbols', [])]
            
            if 'ALL' in symbols_from_config:
                # If 'ALL' is present, load the full list dynamically
                full_symbols = cls._load_full_universe()
                scan_cfg['symbols'] = full_symbols
                logger.warning("--- USING FULL UNIVERSE (ALL KEYWORD) ---")
            else:
                # If 'ALL' is not present, use the list provided in the config
                scan_cfg['symbols'] = symbols_from_config
            
            return scan_cfg
        
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML in {cls.FILE_PATH}: {e}")
            return {"symbols": [], "filters": {}}
