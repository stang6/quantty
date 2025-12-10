# core/strategy/stage_analyzer.py
import pandas as pd
import os
import logging
from typing import Dict, Any
from core.logging.logger import get_logger

# Constants
WMA_PERIOD = 30

# NOTE: This path is currently hardcoded to match the existing file structure. 
# We assume the data ingestion module saves data here.
FILE_PATH_TEMPLATE = "historical_data/{symbol}_1week_3Y.csv" 

# Stage Analyzer
logger = get_logger("STGANA")

class StageAnalyzer:
    """
    Implements Stan Weinstein's Stage Analysis logic.
    Calculates the 30-Week Moving Average (30-WMA) and determines the current stage.
    Also calculates average volume and provides necessary data for filtering.
    """
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.data: pd.DataFrame = self._load_data()
        self.wma_period = WMA_PERIOD
        # Initialize instance attributes
        self.current_stage = "UNKNOWN"
        self.wma_slope_trend = "UNKNOWN"
        self.current_wma = None
        
        # --- NEW/MODIFIED ATTRIBUTES FOR SCANNING ---
        self.avg_volume = 0.0 # Average weekly volume (last 52 weeks)
        self.last_close = 0.0 # Last closing price
        # Attribute to store detailed analysis (used for transition check)
        self.stage_history: Dict[str, Any] = {"recent_stages": []} 
        # -------------------------------------------

        if not self.data.empty:
            self.last_close = self.data['close'].iloc[-1] # Get last close immediately
            self._calculate_wma()
            self._analyze_stage()
            self._calculate_avg_volume() # Calculate average volume

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


    def _calculate_avg_volume(self):
        """Calculates the 52-week simple average of trading volume."""
        # Use the last 52 weeks of data
        volume_series = self.data['volume'].tail(52) 
        if not volume_series.empty:
            self.avg_volume = volume_series.mean()
        else:
            self.avg_volume = 0.0


    def _analyze_stage(self):
        """Determines the current market stage based on Weinstein's rules."""
        if self.data.empty or self.current_wma is None:
            self.current_stage = "ERROR"
            return

        # Last closing price is already stored in self.last_close

        # 1. Price is Above WMA
        if self.last_close > self.current_wma:
            if self.wma_slope_trend == "UP":
                self.current_stage = "STAGE 2 (Uptrend)"
            elif self.wma_slope_trend == "FLAT":
                self.current_stage = "STAGE 1 (Accumulation/Breakout)"
            else: # WMA is DOWN
                self.current_stage = "STAGE 1 (Accumulation/Transition)"

        # 2. Price is Below WMA
        else: # last_close <= self.current_wma
            if self.wma_slope_trend == "DOWN":
                self.current_stage = "STAGE 4 (Downtrend)"
            elif self.wma_slope_trend == "FLAT":
                self.current_stage = "STAGE 3 (Distribution/Breakdown)"
            else: # WMA is UP
                self.current_stage = "STAGE 3 (Distribution/Transition)"

        logger.info(f"[{self.symbol}] Determined Stage: {self.current_stage}")

    def get_analysis_summary(self) -> Dict:
        """Returns the current analysis summary including all analysis data."""
        if self.data.empty or self.current_wma is None:
            return {
                "symbol": self.symbol,
                "error": True,
                "message": "Data not loaded/analyzed."
            }

        return {
            "symbol": self.symbol,
            "last_close": self.last_close.round(2), 
            "wma_period": self.wma_period,
            "current_wma": round(self.current_wma, 2) if self.current_wma is not None else 'N/A',
            "wma_slope_trend": self.wma_slope_trend,
            "current_stage": self.current_stage,
            "price_vs_wma": "ABOVE" if self.last_close > self.current_wma else "BELOW/AT",
            "stage1_to_stage2_breakout": False, # Placeholder for StanStrategy check
            "avg_volume": self.avg_volume, 
            "data_points": len(self.data), 
            "error": False,
        }
