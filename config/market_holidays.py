from datetime import date
from typing import Set

# --- NYSE/NASDAQ US MARKET HOLIDAYS ---

def load_us_market_holidays() -> Set[date]:
    """
    Loads US stock market holidays (NYSE/NASDAQ) for 2025 and 2026.
    The market is completely closed on these dates.
    """
    holidays = {
        # --- 2025 Remaining Holidays ---
        date(2025, 11, 27), # Thanksgiving Day
        date(2025, 12, 25), # Christmas Day
        
        # --- 2026 Holidays ---
        date(2026, 1, 1),   # New Year's Day
        date(2026, 1, 19),  # Martin Luther King, Jr.'s Birthday (Monday)
        date(2026, 2, 16),  # Washington's Birthday (Monday)
        date(2026, 4, 3),   # Good Friday (Friday)
        date(2026, 5, 25),  # Memorial Day (Monday)
        date(2026, 6, 19),  # Juneteenth National Independence Day (Friday)
        date(2026, 7, 3),   # Independence Day (Friday observed, since 7/4 is a Saturday)
        date(2026, 9, 7),   # Labor Day (Monday)
        date(2026, 11, 26), # Thanksgiving Day (Thursday)
        date(2026, 12, 25), # Christmas Day (Friday)
        
        # Note: Markets close early (e.g., 1 PM ET) on some dates (e.g., day after Thanksgiving, Christmas Eve),
        # but for simplicity, we only include full-day closures here.
    }
    return holidays

# You can now use this set in your module_C_execution.py

# Example usage in other modules:
# from config.market_holidays import load_us_market_holidays
# US_HOLIDAYS = load_us_market_holidays()
