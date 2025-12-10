# main.py
import os
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Set, List

# Core IBKR and Data Modules
from core.ibkr.ib_connection import IBConnection
from core.data.realtime_ingestion import RealtimeIngestion
from core.data.historical_ingestion import run_blocking_ingestion

# Strategy and Scanning Modules (NEW/MODIFIED IMPORTS)
from core.strategy.stage_analyzer import StageAnalyzer # Still needed for completeness
from core.scanner.market_scanner import MarketScanner # NEW: Scanner
# Placeholder for strategies (Will be initialized later)
from core.strategy.stage2_breakdown_strategy import Stage2BreakdownStrategy 

# Monitoring and Config
from core.monitor.dashboard import Dashboard
from core.config.loader import Config
from core.logging.logger import get_logger

logger = get_logger("MAIN")


# ---------------------------------------------------------
# Helper: Ensure required directories exist
# ---------------------------------------------------------
def ensure_directories():
    """Ensures required data and log directories are present."""
    required_dirs = ["data", "logs", "historical_data"]
    for d in required_dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info(f"[MAIN] Ensured required directories: {required_dirs}")


# ---------------------------------------------------------
# Helper: Allocates symbols to active strategies
# ---------------------------------------------------------
def allocate_symbols_to_strategies(cfg: Dict[str, Any], candidates: Dict[str, Dict]) -> Tuple[Dict[str, List[str]], Set[str]]:
    """
    Filters the market scan candidates and allocates symbols to active strategies
    based on their required market stage.
    
    Args:
        cfg: The main configuration dictionary.
        candidates: Dictionary of symbols and their StageAnalysis summaries (passed hygiene/liquidity).
        
    Returns:
        A tuple: (allocation_map, unique_symbols_to_monitor)
    """
    strategy_allocations: Dict[str, List[str]] = {}
    symbols_to_monitor: Set[str] = set()
    
    strategies_cfg = cfg.get('portfolio', {}).get('strategies', {})

    for name, s_cfg in strategies_cfg.items():
        if not s_cfg.get('enabled'):
            logger.info(f"[ALLOC] Strategy {name} is disabled.")
            continue
            
        required_stages = []
        
        # StanStrategy: Long-term trend positions (Stage 1 for breakout, Stage 2 for holding)
        if name == "StanStrategy":
            required_stages = ["STAGE 1", "STAGE 2"]
        # FujimotoStrategy: Short-term swing trading, typically within a strong uptrend
        elif name == "FujimotoStrategy":
            required_stages = ["STAGE 2"]
        else:
            logger.warning(f"[ALLOC] Unknown strategy name: {name}. Skipping allocation.")
            continue

        
        allocated_symbols = []
        for symbol, summary in candidates.items():
            current_stage = summary['current_stage']
            
            # Check if the symbol's stage matches the strategy's requirement
            if any(stage_prefix in current_stage for stage_prefix in required_stages):
                allocated_symbols.append(symbol)
                symbols_to_monitor.add(symbol)
        
        strategy_allocations[name] = allocated_symbols
        logger.info(f"[ALLOC] {name} allocated {len(allocated_symbols)} symbol(s). Required stages: {required_stages}")

    return strategy_allocations, symbols_to_monitor


# ---------------------------------------------------------
# Main Launcher
# ---------------------------------------------------------
def main():
    logger.info("=== Starting Quantty Launcher (Multi-Strategy Mode) ===")

    # 1. Ensure folders exist
    ensure_directories()

    # 2. Load configuration
    cfg = Config.load()
    logger.info("[MAIN] Loaded config from config/config.yaml")

    host = cfg["ib"]["host"]
    port = cfg["ib"]["port"]
    client_id = cfg["ib"]["client_id"]
    poll_interval = cfg["ingestion"]["poll_interval"]
    
    # 3. Establish IB Connection
    conn = IBConnection(host, port, client_id)

    # 4. Run Market Scan and Allocation
    
    # NOTE: Before scanning, you should run data ingestion 
    # to ensure all symbols in the universe have up-to-date historical data.
    # We will assume historical data download is handled separately or is currently skipped
    # for this architectural step. (run_blocking_ingestion is commented out for now)
    # run_blocking_ingestion(conn, cfg) 
    
    scanner = MarketScanner()
    # passed_candidates: Dict[symbol: summary]
    passed_candidates = scanner.scan_market() 
    
    # 5. Filter the candidates and allocate symbols to strategies
    strategy_allocations, symbols_to_monitor = allocate_symbols_to_strategies(cfg, passed_candidates)
    
    if not symbols_to_monitor:
        logger.critical("[MAIN] No symbols passed the market scan and allocation process. Shutting down.")
        conn.disconnect()
        return
        
    # 6. Initialize Realtime Ingestion and Dashboard
    dashboard = Dashboard()
    
    # Initialize Realtime Ingestion with the combined list of symbols to monitor
    ingestion = RealtimeIngestion(
        conn=conn,
        symbols=list(symbols_to_monitor), # Pass the final unique list of symbols for monitoring
        poll_interval=poll_interval,
        dashboard=dashboard,
        # Placeholder: Pass the allocation map to RealtimeIngestion for strategy execution later
        strategy_allocations=strategy_allocations 
    )

    # 7. Start the main loop
    try:
        ingestion.start_loop()
        
    except KeyboardInterrupt:
        logger.info("[MAIN] Shutting down Quantty via KeyboardInterrupt.")
    finally:
        conn.disconnect()
        logger.info("[MAIN] Disconnected from IB Gateway/TWS.")


if __name__ == "__main__":
    main()
