"""SMC Engine - Smart Money Concepts"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class SMCEngine:
    """SMC: Market Structure, BOS, CHoCH"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy().reset_index(drop=True)
    
    def _find_bos(self) -> str:
        """Break of Structure"""
        try:
            if len(self.df) < 5:
                return "⚠️ Dados insuficientes\n"
            
            closes = self.df['Close'].values
            highs = self.df['High'].values
            lows = self.df['Low'].values
            
            last_high = highs[-2]
            last_low = lows[-2]
            last_close = closes[-1]
            
            if last_close > last_high:
                return "📈 **BOS ALTA**\n"
            elif last_close < last_low:
                return "📉 **BOS BAIXA**\n"
            else:
                return "🔄 **SEM BOS**\n"
        except:
            return "⚠️ Erro\n"
    
    def _find_choch(self) -> str:
        """Change of Character"""
        try:
            if len(self.df) < 20:
                return "⚠️ Dados insuficientes\n"
            
            recent = self.df['Close'].tail(10).values
            older = self.df['Close'].iloc[5:15].values
            
            recent_range = recent.max() - recent.min()
            older_range = older.max() - older.min()
            
            if recent_range > older_range * 1.5:
                return "⚡ **CHoCH** - Volatilidade ↑\n"
            else:
                return "🔇 **Volatilidade estável**\n"
        except:
            return "⚠️ Erro\n"
    
    def _find_order_blocks(self) -> str:
        """Order Blocks"""
        try:
            if len(self.df) < 10:
                return "⚠️ Dados insuficientes\n"
            
            lows = self.df['Low'].values
            highs = self.df['High'].values
            ma20 = self.df['Close'].rolling(20).mean().iloc[-1]
            
            report = "🔳 **ORDER BLOCKS**\n"
            report += f"• Suporte: {lows[-1]:.2f}\n"
            report += f"• Resistência: {highs[-1]:.2f}\n"
            report += f"• MA20: {ma20:.2f}\n"
            
            return report
        except:
            return "⚠️ Erro\n"
    
    def get_signal_smc(self) -> str:
        """Signal SMC"""
        report = ""
        report += self._find_bos()
        report += self._find_choch()
        report += self._find_order_blocks()
        return report
