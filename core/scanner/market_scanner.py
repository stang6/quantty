# core/scanner/market_scanner.py
import logging
from typing import Dict, Any, List
from core.config.scan_loader import ScanConfig
from core.strategy.stage_analyzer import StageAnalyzer

# Use the core logging system
logger = logging.getLogger("MAIN")

class MarketScanner:
    """
    The MarketScanner orchestrates the filtering and analysis process.
    It loads the universe and filters from scan_universe.yaml and
    applies the hygiene, liquidity, and Stan Weinstein stage analysis criteria.
    """

    def __init__(self):
        # Load the scan configuration (universe list and filter thresholds)
        self.scan_cfg = ScanConfig.load()
        self.filters = self.scan_cfg.get('filters', {})
        self.universe = self.scan_cfg.get('symbols', [])
        
        # Check if the universe is empty after loading (e.g., if 'ALL' failed to load the list)
        if not self.universe:
            logger.critical("The scanning universe is empty. Check config/scan_universe.yaml or NASDAQ_UNIVERSE_URL.")

        logger.info(f"MarketScanner initialized. Universe size: {len(self.universe)}. Filters loaded.")

    def _apply_hygiene_and_liquidity_filters(self, summary: Dict) -> bool:
        """
        Applies static filters based on price, data points, and average volume.
        
        Args:
            summary: The analysis summary dictionary from StageAnalyzer.
            
        Returns:
            True if the stock passes all hygiene and liquidity checks, False otherwise.
        """
        symbol = summary.get('symbol', 'N/A')

        # Check 1: Data Integrity
        min_data_points = self.filters.get('min_data_points', 82)
        if summary.get('data_points', 0) < min_data_points:
            logger.debug(f"[{symbol}] Failed Check 1: Data points ({summary['data_points']}) < {min_data_points}.")
            return False

        # Check 2: Minimum Price Filter (excludes penny stocks)
        min_price = self.filters.get('min_price', 5.0)
        if summary.get('last_close', 0.0) < min_price:
            logger.debug(f"[{symbol}] Failed Check 2: Price ({summary['last_close']}) < {min_price}.")
            return False
        
        # Check 3: Minimum Average Weekly Volume (liquidity filter)
        min_volume = self.filters.get('min_avg_weekly_volume', 500000)
        if summary.get('avg_volume', 0.0) < min_volume:
            logger.debug(f"[{symbol}] Failed Check 3: Volume ({summary['avg_volume']:.0f}) < {min_volume}.")
            return False
            
        return True

    def scan_market(self) -> Dict[str, Dict]:
        """
        Executes the full market scan, applying all filters and returning a summary
        of only the passing candidates.
        
        Returns:
            A dictionary where keys are passing symbols and values are their StageAnalysis summaries.
        """
        passed_candidates: Dict[str, Dict] = {}
        total_symbols = len(self.universe)
        
        logger.info(f"--- STARTING MARKET SCAN on {total_symbols} symbols ---")
        
        for i, symbol in enumerate(self.universe):
            # Skip empty or malformed symbols
            if not symbol or not isinstance(symbol, str):
                continue
                
            # 1. Stage Analysis and Data Collection
            analyzer = StageAnalyzer(symbol)
            summary = analyzer.get_analysis_summary()
            
            # Skip if there was a data loading error
            if summary.get('error'):
                logger.warning(f"[{symbol}] Skipping due to data error: {summary.get('message', 'N/A')}")
                continue

            # 2. Apply Hygiene and Liquidity Filters
            if self._apply_hygiene_and_liquidity_filters(summary):
                
                # 3. Stage 2 (Uptrend) and Stage 1 (Accumulation) automatically pass the scan.
                # Stage 3/4 stocks are filtered out implicitly by not being added to the list.
                # However, we only need to return the analysis summary for allocation in main.py
                
                if "STAGE 2" in summary['current_stage'] or "STAGE 1" in summary['current_stage']:
                    passed_candidates[symbol] = summary
                    logger.debug(f"[{symbol}] Passed scan. Stage: {summary['current_stage']}")
                else:
                    logger.debug(f"[{symbol}] Failed Check 4: Stage is {summary['current_stage']}")


        logger.info(f"--- SCAN COMPLETE. {len(passed_candidates)} candidate(s) passed all filters. ---")
        return passed_candidates
