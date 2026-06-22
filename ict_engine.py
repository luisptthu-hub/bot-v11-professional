"""ICT Engine - Institutional Client Time"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ICTEngine:
    """ICT: Kill Zones, Market Bias, Delivery"""
    
    def __init__(self, df: pd.DataFrame, asset: str = ''):
        self.df = df.copy().reset_index(drop=True)
        self.asset = asset
    
    def _get_kill_zones(self) -> str:
        """Kill zones (NY/London)"""
        try:
            if len(self.df) < 5:
                return "⚠️ Dados insuficientes\n"
            
            recent_highs = self.df['High'].tail(5).max()
            recent_lows = self.df['Low'].tail(5).min()
            
            report = "🎯 **KILL ZONES**\n"
            report += f"• Alta recente: {recent_highs:.2f}\n"
            report += f"• Baixa recente: {recent_lows:.2f}\n"
            
            return report
        except:
            return "⚠️ Erro\n"
    
    def _get_market_bias(self) -> str:
        """Market Bias - Tendência"""
        try:
            if len(self.df) < 20:
                return "⚠️ Dados insuficientes\n"
            
            close_prices = self.df['Close'].values
            ma20 = self.df['Close'].rolling(20).mean().iloc[-1]
            ma50 = self.df['Close'].rolling(50).mean().iloc[-1] if len(self.df) >= 50 else ma20
            
            last_price = close_prices[-1]
            
            if last_price > ma20 > ma50:
                bias = "📈 **BULLISH**\n"
            elif last_price < ma20 < ma50:
                bias = "📉 **BEARISH**\n"
            else:
                bias = "🔄 **MIXED**\n"
            
            report = "📊 **MARKET BIAS**\n"
            report += bias
            report += f"• Preço: {last_price:.2f}\n"
            report += f"• MA20: {ma20:.2f}\n"
            
            return report
        except:
            return "⚠️ Erro\n"
    
    def _get_delivery(self) -> str:
        """Delivery - Estrutura de preço"""
        try:
            if len(self.df) < 5:
                return "⚠️ Dados insuficientes\n"
            
            opens = self.df['Open'].tail(5).values
            closes = self.df['Close'].tail(5).values
            
            up_candles = sum(1 for o, c in zip(opens, closes) if c > o)
            down_candles = 5 - up_candles
            
            if up_candles > 3:
                delivery = "🟢 **Entrega para CIMA**\n"
            elif down_candles > 3:
                delivery = "🔴 **Entrega para BAIXO**\n"
            else:
                delivery = "🟡 **Entrega Mista**\n"
            
            return delivery
        except:
            return "⚠️ Erro\n"
    
    def get_signal_ict(self) -> str:
        """Signal ICT"""
        report = ""
        report += self._get_kill_zones()
        report += self._get_market_bias()
        report += self._get_delivery()
        return report
