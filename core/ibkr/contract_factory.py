# core/ibkr/contract_factory.py
from ib_insync import Stock, Contract

class ContractFactory:
    """
    Centralized factory for creating different types of Interactive Brokers contracts.
    Ensures consistency in contract specification across the application.
    """

    def create_stock_contract(self, symbol: str, exchange: str, currency: str = "USD") -> Contract:
        """
        Creates a standard stock contract.
        
        Args:
            symbol: The stock ticker symbol (e.g., 'TSLA').
            exchange: The primary exchange (e.g., 'SMART').
            currency: The trading currency.
            
        Returns:
            A configured ib_insync Contract object.
        """
        return Stock(symbol, exchange, currency)

    # You can add methods for other contract types here later:
    # def create_option_contract(self, ...):
    #     pass
    
    # def create_future_contract(self, ...):
    #     pass
