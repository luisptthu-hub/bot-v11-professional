"""
BOT V11 PROFESSIONAL COMPLETO
Análise Institucional: Macro Real + Técnica + Notícias
Roda 100% localmente no PC
"""

import os
import logging
from datetime import datetime
import telebot
from dotenv import load_dotenv

# Import dos engines
from smc_engine import SMCEngine
from ict_engine import ICTEngine
from wyckoff_engine import WyckoffEngine
from macro_engine_v2 import MacroEngineV2
from volume_liquidity_engine import VolumeLiquidityEngine
from ml_engine import MLEngine
from news_engine import NewsEngine
from data_fetcher import DataFetcher

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT = int(os.getenv('TELEGRAM_CHAT'))
FRED_KEY = os.getenv('FRED_KEY')
NEWS_KEY = os.getenv('NEWS_API_KEY')

VERSION = "V11 PROFESSIONAL COMPLETO"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# ANALISADOR PROFISSIONAL COMPLETO
# ============================================================

class ProfessionalAnalyzerV11:
    """Analisador com Macro Real + Técnica + Notícias"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.news_engine = NewsEngine(NEWS_KEY) if NEWS_KEY else None
        self.macro_engine = MacroEngineV2(FRED_KEY) if FRED_KEY else None
    
    def analyze_asset_complete(self, asset: str) -> str:
        """Análise COMPLETA: Macro + Técnica + Notícias"""
        
        logger.info(f"Analisando {asset}...")
        
        # 1. BUSCAR DADOS TÉCNICOS
        df = self.data_fetcher.fetch_data(asset, period='3mo')
        if df is None or len(df) < 50:
            return f"❌ Sem dados técnicos para {asset}"
        
        # 2. BUSCAR DADOS MACRO
        macro_data = ""
        if self.macro_engine:
            macro_data = self.macro_engine.get_macro_data(asset)
        
        # 3. BUSCAR NOTÍCIAS
        news = ""
        if self.news_engine:
            news = self.news_engine.get_news(asset)
        
        try:
            # Rodar engines técnicos
            ohlc_df = df[['Open', 'High', 'Low', 'Close']].copy()
            if 'Volume' in df.columns:
                ohlc_df['Volume'] = df['Volume']
            
            smc = SMCEngine(ohlc_df)
            ict = ICTEngine(ohlc_df, asset)
            wyckoff = WyckoffEngine(ohlc_df)
            volume = VolumeLiquidityEngine(ohlc_df)
            ml = MLEngine(ohlc_df)
            
            # Montar relatório COMPLETO
            report = f"🎯 **ANÁLISE COMPLETA - {asset}**\n"
            report += f"⏰ {datetime.now().strftime('%H:%M %d/%m/%Y')}\n"
            report += "=" * 60 + "\n\n"
            
            # MACRO DATA
            if macro_data:
                report += "📊 **DADOS MACROECONÔMICOS**\n"
                report += macro_data
                report += "\n"
            
            # NOTÍCIAS
            if news:
                report += "📰 **NOTÍCIAS RELEVANTES**\n"
                report += news
                report += "\n"
            
            # ANÁLISE TÉCNICA
            report += "📈 **ANÁLISE TÉCNICA - SMC**\n"
            report += smc.get_signal_smc()
            report += "\n"
            
            report += "📈 **ANÁLISE TÉCNICA - ICT**\n"
            report += ict.get_signal_ict()
            report += "\n"
            
            report += "📈 **ANÁLISE TÉCNICA - WYCKOFF**\n"
            report += wyckoff.get_signal_wyckoff()
            report += "\n"
            
            report += "📈 **VOLUME & LIQUIDEZ**\n"
            report += volume.get_signal_volume()
            report += "\n"
            
            report += "🤖 **MACHINE LEARNING**\n"
            report += ml.get_signal_ml()
            
            return report
        
        except Exception as e:
            logger.error(f"Erro: {e}")
            return f"❌ Erro na análise: {str(e)}"

# ============================================================
# TELEGRAM HANDLERS
# ============================================================

analyzer = None

@bot.message_handler(commands=['start'])
def handle_start(message):
    msg = f"""
🚀 **{VERSION}**

*Análise Profissional: Macro Real + Técnica + Notícias*

*Comandos:*
/eur - EURUSD (Completo)
/jpy - USDJPY (Completo)
/xau - OURO (Completo)
/btc - BITCOIN (Completo)

/summary - Resumo dos 4 ativos

/help - Menu
    """
    bot.send_message(TELEGRAM_CHAT, msg, parse_mode='Markdown')
    logger.info("✅ /start")

@bot.message_handler(commands=['help'])
def handle_help(message):
    msg = f"""
