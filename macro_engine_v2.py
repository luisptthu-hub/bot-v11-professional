"""Macro Engine V2 - FRED + Análise de sentimento econômico"""
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MacroEngineV2:
    """Análise macro com dados REAIS do FRED"""
    
    def __init__(self, fred_key: str):
        self.fred_key = fred_key
        self.fred_base = "https://api.stlouisfed.org/fred"
    
    def _fetch_fred(self, series_id: str) -> float:
        """Fetch último valor do FRED"""
        try:
            url = f"{self.fred_base}/series/observations"
            params = {
                'series_id': series_id,
                'api_key': self.fred_key,
                'sort_order': 'desc',
                'limit': 1
            }
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data.get('observations'):
                return float(data['observations'][0]['value'])
            return None
        except Exception as e:
            logger.error(f"FRED {series_id}: {e}")
            return None
    
    def get_macro_data(self, asset: str) -> str:
        """Análise macro completa para o ativo"""
        
        report = ""
        
        if asset == 'EURUSD':
            dxy = self._fetch_fred('DEXUSEU')
            ecb = self._fetch_fred('ECBDFR')
            fed = self._fetch_fred('FEDFUNDS')
            us_10y = self._fetch_fred('DGS10')
            eur_10y = self._fetch_fred('IRLTLT01EZM156N')
            
            report += f"💱 **EUR/USD**\n"
            report += f"• DXY: {dxy:.2f}\n" if dxy else ""
            report += f"• ECB: {ecb:.2f}%\n" if ecb else ""
            report += f"• Fed: {fed:.2f}%\n" if fed else ""
            report += f"• US 10Y: {us_10y:.2f}%\n" if us_10y else ""
            report += f"• EUR 10Y: {eur_10y:.2f}%\n" if eur_10y else ""
            
            if fed and ecb:
                if fed > ecb:
                    report += "🔴 **USD mais atrativo**\n"
                else:
                    report += "🟢 **EUR mais atrativo**\n"
        
        elif asset == 'USDJPY':
            fed = self._fetch_fred('FEDFUNDS')
            jpy_rate = self._fetch_fred('INTDSRJPM193N')
            us_10y = self._fetch_fred('DGS10')
            
            report += f"💱 **USD/JPY**\n"
            report += f"• Fed: {fed:.2f}%\n" if fed else ""
            report += f"• BOJ: {jpy_rate:.2f}%\n" if jpy_rate else ""
            report += f"• US 10Y: {us_10y:.2f}%\n" if us_10y else ""
            
            if fed and jpy_rate:
                diff = fed - jpy_rate
                if diff > 3:
                    report += f"🔴 **Carry Trade Extremo**\n"
                elif diff > 2:
                    report += f"🟠 **Carry Trade Forte**\n"
        
        elif asset == 'XAUUSD':
            us_10y = self._fetch_fred('DGS10')
            cpi = self._fetch_fred('CPIAUCSL')
            dxy = self._fetch_fred('DEXUSEU')
            fed = self._fetch_fred('FEDFUNDS')
            
            report += f"💰 **OURO**\n"
            report += f"• US 10Y: {us_10y:.2f}%\n" if us_10y else ""
            report += f"• CPI: {cpi:.2f}%\n" if cpi else ""
            report += f"• DXY: {dxy:.2f}\n" if dxy else ""
            report += f"• Fed: {fed:.2f}%\n" if fed else ""
            
            if us_10y and fed:
                real_yield = us_10y - (cpi if cpi else 3)
                if real_yield > 2:
                    report += "🔴 **Real Yields Altos**\n"
                elif real_yield < 0:
                    report += "🟢 **Real Yields Negativos**\n"
        
        elif asset == 'BTCUSD':
            fed = self._fetch_fred('FEDFUNDS')
            us_10y = self._fetch_fred('DGS10')
            dxy = self._fetch_fred('DEXUSEU')
            
            report += f"🪙 **BITCOIN**\n"
            report += f"• Fed: {fed:.2f}%\n" if fed else ""
            report += f"• US 10Y: {us_10y:.2f}%\n" if us_10y else ""
            report += f"• DXY: {dxy:.2f}\n" if dxy else ""
            
            if fed:
                if fed > 3:
                    report += "🔴 **Taxas Altas** → Menos liquidez\n"
                elif fed < 1:
                    report += "🟢 **Taxas Baixas** → Liquidez alta\n"
        
        if not report:
            report = "⚠️ Dados indisponíveis\n"
        
        return report
