"""News Engine - Notícias REAIS com NewsAPI"""
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class NewsEngine:
    """Busca notícias relevantes do mercado"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"
    
    def get_news(self, asset: str, days: int = 3) -> str:
        """Busca notícias relevantes para o ativo"""
        
        try:
            keywords = self._get_keywords(asset)
            report = ""
            
            for keyword in keywords:
                try:
                    from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                    
                    params = {
                        'q': keyword,
                        'from': from_date,
                        'sortBy': 'relevancy',
                        'language': 'en',
                        'apiKey': self.api_key
                    }
                    
                    response = requests.get(self.base_url, params=params, timeout=5)
                    data = response.json()
                    
                    if data.get('articles'):
                        articles = data['articles'][:2]
                        
                        for article in articles:
                            title = article.get('title', 'N/A')
                            source = article.get('source', {}).get('name', 'Unknown')
                            
                            report += f"📌 {title}\n"
                            report += f"   {source}\n"
                
                except:
                    continue
            
            if not report:
                report = "📰 Sem notícias\n"
            
            return report
        
        except Exception as e:
            logger.error(f"News error: {e}")
            return "⚠️ Notícias indisponíveis\n"
    
    @staticmethod
    def _get_keywords(asset: str) -> list:
        """Keywords para busca"""
        
        keywords_map = {
            'EURUSD': ['EUR USD', 'ECB'],
            'USDJPY': ['USD JPY', 'BOJ'],
            'XAUUSD': ['Gold', 'XAU'],
            'BTCUSD': ['Bitcoin', 'crypto']
        }
        
        return keywords_map.get(asset, [asset])
