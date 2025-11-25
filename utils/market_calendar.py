# ============================================
# utils/market_calendar.py (Dynamic Holiday Check)
# ============================================

import logging
from typing import Set
from datetime import date, timedelta
import pandas_market_calendars as mcal

# Global cache to store calculated holiday dates to avoid recalculating frequently
_HOLIDAY_CACHE: Set[date] = set()
_CACHE_EXPIRATION_DATE: date = date.min

def load_us_market_holidays() -> Set[date]:
    """
    Dynamically loads US stock market full holidays for the current and next year
    using pandas-market-calendars.
    
    Returns: A set of datetime.date objects representing full market closure days.
    """
    global _HOLIDAY_CACHE
    global _CACHE_EXPIRATION_DATE
    
    current_year = date.today().year

    # Check cache expiration (recalculate once a year)
    if date.today() < _CACHE_EXPIRATION_DATE:
        logging.debug("Market holidays loaded from cache.")
        return _HOLIDAY_CACHE

    logging.info(f"Recalculating US market holidays for {current_year} and {current_year + 1}...")
    
    try:
        # Define the New York Stock Exchange calendar
        nyse = mcal.get_calendar('NYSE')
        
        # Determine the start and end date for calculation (Current year to end of next year)
        start_date = f'{current_year}-01-01'
        end_date = f'{current_year + 1}-12-31'
        
        # Get the full schedule, including holidays (returns only business days)
        schedule = nyse.schedule(start_date=start_date, end_date=end_date)
        
        # Get all days within the range
        all_days = pd.date_range(start=start_date, end=end_date, freq='D').date
        
        # Get the set of all trading days
        trading_days = set(schedule.index.normalize().date)
        
        # Holidays are all days minus trading days (including weekends)
        # We filter this down to only days that are NOT trading days AND are NOT Saturday/Sunday
        # NYSE.holidays().holidays is the most direct way to get official holidays.
        
        # Get the official list of full holidays (trading=False and is_holiday=True)
        all_holidays = nyse.holidays().holidays.date
        
        # Filter out weekends to get only official closure days (mandatory liquidation days)
        full_holidays = {d for d in all_holidays if d.weekday() < 5} # weekday < 5 means Mon-Fri

        _HOLIDAY_CACHE = full_holidays
        _CACHE_EXPIRATION_DATE = date(current_year + 2, 1, 1) # Set expiration to next two years
        
        logging.info(f"Found {len(_HOLIDAY_CACHE)} official full market closure days.")
        
        return _HOLIDAY_CACHE

    except ImportError:
        logging.critical("CRITICAL: pandas-market-calendars not installed. Using static list if available.")
        # Fallback to a simple static list if necessary, but this requires manual updating.
        return set()
    except Exception as e:
        logging.error(f"Error dynamically loading holidays: {e}")
        return set()

# Optional: Add a function to check for half days if needed for Module C in the future
# def is_half_day(check_date: date) -> bool:
#     # ... implementation to check for days where market closes early ...
#     pass
