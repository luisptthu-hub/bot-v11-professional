"""Volume & Liquidity Engine"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class VolumeLiquidityEngine:
    """Análise de volume e liquidez"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy().reset_index(drop=True)
    
    def _analyze_volume(self) -> str:
        """Análise de volume"""
        try:
            if 'Volume' not in self.df.columns or len(self.df) < 10:
                return "⚠️ Sem dados de volume\n"
            
            volumes = self.df['Volume'].tail(10).values
            avg_vol = volumes.mean()
            last_vol = volumes[-1]
            
            if last_vol > avg_vol * 1.5:
                return "📊 **VOLUME ALTO** - Interesse institucional\n"
            elif last_vol < avg_vol * 0.7:
                return "🔇 **VOLUME BAIXO** - Pouca liquidez\n"
            else:
                return "🔄 **Volume normal**\n"
        except:
            return "⚠️ Erro\n"
    
    def _analyze_profile(self) -> str:
        """Profile de volume - Aonde há mais negócios"""
        try:
            if len(self.df) < 10:
                return "⚠️ Dados insuficientes\n"
            
            highs = self.df['High'].tail(10).max()
            lows = self.df['Low'].tail(10).min()
            closes = self.df['Close'].tail(10).values
            
            avg_close = closes.mean()
            
            if closes[-1] > avg_close:
                report = "🔴 **Volume Profile** - Preço acima da média\n"
            else:
                report = "🟢 **Volume Profile** - Preço abaixo da média\n"
            
            report += f"• Alto: {highs:.2f}\n"
            report += f"• Baixo: {lows:.2f}\n"
            
            return report
        except:
            return "⚠️ Erro\n"
    
    def _analyze_support_resistance(self) -> str:
        """Suporte e resistência baseado em volume"""
        try:
            if len(self.df) < 20:
                return "⚠️ Dados insuficientes\n"
            
            highs = self.df['High'].tail(20).values
            lows = self.df['Low'].tail(20).values
            
            support = lows.min()
            resistance = highs.max()
            
            report = "📈 **S/R**\n"
            report += f"• Resistência: {resistance:.2f}\n"
            report += f"• Suporte: {support:.2f}\n"
            
            return report
        except:
            return "⚠️ Erro\n"
    
    def get_signal_volume(self) -> str:
        """Signal volume completo"""
        report = ""
        report += self._analyze_volume()
        report += self._analyze_profile()
        report += self._analyze_support_resistance()
        return report
