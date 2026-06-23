"""
BOT V11 — Trader Macro Profissional
Telegram bot rodando localmente
Dados reais: YFinance + FRED API
4 ativos: XAUUSD, EURUSD, USDJPY, BTCUSD
"""

import os
import logging
import schedule
import time
import threading
from datetime import datetime

import telebot
from dotenv import load_dotenv

from data_fetcher import (
    fetch_multi_timeframe,
    fetch_current_price,
    fetch_all_assets_prices,
    fetch_intermarket,
)
from macro_engine import analyze_macro, format_macro_message
from technical_engine import analyze_technical
from confluence_engine import (
    calculate_confluence,
    format_asset_message,
    format_summary_message,
)
from ml_engine import analyze_ml_multi_tf, format_ml_message, ml_confluence_score
from ict_engine import analyze_ict, format_ict_message, ict_confluence_score
from session_engine import analyze_sessions, format_session_message, session_confluence_score

# ─── CONFIG ───
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT  = int(os.getenv('TELEGRAM_CHAT'))
FRED_KEY       = os.getenv('FRED_KEY')
NEWS_API_KEY   = os.getenv('NEWS_API_KEY', '')

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT or not FRED_KEY:
    raise ValueError("❌ Variáveis de ambiente faltando! Verifique o .env")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

ASSETS = ['XAUUSD', 'EURUSD', 'USDJPY', 'BTCUSD']

ASSET_NAMES = {
    'XAUUSD': '🥇 OURO',
    'EURUSD': '💶 EUR/USD',
    'USDJPY': '💴 USD/JPY',
    'BTCUSD': '₿ BITCOIN',
}


# ─────────────────────────────
# ANÁLISE COMPLETA DE UM ATIVO
# ─────────────────────────────

def run_analysis(asset: str) -> str:
    """Roda análise completa de um ativo e retorna mensagem formatada."""
    try:
        logger.info(f"Analisando {asset}...")

        # 1. Preço atual
        price_data = fetch_current_price(asset)
        if not price_data:
            return f"⚠️ {asset}: Não foi possível puxar preço atual."

        # 2. Dados multi-timeframe
        tf_data = fetch_multi_timeframe(asset)
        if not tf_data:
            return f"⚠️ {asset}: Sem dados de gráfico disponíveis."

        # 3. Dados macro
        macro = analyze_macro(FRED_KEY)

        # 4. Análise técnica
        tech = analyze_technical(asset, tf_data)

        # 5. Intermarket
        intermarket = fetch_intermarket()

        # 6. ML Engine
        ml_result = analyze_ml_multi_tf(asset, tf_data)

        # 7. ICT Engine
        ict_result = analyze_ict(asset, tf_data)

        # 8. Session Engine
        session_result = analyze_sessions(asset, tf_data)

        # 9. Confluência
        ml_score = ml_confluence_score(ml_result, 'NEUTRO')
        confluence = calculate_confluence(asset, macro, tech, intermarket,
                                          ml=ml_result, ict=ict_result, session=session_result)

        # 10. Formata mensagem
        msg = format_asset_message(asset, price_data, macro, tech, confluence)
        msg += '\n' + format_session_message(session_result)
        msg += '\n' + format_ict_message(ict_result)
        msg += '\n' + format_ml_message(asset, ml_result)
        return msg

    except Exception as e:
        logger.error(f"Erro na análise de {asset}: {e}")
        return f"⚠️ {asset}: Erro na análise. Tente novamente."


def run_all_assets() -> list[dict]:
    """Roda análise de todos os 4 ativos."""
    results = []
    macro = analyze_macro(FRED_KEY)

    for asset in ASSETS:
        try:
            price_data  = fetch_current_price(asset)
            tf_data     = fetch_multi_timeframe(asset)
            intermarket = fetch_intermarket()

            if not price_data or not tf_data:
                continue

            tech           = analyze_technical(asset, tf_data)
            ml_result      = analyze_ml_multi_tf(asset, tf_data)
            ict_result     = analyze_ict(asset, tf_data)
            session_result = analyze_sessions(asset, tf_data)
            confluence     = calculate_confluence(asset, macro, tech, intermarket,
                                                  ml=ml_result, ict=ict_result, session=session_result)

            results.append({
                'asset':          asset,
                'price':          price_data.get('price'),
                'direction':      confluence.get('direction'),
                'confluence_pct': confluence.get('confluence_pct'),
                'rec_emoji':      confluence.get('rec_emoji'),
            })

        except Exception as e:
            logger.error(f"Erro em {asset}: {e}")

    return results


# ─────────────────────────────
# COMANDOS DO BOT
# ─────────────────────────────

@bot.message_handler(commands=['start'])
def cmd_start(message):
    msg = """🤖 BOT V11 — Trader Macro Profissional

Comandos disponíveis:

/macro — Contexto macro global
/analise — Resumo dos 4 ativos
/noticias — Notícias dos 4 ativos
/xau — Análise OURO
/eur — Análise EUR/USD
/jpy — Análise USD/JPY
/btc — Análise Bitcoin
/mt5 — Status da conexão MT5

📅 Análise automática:
• 08:00 UTC — Abertura Londres
• 13:00 UTC — Abertura NY

🔔 Alertas automáticos:
• Confluência > 80% → alerta imediato
• Confluência > 90% → alerta FORTE 🚨

Dados: YFinance + FRED API (reais)"""
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['macro'])
def cmd_macro(message):
    bot.send_message(message.chat.id, "⏳ Puxando dados macro...")
    try:
        macro = analyze_macro(FRED_KEY)
        msg   = format_macro_message(macro)
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Erro ao puxar macro: {e}")


