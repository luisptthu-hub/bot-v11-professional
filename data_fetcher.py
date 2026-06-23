"""
DATA FETCHER — Bot V11
Fonte primária: MetaTrader 5 (Windows local)
Fallback: YFinance
"""

import yfinance as yf
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# MT5 como fonte primária
try:
    from mt5_fetcher import (
        fetch_ohlcv_mt5,
        fetch_tick_mt5,
        fetch_multi_timeframe_mt5,
        ensure_connected,
        MT5_AVAILABLE,
    )
    _mt5_ready = MT5_AVAILABLE and ensure_connected()
    if _mt5_ready:
        logger.info("[DATA] MT5 ativo — usando como fonte primária")
    else:
        logger.info("[DATA] MT5 indisponível — usando YFinance")
except Exception as e:
    _mt5_ready = False
    logger.warning(f"[DATA] MT5 não carregado: {e} — usando YFinance")

# Símbolos corretos no YFinance
SYMBOLS = {
    'XAUUSD': 'GC=F',
    'EURUSD': 'EURUSD=X',
    'USDJPY': 'USDJPY=X',
    'BTCUSD': 'BTC-USD',
    'DXY':    'DX-Y.NYB',
    'US10Y':  '^TNX',
    'SP500':  '^GSPC',
    'WTI':    'CL=F',
}

TIMEFRAMES = {
    '1M':  ('7d',  '1m'),
    '5M':  ('7d',  '5m'),
    '15M': ('7d',  '15m'),
    '1H':  ('30d', '1h'),
    
    '4H':  ('60d', '4h'),
    'D1':  ('3mo', '1d'),
}


def _fix_columns(df):
    """Corrige MultiIndex do yfinance 1.4+"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_ohlcv(asset: str, timeframe: str):
    """Puxa dados OHLCV — MT5 primeiro, YFinance como fallback."""

    # ── MT5 ──
    if _mt5_ready:
        df = fetch_ohlcv_mt5(asset, timeframe)
        if df is not None and len(df) >= 5:
            return df
        logger.warning(f"[DATA] MT5 falhou para {asset} {timeframe} — tentando YFinance")

    # ── YFinance (fallback) ──
    return _fetch_ohlcv_yf(asset, timeframe)


def _fetch_ohlcv_yf(asset: str, timeframe: str):
    """Puxa dados OHLCV via YFinance (fallback)."""
    symbol = SYMBOLS.get(asset)
    if not symbol:
        return None

    period, interval = TIMEFRAMES.get(timeframe, ('3mo', '1d'))

    try:
        df = yf.download(symbol, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None

        df = _fix_columns(df)
        cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
        df = df[cols].copy()
        df.dropna(inplace=True)

        if len(df) < 5:
            return None

        logger.info(f"✅ {asset} {timeframe}: {len(df)} candles")
        return df

    except Exception as e:
        logger.error(f"Erro ao puxar {asset} {timeframe}: {e}")
        return None


def fetch_current_price(asset: str):
    """Puxa preço atual — MT5 tick primeiro, YFinance como fallback."""

    # ── MT5 ──
    if _mt5_ready:
        data = fetch_tick_mt5(asset)
        if data:
            return data
        logger.warning(f"[DATA] MT5 tick falhou para {asset} — tentando YFinance")

    # ── YFinance (fallback) ──
    return _fetch_current_price_yf(asset)


def _fetch_current_price_yf(asset: str):
    """Puxa preço atual via YFinance (fallback)."""
    symbol = SYMBOLS.get(asset)
    if not symbol:
        return None

    try:
        df = yf.download(symbol, period='5d', interval='1d',
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 2:
            logger.warning(f"Sem dados para {asset}")
            return None

        df = _fix_columns(df)

        price      = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        change     = price - prev_close
        change_pct = (change / prev_close) * 100

        return {
            'asset':      asset,
            'price':      round(price, 5),
            'change':     round(change, 5),
            'change_pct': round(change_pct, 2),
            'direction':  '⬆️' if change >= 0 else '⬇️',
        }

    except Exception as e:
        logger.error(f"Erro ao puxar preço de {asset}: {e}")
        return None


def fetch_intermarket():
    """Puxa dados de intermarket."""
    result = {}
    for asset in ['DXY', 'US10Y', 'SP500', 'WTI', 'XAUUSD', 'BTCUSD']:
        data = fetch_current_price(asset)
        if data:
            result[asset] = data
    return result


def fetch_all_assets_prices():
    """Puxa preço atual dos 4 ativos principais."""
    result = {}
    for asset in ['XAUUSD', 'EURUSD', 'USDJPY', 'BTCUSD']:
        data = fetch_current_price(asset)
        if data:
            result[asset] = data
    return result


def fetch_multi_timeframe(asset: str):
    """Puxa dados do ativo em todos os timeframes — MT5 primeiro, YFinance como fallback."""

    # ── MT5 ──
    if _mt5_ready:
        result = fetch_multi_timeframe_mt5(asset)
        if result:
            # Preenche timeframes faltantes com YFinance
            missing = [tf for tf in ['D1', '4H', '1H', '15M', '5M', '1M'] if tf not in result]
            for tf in missing:
                logger.warning(f"[DATA] MT5 sem dados para {asset} {tf} — usando YFinance")
                df = _fetch_ohlcv_yf(asset, tf)
                if df is not None:
                    result[tf] = df
            return result

        logger.warning(f"[DATA] MT5 multi-TF falhou para {asset} — usando YFinance")

    # ── YFinance (fallback) ──
    result = {}
    for tf in ['D1', '4H', '1H', '15M', '5M', '1M']:
        df = _fetch_ohlcv_yf(asset, tf)
        if df is not None:
            result[tf] = df
    return result