💡 **COMANDOS**

/eur - Análise completa EURO
/jpy - Análise completa IENES
/xau - Análise completa OURO
/btc - Análise completa BITCOIN

/summary - Resumo dos 4 ativos

{VERSION}
    """
    bot.send_message(TELEGRAM_CHAT, msg, parse_mode='Markdown')
    logger.info("✅ /help")

@bot.message_handler(commands=['eur'])
def handle_eur(message):
    try:
        bot.send_message(TELEGRAM_CHAT, "⏳ Analisando EURO...")
        analysis = analyzer.analyze_asset_complete('EURUSD')
        
        if len(analysis) > 4000:
            parts = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
            for part in parts:
                bot.send_message(TELEGRAM_CHAT, part, parse_mode='Markdown')
        else:
            bot.send_message(TELEGRAM_CHAT, analysis, parse_mode='Markdown')
        
        logger.info("✅ /eur")
    except Exception as e:
        logger.error(f"❌ {e}")
        bot.send_message(TELEGRAM_CHAT, f"❌ Erro: {str(e)}")

@bot.message_handler(commands=['jpy'])
def handle_jpy(message):
    try:
        bot.send_message(TELEGRAM_CHAT, "⏳ Analisando IENES...")
        analysis = analyzer.analyze_asset_complete('USDJPY')
        
        if len(analysis) > 4000:
            parts = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
            for part in parts:
                bot.send_message(TELEGRAM_CHAT, part, parse_mode='Markdown')
        else:
            bot.send_message(TELEGRAM_CHAT, analysis, parse_mode='Markdown')
        
        logger.info("✅ /jpy")
    except Exception as e:
        logger.error(f"❌ {e}")

@bot.message_handler(commands=['xau'])
def handle_xau(message):
    try:
        bot.send_message(TELEGRAM_CHAT, "⏳ Analisando OURO...")
        analysis = analyzer.analyze_asset_complete('XAUUSD')
        
        if len(analysis) > 4000:
            parts = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
            for part in parts:
                bot.send_message(TELEGRAM_CHAT, part, parse_mode='Markdown')
        else:
            bot.send_message(TELEGRAM_CHAT, analysis, parse_mode='Markdown')
        
        logger.info("✅ /xau")
    except Exception as e:
        logger.error(f"❌ {e}")

@bot.message_handler(commands=['btc'])
def handle_btc(message):
    try:
        bot.send_message(TELEGRAM_CHAT, "⏳ Analisando BITCOIN...")
        analysis = analyzer.analyze_asset_complete('BTCUSD')
        
        if len(analysis) > 4000:
            parts = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
            for part in parts:
                bot.send_message(TELEGRAM_CHAT, part, parse_mode='Markdown')
        else:
            bot.send_message(TELEGRAM_CHAT, analysis, parse_mode='Markdown')
        
        logger.info("✅ /btc")
    except Exception as e:
        logger.error(f"❌ {e}")

@bot.message_handler(commands=['summary'])
def handle_summary(message):
    try:
        bot.send_message(TELEGRAM_CHAT, "⏳ Gerando resumo...")
        
        assets = ['EURUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']
        summary = "📊 **RESUMO GERAL - 4 ATIVOS**\n"
        summary += f"⏰ {datetime.now().strftime('%H:%M %d/%m/%Y')}\n"
        summary += "=" * 60 + "\n\n"
        
        for asset in assets:
            df = analyzer.data_fetcher.fetch_data(asset, period='3mo')
            if df is not None:
                last_close = df['Close'].iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                trend = "📈 UP" if last_close > ma20 else "📉 DOWN"
                
                macro_data = ""
                if analyzer.macro_engine:
                    macro_data = analyzer.macro_engine.get_macro_data(asset)
                
                summary += f"**{asset}** {trend}\n"
                if macro_data:
                    summary += macro_data
                summary += "\n"
            else:
                summary += f"❌ {asset}: Sem dados\n\n"
        
        bot.send_message(TELEGRAM_CHAT, summary, parse_mode='Markdown')
        logger.info("✅ /summary")
    except Exception as e:
        logger.error(f"❌ {e}")

@bot.message_handler(func=lambda message: True)
def handle_any(message):
    bot.send_message(TELEGRAM_CHAT, "❓ /help para comandos")

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    logger.info(f"🚀 {VERSION} iniciando...")
    
    analyzer = ProfessionalAnalyzerV11()
    
    bot.send_message(TELEGRAM_CHAT, f"🚀 *{VERSION} ONLINE!*\n\n✅ Macro Real\n✅ Técnica\n✅ Notícias\n\n/help", parse_mode='Markdown')
    
    logger.info("📡 Bot escutando...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
