# core/strategy/stage_analyzer.py
import pandas as pd
import os
import logging
from typing import Dict, Any
from core.logging.logger import get_logger

# Constants
WMA_PERIOD = 30
FILE_PATH_TEMPLATE = "historical_data/{symbol}_1week_3Y.csv"

logger = get_logger("STGANA") # Stage Analyzer

class StageAnalyzer:
    """
    Implements Stan Weinstein's Stage Analysis logic.
    Calculates the 30-Week Moving Average (30-WMA) and determines the current stage.
    """
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.data: pd.DataFrame = self._load_data()
        self.wma_period = WMA_PERIOD
        # Initialize instance attributes
        self.current_stage = "UNKNOWN"
        self.wma_slope_trend = "UNKNOWN"
        self.current_wma = None
        
        # Attribute to store detailed analysis (used for transition check)
        self.stage_history: Dict[str, Any] = {"recent_stages": []} 

        if not self.data.empty:
            self._calculate_wma()
            self._analyze_stage()

    def _load_data(self) -> pd.DataFrame:
        """Loads historical weekly data from CSV."""
        file_path = FILE_PATH_TEMPLATE.format(symbol=self.symbol)
        if not os.path.exists(file_path):
            logger.error(f"[{self.symbol}] Historical data file not found at {file_path}")
            return pd.DataFrame()

        try:
            # Ensure 'date' is parsed as datetime and set as index
            df = pd.read_csv(file_path, index_col='date', parse_dates=True)
            # Sort to ensure chronological order for MA calculation
            df.sort_index(inplace=True)
            logger.info(f"[{self.symbol}] Loaded {len(df)} weekly bars for Stage Analysis.")
            # Only use OHLCV columns for analysis
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            logger.error(f"[{self.symbol}] Failed to load or parse data: {e}", exc_info=True)
            return pd.DataFrame()

    def _calculate_wma(self):
        """Calculates the 30-Week Simple Moving Average (30-WMA) and its slope."""
        # Calculate 30-Week Simple Moving Average
        self.data['wma'] = self.data['close'].rolling(window=self.wma_period).mean()

        # Calculate WMA Slope: Change over the last 3 bars
        ma_series = self.data['wma'].dropna()
        if len(ma_series) >= 3:
            # Use a 3-bar difference for the slope calculation
            recent_wma = ma_series.tail(3)
            # Slope calculation: (Last WMA - First WMA) / (Number of bars - 1)
            slope = (recent_wma.iloc[-1] - recent_wma.iloc[0]) / (len(recent_wma) - 1)

            # Use a small threshold to filter minor fluctuations
            if slope > 0.05:
                self.wma_slope_trend = "UP"
            elif slope < -0.05:
                self.wma_slope_trend = "DOWN"
            else:
                self.wma_slope_trend = "FLAT"

            self.current_wma = ma_series.iloc[-1]
            logger.info(f"[{self.symbol}] WMA: {self.current_wma:.2f}, Slope: {self.wma_slope_trend}")
        else:
            logger.warning(f"[{self.symbol}] Not enough data to calculate WMA or slope.")


    def _analyze_stage(self):
        """
        Determines the current market stage based on Weinstein's rules.
        For MVP, this only determines the stage of the last bar.
        """
        if self.data.empty or self.current_wma is None:
            self.current_stage = "ERROR"
            return
        
        # We need a dedicated function to classify a single bar's stage
        def classify_bar_stage(close_price, wma_value, wma_slope):
            if close_price > wma_value:
                if wma_slope == "UP":
                    return "STAGE 2 (Uptrend)"
                elif wma_slope == "FLAT":
                    return "STAGE 1 (Accumulation/Breakout)"
                else: # WMA is DOWN
                    return "STAGE 1 (Accumulation/Transition)"
            else: # close_price <= wma_value
                if wma_slope == "DOWN":
                    return "STAGE 4 (Downtrend)"
                elif wma_slope == "FLAT":
                    return "STAGE 3 (Distribution/Breakdown)"
                else: # WMA is UP
                    return "STAGE 3 (Distribution/Transition)"
        
        # Determine current stage (last bar)
        last_close = self.data['close'].iloc[-1]
        
        # Determine current stage based on last bar and calculated slope/WMA
        self.current_stage = classify_bar_stage(last_close, self.current_wma, self.wma_slope_trend)

        logger.info(f"[{self.symbol}] Determined Stage: {self.current_stage}")

    def get_analysis_summary(self) -> Dict:
        """
        Returns the current analysis summary and checks for Stage 1 -> Stage 2 breakout.
        NOTE: Stage transition check is mocked for MVP and relies on the test override for verification.
        """
        if self.data.empty or self.current_wma is None:
            return {
                "symbol": self.symbol,
                "error": True,
                "message": "Data not loaded/analyzed."
            }
        
        current_stage = self.current_stage
        buy_signal = False
        
        # Dummy structure for transition check.
        details: Dict[str, Any] = {"recent_stages": []} 
        
        # --- TEST OVERRIDE START (20251210 - For Stage 1 Breakout Test Only) ---
        # Temporarily force a Stage 1 -> Stage 2 transition for testing buy signal logic for NVDA.
        ##if self.symbol == "NVDA":
        ##    logger.critical("NVDA STAGE OVERRIDE: Forcing Stage 1 -> Stage 2 transition for test.")
        ##    current_stage = "STAGE 2 (Uptrend)"
            # Simulate that the previous bar was Stage 1
        ##    details['recent_stages'] = [
        ##        {'date': 'Previous_Week', 'stage': 'STAGE 1 (Consolidation)'},
        ##        {'date': 'Current_Week', 'stage': current_stage}
        ##    ]
        # --- TEST OVERRIDE END ---
        
        
        # --- STAGE 1 BREAKOUT CHECK (PERMANENT LOGIC) ---
        # Check for Stage 1 to Stage 2 transition:
        # 1. Current stage must be Stage 2 (uptrend breakout).
        # 2. We check if the historical analysis (details) shows the immediate previous stage was Stage 1.
        if current_stage == "STAGE 2 (Uptrend)" and len(details['recent_stages']) > 1:
            # Check the second-to-last bar's stage
            previous_stage = details['recent_stages'][-2]['stage']
            
            if "STAGE 1" in previous_stage:
                buy_signal = True
                logger.critical(
                    "STAGE BREAKOUT BUY SIGNAL: [%s] Transitioned from Stage 1 to Stage 2! Buy Signal Triggered.",
                    self.symbol
                )
        # --- END PERMANENT LOGIC ---


        return {
            "symbol": self.symbol,
            "last_close": self.data['close'].iloc[-1].round(2),
            "wma_period": self.wma_period,
            "current_wma": round(self.current_wma, 2) if self.current_wma is not None else 'N/A',
            "wma_slope_trend": self.wma_slope_trend,
            "current_stage": current_stage,
            "price_vs_wma": "ABOVE" if self.data['close'].iloc[-1] > self.current_wma else "BELOW/AT",
            "stage1_to_stage2_breakout": buy_signal,
            "error": False,
        }