@bot.message_handler(commands=['xau'])
def cmd_xau(message):
    bot.send_message(message.chat.id, "⏳ Analisando OURO...")
    msg = run_analysis('XAUUSD')
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['eur'])
def cmd_eur(message):
    bot.send_message(message.chat.id, "⏳ Analisando EUR/USD...")
    msg = run_analysis('EURUSD')
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['jpy'])
def cmd_jpy(message):
    bot.send_message(message.chat.id, "⏳ Analisando USD/JPY...")
    msg = run_analysis('USDJPY')
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['btc'])
def cmd_btc(message):
    bot.send_message(message.chat.id, "⏳ Analisando Bitcoin...")
    msg = run_analysis('BTCUSD')
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['analise'])
def cmd_analise(message):
    bot.send_message(message.chat.id, "⏳ Analisando os 4 ativos...")
    results = run_all_assets()
    if results:
        msg = format_summary_message(results)
        bot.send_message(message.chat.id, msg)
    else:
        bot.send_message(message.chat.id, "⚠️ Não foi possível puxar dados. Tente novamente.")


@bot.message_handler(commands=['mt5'])
def cmd_mt5(message):
    try:
        from mt5_fetcher import format_mt5_status
        bot.send_message(message.chat.id, format_mt5_status())
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Erro ao verificar MT5: {e}")


@bot.message_handler(commands=['noticias'])
def cmd_noticias(message):
    bot.send_message(message.chat.id, '⏳ Buscando notícias e calendário...')
    try:
        all_tech = {}
        for asset in ASSETS:
            tf_data = fetch_multi_timeframe(asset)
            if tf_data:
                all_tech[asset] = analyze_technical(asset, tf_data)

        from news_engine import format_news_calendar_message
        msg = format_news_calendar_message(NEWS_API_KEY, all_tech)
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        logger.error(f'Erro /noticias: {e}')
        bot.send_message(message.chat.id, f'⚠️ Erro ao buscar notícias: {e}')


# ─────────────────────────────
# ANÁLISE AUTOMÁTICA (Sessões)
# ─────────────────────────────

def auto_analysis(session_name: str):
    """Roda análise automática e envia pro Telegram."""
    logger.info(f"🔔 Análise automática — {session_name}")
    now = datetime.utcnow().strftime('%d %b %Y | %H:%M UTC')

    header = f"🔔 ANÁLISE AUTOMÁTICA — {session_name}\n{now}\n"
    bot.send_message(TELEGRAM_CHAT, header)

    # Macro global
    try:
        macro = analyze_macro(FRED_KEY)
        bot.send_message(TELEGRAM_CHAT, format_macro_message(macro))
    except Exception as e:
        logger.error(f"Erro macro auto: {e}")

    # Cada ativo
    for asset in ASSETS:
        try:
            msg = run_analysis(asset)
            bot.send_message(TELEGRAM_CHAT, msg)
            time.sleep(1)  # evita flood
        except Exception as e:
            logger.error(f"Erro auto {asset}: {e}")


def schedule_sessions():
    """Agenda resumo automático dos 4 ativos nos horários de sessão."""

    # 15min antes da Ásia
    schedule.every().day.at("23:45").do(auto_analysis, session_name="⏰ PRÉ-SESSÃO ÁSIA (15min)")
    # Overlap Ásia-Londres
    schedule.every().day.at("07:00").do(auto_analysis, session_name="⚡ OVERLAP ÁSIA-LONDRES")
    # 15min antes de Londres
    schedule.every().day.at("06:45").do(auto_analysis, session_name="⏰ PRÉ-SESSÃO LONDRES (15min)")
    # 15min antes de NY
    schedule.every().day.at("12:45").do(auto_analysis, session_name="⏰ PRÉ-SESSÃO NY (15min)")
    # Overlap Londres-NY
    schedule.every().day.at("13:00").do(auto_analysis, session_name="🔥 OVERLAP LONDRES-NY")

    logger.info(
        "⏰ Agendado: 23:45 Pré-Ásia | 06:45 Pré-Londres | "
        "07:00 Overlap Ásia-Londres | 12:45 Pré-NY | 13:00 Overlap Londres-NY"
    )

    while True:
        schedule.run_pending()
        time.sleep(30)


# ─────────────────────────────
# INICIALIZAÇÃO
# ─────────────────────────────

def main():
    logger.info("🚀 BOT V11 iniciando...")

    # Notifica no Telegram que tá online
    try:
        bot.send_message(TELEGRAM_CHAT, "✅ Bot V11 online! Use /start para ver os comandos.")
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de inicio: {e}")

    # Inicia scheduler em thread separada
    scheduler_thread = threading.Thread(target=schedule_sessions, daemon=True)
    scheduler_thread.start()

    logger.info("📡 Bot escutando...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)


if __name__ == '__main__':
    main()
