"""ML Engine - Random Forest classification"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import logging

logger = logging.getLogger(__name__)

class MLEngine:
    """Machine Learning com Random Forest"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy().reset_index(drop=True)
        self.model = None
        self.train_model()
    
    def _create_features(self) -> pd.DataFrame:
        """Criar features para ML"""
        try:
            df = self.df.copy()
            
            # Retornos
            df['returns'] = df['Close'].pct_change()
            
            # MAs
            df['ma5'] = df['Close'].rolling(5).mean()
            df['ma20'] = df['Close'].rolling(20).mean()
            df['ma50'] = df['Close'].rolling(50).mean() if len(df) >= 50 else df['Close'].rolling(20).mean()
            
            # Volatilidade
            df['volatility'] = df['returns'].rolling(10).std()
            
            # RSI simplificado
            df['rsi'] = self._calculate_rsi(df['Close'])
            
            # Target: próximo movimento (1=UP, 0=DOWN)
            df['target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
            
            # Remover NaNs
            df = df.dropna()
            
            return df
        except Exception as e:
            logger.error(f"Feature creation error: {e}")
            return None
    
    @staticmethod
    def _calculate_rsi(prices, period=14):
        """Calcular RSI"""
        try:
            deltas = np.diff(prices)
            seed = deltas[:period+1]
            up = seed[seed >= 0].sum() / period
            down = -seed[seed < 0].sum() / period
            rs = up / down if down != 0 else up
            
            rsi = np.zeros_like(prices)
            rsi[:period] = 100. - 100. / (1. + rs)
            
            for i in range(period, len(prices)):
                delta = deltas[i-1]
                if delta > 0:
                    upval = delta
                    downval = 0.
                else:
                    upval = 0.
                    downval = -delta
                
                up = (up * (period - 1) + upval) / period
                down = (down * (period - 1) + downval) / period
                
                rs = up / down if down != 0 else up
                rsi[i] = 100. - 100. / (1. + rs)
            
            return rsi
        except:
            return np.zeros(len(prices))
    
    def train_model(self):
        """Treinar Random Forest"""
        try:
            df = self._create_features()
            if df is None or len(df) < 30:
                logger.warning("Dados insuficientes para ML")
                return
            
            features = ['returns', 'ma5', 'ma20', 'ma50', 'volatility', 'rsi']
            X = df[features].values
            y = df['target'].values
            
            self.model = RandomForestClassifier(n_estimators=10, max_depth=5, random_state=42)
            self.model.fit(X, y)
            
        except Exception as e:
            logger.error(f"ML training error: {e}")
            self.model = None
    
    def predict(self) -> tuple:
        """Fazer predição"""
        try:
            if self.model is None:
                return None, 0.5
            
            df = self._create_features()
            if df is None or len(df) < 5:
                return None, 0.5
            
            features = ['returns', 'ma5', 'ma20', 'ma50', 'volatility', 'rsi']
            X_last = df[features].values[-1:] 
            
            prediction = self.model.predict(X_last)[0]
            probability = self.model.predict_proba(X_last)[0][1]
            
            return prediction, probability
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None, 0.5
    
    def get_signal_ml(self) -> str:
        """Signal ML"""
        try:
            prediction, probability = self.predict()
            
            if prediction is None:
                return "⚠️ Modelo em treinamento\n"
            
            report = "🤖 **RANDOM FOREST**\n"
            
            if prediction == 1:
                report += f"📈 **BULLISH** - {probability*100:.1f}%\n"
            else:
                report += f"📉 **BEARISH** - {(1-probability)*100:.1f}%\n"
            
            report += f"• Confiança: {max(probability, 1-probability)*100:.1f}%\n"
            
            return report
        except Exception as e:
            logger.error(f"Signal error: {e}")
            return "⚠️ Erro no ML\n"
