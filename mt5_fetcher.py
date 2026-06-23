"""
MT5 FETCHER — Bot V11
Puxa dados OHLCV e preço atual via MetaTrader 5 (Windows local)
Usado como fonte primária — YFinance como fallback
"""

import pandas as pd
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# MT5 só disponível em Windows
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("[MT5] MetaTrader5 não instalado. Use: pip install MetaTrader5")


# ─────────────────────────────
# SÍMBOLOS MT5
# ─────────────────────────────

MT5_SYMBOLS = {
    'XAUUSD': 'XAUUSD',
    'EURUSD': 'EURUSD',
    'USDJPY': 'USDJPY',
    'BTCUSD': 'BTCUSD',
    'DXY':    'DXY',
    'US10Y':  'US10Y',
    'SP500':  'SP500',
    'WTI':    'USOIL',
}

# Timeframes MT5
MT5_TIMEFRAMES = {
    '1M':  1,       # TIMEFRAME_M1
    '5M':  5,       # TIMEFRAME_M5
    '15M': 15,      # TIMEFRAME_M15
    '1H':  16385,   # TIMEFRAME_H1
    '4H':  16388,   # TIMEFRAME_H4
    'D1':  16408,   # TIMEFRAME_D1
}

# Quantidade de candles por timeframe
MT5_CANDLES = {
    '1M':  500,
    '5M':  500,
    '15M': 500,
    '1H':  720,
    '4H':  500,
    'D1':  365,
}


# ─────────────────────────────
# CONEXÃO
# ─────────────────────────────

_connected = False


def connect(login: int = None, password: str = None,
            server: str = None, path: str = None) -> bool:
    """
    Conecta ao MT5.
    Se login/password/server forem None, usa a sessão já aberta no MT5.
    """
    global _connected

    if not MT5_AVAILABLE:
        logger.error("[MT5] Lib não instalada.")
        return False

    if _connected:
        return True

    try:
        # Inicializa MT5
        if path:
            ok = mt5.initialize(path=path)
        else:
            ok = mt5.initialize()

        if not ok:
            err = mt5.last_error()
            logger.error(f"[MT5] initialize() falhou: {err}")
            return False

        # Login explícito (opcional — se MT5 já estiver aberto e logado, pula)
        if login and password and server:
            ok = mt5.login(login=login, password=password, server=server)
            if not ok:
                err = mt5.last_error()
                logger.error(f"[MT5] login() falhou: {err}")
                mt5.shutdown()
                return False

        info = mt5.terminal_info()
        if info is None:
            logger.error("[MT5] terminal_info() retornou None")
            mt5.shutdown()
            return False

        _connected = True
        logger.info(f"[MT5] Conectado — {info.name} | Build {info.build}")
        return True

    except Exception as e:
        logger.error(f"[MT5] Erro na conexão: {e}")
        return False


def disconnect():
    """Encerra conexão com MT5."""
    global _connected
    if MT5_AVAILABLE and _connected:
        mt5.shutdown()
        _connected = False
        logger.info("[MT5] Desconectado.")


def is_connected() -> bool:
    """Verifica se MT5 está conectado e operacional."""
    global _connected
    if not MT5_AVAILABLE or not _connected:
        return False
    try:
        info = mt5.terminal_info()
        return info is not None
    except Exception:
        _connected = False
        return False


def ensure_connected(login: int = None, password: str = None,
                     server: str = None, path: str = None) -> bool:
    """Garante conexão ativa, reconecta se necessário."""
    if is_connected():
        return True
    return connect(login, password, server, path)


# ─────────────────────────────
# SÍMBOLO
# ─────────────────────────────

def _resolve_symbol(asset: str) -> Optional[str]:
    """
    Resolve símbolo MT5 para o ativo.
    Tenta variações comuns se o símbolo padrão não existir.
    """
    candidates = [
        MT5_SYMBOLS.get(asset, asset),
        asset,
        asset + 'm',    # ex: XAUUSDm (alguns brokers)
        asset + '..',   # ex: XAUUSD..
        asset + 'pro',  # ex: XAUUSDpro
    ]

    for sym in candidates:
        info = mt5.symbol_info(sym)
        if info is not None:
            if not info.visible:
                mt5.symbol_select(sym, True)
            return sym

    logger.warning(f"[MT5] Símbolo não encontrado para {asset}. Tentativas: {candidates}")
    return None


# ─────────────────────────────
# OHLCV
# ─────────────────────────────

