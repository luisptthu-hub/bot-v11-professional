"""Data Fetcher - Puxar dados REAIS do YFinance"""
import yfinance as yf
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DataFetcher:
    """Busca dados técnicos reais"""
    
    ASSETS = {
        'EURUSD': 'EURUSD=X',
        'USDJPY': 'USDJPY=X',
        'XAUUSD': 'GC=F',
        'BTCUSD': 'BTC-USD'
    }
    
    @staticmethod
    def fetch_data(asset: str, period: str = '3mo', interval: str = '1d') -> pd.DataFrame:
        """Fetch OHLCV data"""
        try:
            ticker = DataFetcher.ASSETS.get(asset, asset)
            data = yf.download(ticker, period=period, interval=interval, progress=False)
            
            if data.empty:
                logger.error(f"Sem dados para {asset}")
                return None
            
            return data
        except Exception as e:
            logger.error(f"Erro fetching {asset}: {e}")
            return None
    
    @staticmethod
    def get_current_price(asset: str) -> float:
        """Get last close price"""
        try:
            ticker = DataFetcher.ASSETS.get(asset, asset)
            data = yf.download(ticker, period='1d', progress=False)
            return float(data['Close'].iloc[-1])
        except:
            return None
