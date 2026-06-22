"""Wyckoff Engine - Acumulação e Distribuição"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class WyckoffEngine:
    """Wyckoff: Acumulação, Distribuição, Spring"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy().reset_index(drop=True)
    
    def _detect_accumulation(self) -> str:
        """Detecção de fase de acumulação"""
        try:
            if len(self.df) < 20:
                return "⚠️ Dados insuficientes\n"
            
            lows = self.df['Low'].tail(20).values
            closes = self.df['Close'].tail(20).values
            
            min_low = lows.min()
            max_close = closes.max()
            
            if max_close - min_low < (closes.mean() * 0.05):
                return "🟢 **ACUMULAÇÃO DETECTADA**\n"
            else:
                return "🔄 **Sem padrão de acumulação**\n"
        except:
            return "⚠️ Erro\n"
    
    def _detect_distribution(self) -> str:
        """Detecção de fase de distribuição"""
        try:
            if len(self.df) < 20:
                return "⚠️ Dados insuficientes\n"
            
            highs = self.df['High'].tail(20).values
            closes = self.df['Close'].tail(20).values
            
            max_high = highs.max()
            min_close = closes.min()
            
            if max_high - min_close < (closes.mean() * 0.05):
                return "🔴 **DISTRIBUIÇÃO DETECTADA**\n"
            else:
                return "🔄 **Sem padrão de distribuição**\n"
        except:
            return "⚠️ Erro\n"
    
    def _detect_spring(self) -> str:
        """Spring - Toque do suporte com rompimento"""
        try:
            if len(self.df) < 10:
                return "⚠️ Dados insuficientes\n"
            
            lows = self.df['Low'].tail(10).values
            closes = self.df['Close'].tail(5).values
            
            min_low = lows.min()
            recent_close = closes[-1]
            
            if recent_close > min_low * 1.01 and recent_close > closes[-2]:
                return "⚡ **SPRING DETECTADO** - Rompimento do suporte\n"
            else:
                return "🔇 **Sem spring**\n"
        except:
            return "⚠️ Erro\n"
    
    def get_signal_wyckoff(self) -> str:
        """Signal Wyckoff completo"""
        report = ""
        report += self._detect_accumulation()
        report += self._detect_distribution()
        report += self._detect_spring()
        return report