def fetch_ohlcv_mt5(asset: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Puxa dados OHLCV via MT5.
    Retorna DataFrame com colunas Open/High/Low/Close/Volume ou None.
    """
    if not ensure_connected():
        return None

    symbol = _resolve_symbol(asset)
    if symbol is None:
        return None

    tf_int = MT5_TIMEFRAMES.get(timeframe)
    if tf_int is None:
        logger.error(f"[MT5] Timeframe desconhecido: {timeframe}")
        return None

    n_candles = MT5_CANDLES.get(timeframe, 500)

    try:
        # Tenta via copy_rates_from_pos (mais confiável)
        rates = mt5.copy_rates_from_pos(symbol, tf_int, 0, n_candles)

        if rates is None or len(rates) == 0:
            err = mt5.last_error()
            logger.warning(f"[MT5] Sem dados para {asset} {timeframe}: {err}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('time', inplace=True)
        df.rename(columns={
            'open':     'Open',
            'high':     'High',
            'low':      'Low',
            'close':    'Close',
            'tick_volume': 'Volume',
        }, inplace=True)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.dropna(inplace=True)

        if len(df) < 5:
            return None

        logger.info(f"[MT5] ✅ {asset} {timeframe}: {len(df)} candles")
        return df

    except Exception as e:
        logger.error(f"[MT5] Erro ao puxar {asset} {timeframe}: {e}")
        return None


# ─────────────────────────────
# PREÇO ATUAL (TICK)
# ─────────────────────────────

def fetch_tick_mt5(asset: str) -> Optional[dict]:
    """
    Puxa último tick (bid/ask) do MT5.
    Mais preciso que OHLCV para preço atual.
    """
    if not ensure_connected():
        return None

    symbol = _resolve_symbol(asset)
    if symbol is None:
        return None

    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        price = (tick.bid + tick.ask) / 2
        spread = tick.ask - tick.bid

        # Variação diária via D1
        rates = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES['D1'], 0, 2)
        change     = 0.0
        change_pct = 0.0
        prev_close = None

        if rates is not None and len(rates) >= 2:
            prev_close = float(rates[-2]['close'])
            change     = round(price - prev_close, 5)
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

        return {
            'asset':      asset,
            'symbol':     symbol,
            'price':      round(price, 5),
            'bid':        round(tick.bid, 5),
            'ask':        round(tick.ask, 5),
            'spread':     round(spread, 5),
            'change':     change,
            'change_pct': change_pct,
            'prev_close': prev_close,
            'direction':  '⬆️' if change >= 0 else '⬇️',
            'source':     'MT5',
        }

    except Exception as e:
        logger.error(f"[MT5] Erro tick {asset}: {e}")
        return None


# ─────────────────────────────
# MULTI-TIMEFRAME
# ─────────────────────────────

def fetch_multi_timeframe_mt5(asset: str) -> dict:
    """Puxa todos os timeframes via MT5."""
    result = {}
    for tf in ['D1', '4H', '1H', '15M', '5M', '1M']:
        df = fetch_ohlcv_mt5(asset, tf)
        if df is not None:
            result[tf] = df
    return result


# ─────────────────────────────
# STATUS
# ─────────────────────────────

def get_mt5_status() -> dict:
    """Retorna status detalhado da conexão MT5."""
    if not MT5_AVAILABLE:
        return {'available': False, 'connected': False, 'reason': 'Lib não instalada'}

    if not _connected:
        return {'available': True, 'connected': False, 'reason': 'Não conectado'}

    try:
        info    = mt5.terminal_info()
        account = mt5.account_info()

        if info is None:
            return {'available': True, 'connected': False, 'reason': 'Terminal não responde'}

        return {
            'available':  True,
            'connected':  True,
            'terminal':   info.name,
            'build':      info.build,
            'broker':     account.company if account else 'N/D',
            'account':    account.login if account else 'N/D',
            'currency':   account.currency if account else 'N/D',
            'reason':     '',
        }
    except Exception as e:
        return {'available': True, 'connected': False, 'reason': str(e)}


def format_mt5_status() -> str:
    """Formata status MT5 para o Telegram."""
    s = get_mt5_status()
    if not s['available']:
        return "🔴 MT5: Lib não instalada (pip install MetaTrader5)"
    if not s['connected']:
        return f"🔴 MT5: Desconectado — {s['reason']}"
    return (
        f"🟢 MT5: Conectado\n"
        f"   Terminal: {s['terminal']} (build {s['build']})\n"
        f"   Broker: {s['broker']}\n"
        f"   Conta: {s['account']} ({s['currency']})"
    )
