"""
SESSION ENGINE — Bot V11
Análise de sessões: Ásia, Londres, NY e sobreposições
Volatilidade por sessão, range esperado, bias de sessão
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────
# DEFINIÇÃO DAS SESSÕES (UTC)
# ─────────────────────────────

SESSIONS = {
    'Asia': {
        'start': 0,   'end': 8,
        'emoji': '🌏',
        'desc':  'Tokyo/Sydney',
        'color': 'yellow',
    },
    'London': {
        'start': 7,   'end': 16,
        'emoji': '🇬🇧',
        'desc':  'Londres/Frankfurt',
        'color': 'blue',
    },
    'NY': {
        'start': 13,  'end': 22,
        'emoji': '🇺🇸',
        'desc':  'Nova York',
        'color': 'green',
    },
}

# Sobreposições (overlap)
OVERLAPS = {
    'Asia-London': {
        'start': 7, 'end': 8,
        'emoji': '⚡',
        'desc':  'Maior volatilidade — abertura Londres dentro da sessão asiática',
    },
    'London-NY': {
        'start': 13, 'end': 16,
        'emoji': '🔥',
        'desc':  'Maior volume do dia — melhor janela para setups',
    },
}

# Características por ativo em cada sessão
ASSET_SESSION_BIAS = {
    'XAUUSD': {
        'Asia':   {'activity': 'BAIXA',  'note': 'Range estreito, liquidez baixa'},
        'London': {'activity': 'ALTA',   'note': 'Maior movimento do ouro'},
        'NY':     {'activity': 'ALTA',   'note': 'CPI/NFP movem ouro fortemente'},
        'Asia-London': {'activity': 'MODERADA', 'note': 'Transição — primeiros movimentos'},
        'London-NY':   {'activity': 'MÁXIMA',   'note': 'Pico de volume e volatilidade'},
    },
    'EURUSD': {
        'Asia':   {'activity': 'BAIXA',  'note': 'Par europeu dorme na Ásia'},
        'London': {'activity': 'MÁXIMA', 'note': 'Maior volume EUR/USD do dia'},
        'NY':     {'activity': 'ALTA',   'note': 'Dados US movem o par'},
        'Asia-London': {'activity': 'MODERADA', 'note': 'Despertar gradual'},
        'London-NY':   {'activity': 'MÁXIMA',   'note': 'Pico absoluto de volume'},
    },
    'USDJPY': {
        'Asia':   {'activity': 'ALTA',   'note': 'Par japonês mais ativo na Ásia'},
        'London': {'activity': 'ALTA',   'note': 'Fluxo europeu no yen'},
        'NY':     {'activity': 'ALTA',   'note': 'Dados US + BoJ statements'},
        'Asia-London': {'activity': 'ALTA',     'note': 'Sobreposição ativa para JPY'},
        'London-NY':   {'activity': 'MÁXIMA',   'note': 'Maior liquidez do dia'},
    },
    'BTCUSD': {
        'Asia':   {'activity': 'MODERADA', 'note': 'Mercado asiático de cripto ativo'},
        'London': {'activity': 'ALTA',     'note': 'Europa entra no cripto'},
        'NY':     {'activity': 'ALTA',     'note': 'Maior volume institucional'},
        'Asia-London': {'activity': 'MODERADA', 'note': 'Transição de liquidez'},
        'London-NY':   {'activity': 'MÁXIMA',   'note': 'Pico de volume BTC'},
    },
}


# ─────────────────────────────
# SESSÃO ATUAL
# ─────────────────────────────

def get_active_sessions() -> dict:
    """Retorna sessões ativas agora e próxima sessão."""
    now  = datetime.now(timezone.utc)
    hour = now.hour

    active   = []
    overlaps = []

    for name, s in SESSIONS.items():
        if s['start'] <= hour < s['end']:
            active.append({
                'name':  name,
                'emoji': s['emoji'],
                'desc':  s['desc'],
                'hours_remaining': s['end'] - hour,
            })

    for name, ov in OVERLAPS.items():
        if ov['start'] <= hour < ov['end']:
            overlaps.append({
                'name':  name,
                'emoji': ov['emoji'],
                'desc':  ov['desc'],
            })

    # Próxima sessão
    next_session = None
    min_wait = 25
    for name, s in SESSIONS.items():
        diff = (s['start'] - hour) % 24
        if diff == 0:
            continue
        if diff < min_wait:
            min_wait     = diff
            next_session = {
                'name':        name,
                'emoji':       s['emoji'],
                'hours_until': diff,
                'starts_at':   f"{s['start']:02d}:00 UTC",
            }

    return {
        'hour':         hour,
        'active':       active,
        'overlaps':     overlaps,
        'next':         next_session,
        'is_overlap':   len(overlaps) > 0,
        'session_count': len(active),
    }


def get_session_quality(asset: str) -> dict:
    """Retorna qualidade da sessão atual para o ativo."""
    sessions = get_active_sessions()
    hour     = sessions['hour']

    if sessions['is_overlap']:
        ov_name  = sessions['overlaps'][0]['name']
        bias     = ASSET_SESSION_BIAS.get(asset, {}).get(ov_name, {})
        activity = bias.get('activity', 'MODERADA')
        note     = bias.get('note', '')
        return {
            'quality':   activity,
            'session':   ov_name,
            'note':      note,
            'is_overlap': True,
            'tradeable':  activity in ('ALTA', 'MÁXIMA'),
        }

    if sessions['active']:
        sess_name = sessions['active'][0]['name']
        bias      = ASSET_SESSION_BIAS.get(asset, {}).get(sess_name, {})
        activity  = bias.get('activity', 'MODERADA')
        note      = bias.get('note', '')
        return {
            'quality':   activity,
            'session':   sess_name,
            'note':      note,
            'is_overlap': False,
            'tradeable':  activity in ('ALTA', 'MÁXIMA'),
        }

    return {
        'quality':   'INATIVA',
        'session':   'Sem sessão ativa',
        'note':      'Fora das janelas principais',
        'is_overlap': False,
        'tradeable':  False,
    }


# ─────────────────────────────
# RANGE HISTÓRICO POR SESSÃO
# ─────────────────────────────

def calc_session_ranges(df_1h: pd.DataFrame) -> dict:
    """
    Calcula range médio histórico de cada sessão (últimos 20 dias).
    Útil para saber o quanto o ativo costuma mover em cada janela.
    """
    if df_1h is None or len(df_1h) < 48:
        return {}

    try:
        df = df_1h.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True)
        else:
            df.index = df.index.tz_localize('UTC') if df.index.tzinfo is None else df.index.tz_convert('UTC')

        results = {}

        for sess_name, s in SESSIONS.items():
            sess_data = df[
                (df.index.hour >= s['start']) &
                (df.index.hour < s['end'])
            ]

            if len(sess_data) < 5:
                continue

            # Range por dia de sessão
            daily_ranges = []
            for date, group in sess_data.groupby(sess_data.index.date):
                if len(group) >= 2:
                    r = float(group['High'].max() - group['Low'].min())
                    daily_ranges.append(r)

            if not daily_ranges:
                continue

            avg_range = np.mean(daily_ranges[-20:])
            max_range = np.max(daily_ranges[-20:])
            min_range = np.min(daily_ranges[-20:])

            results[sess_name] = {
                'avg_range': round(avg_range, 5),
                'max_range': round(max_range, 5),
                'min_range': round(min_range, 5),
                'sample':    len(daily_ranges),
            }

        return results

    except Exception as e:
        logger.error(f'[SESSION] calc_session_ranges erro: {e}')
        return {}


# ─────────────────────────────
# RANGE DA SESSÃO ATUAL
# ─────────────────────────────

def calc_current_session_range(df_1h: pd.DataFrame) -> dict:
    """
    Range formado na sessão atual (do início até agora).
    Compara com range histórico médio.
    """
    if df_1h is None or len(df_1h) < 5:
        return {}

    try:
        df = df_1h.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True)
        else:
            df.index = df.index.tz_localize('UTC') if df.index.tzinfo is None else df.index.tz_convert('UTC')

        now  = datetime.now(timezone.utc)
        hour = now.hour

        # Identifica sessão atual
        current_sess = None
        for name, s in SESSIONS.items():
            if s['start'] <= hour < s['end']:
                current_sess = (name, s)
                break

        if not current_sess:
            return {}

        sess_name, s = current_sess
        sess_start   = now.replace(hour=s['start'], minute=0, second=0, microsecond=0)
        sess_data    = df[df.index >= sess_start]

        if len(sess_data) < 1:
            return {}

        current_high  = round(float(sess_data['High'].max()), 5)
        current_low   = round(float(sess_data['Low'].min()), 5)
        current_range = round(current_high - current_low, 5)
        current_close = round(float(df['Close'].iloc[-1]), 5)

        # Posição no range da sessão
        range_pos = ((current_close - current_low) / (current_high - current_low + 1e-10))

        return {
            'session':       sess_name,
            'session_high':  current_high,
            'session_low':   current_low,
            'session_range': current_range,
            'range_position': round(range_pos * 100, 1),  # % do range (0=low, 100=high)
            'bias':          'TOP' if range_pos > 0.7 else ('BOTTOM' if range_pos < 0.3 else 'MEIO'),
            'candles':       len(sess_data),
        }

    except Exception as e:
        logger.error(f'[SESSION] current range erro: {e}')
        return {}


# ─────────────────────────────
# VOLATILIDADE POR SESSÃO
# ─────────────────────────────

def calc_session_volatility(df_1h: pd.DataFrame) -> dict:
    """
    Compara volatilidade da sessão atual vs média histórica.
    Retorna se está acima ou abaixo do normal.
    """
    if df_1h is None or len(df_1h) < 20:
        return {}

    try:
        df = df_1h.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True)

        returns  = df['Close'].pct_change().dropna()
        vol_now  = float(returns.tail(8).std())   # última sessão (~8h)
        vol_hist = float(returns.tail(120).std())  # últimos 5 dias

        ratio = vol_now / (vol_hist + 1e-10)

        if ratio > 1.5:
            state = 'ALTA VOLATILIDADE'
            emoji = '🔴'
        elif ratio > 1.0:
            state = 'VOLATILIDADE NORMAL+'
            emoji = '🟡'
        elif ratio > 0.5:
            state = 'VOLATILIDADE NORMAL'
            emoji = '🟢'
        else:
            state = 'BAIXA VOLATILIDADE'
            emoji = '⚪'

        return {
            'state':     state,
            'emoji':     emoji,
            'ratio':     round(ratio, 2),
            'vol_now':   round(vol_now * 100, 4),
            'vol_hist':  round(vol_hist * 100, 4),
        }

    except Exception as e:
        logger.error(f'[SESSION] volatility erro: {e}')
        return {}


# ─────────────────────────────
# BIAS DE SESSÃO (TENDÊNCIA INTRADAY)
# ─────────────────────────────

def calc_session_bias(df_1h: pd.DataFrame, df_15m: pd.DataFrame = None) -> dict:
    """
    Bias da sessão atual: direção dominante baseada em
    estrutura de preço intraday (HH/HL vs LH/LL).
    """
    df = df_15m if df_15m is not None and len(df_15m) >= 20 else df_1h

    if df is None or len(df) < 10:
        return {}

    try:
        closes = df['Close'].values[-20:]
        highs  = df['High'].values[-20:]
        lows   = df['Low'].values[-20:]

        # HH/HL = alta | LH/LL = baixa
        hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll = sum(1 for i in range(1, len(lows))  if lows[i]  < lows[i-1])
        hl = sum(1 for i in range(1, len(lows))  if lows[i]  > lows[i-1])
        lh = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])

        bull_score = hh + hl
        bear_score = ll + lh

        if bull_score > bear_score * 1.3:
            bias  = 'ALTA'
            emoji = '⬆️'
        elif bear_score > bull_score * 1.3:
            bias  = 'BAIXA'
            emoji = '⬇️'
        else:
            bias  = 'LATERAL'
            emoji = '↔️'

        # Momentum curto (últimas 4 velas)
        momentum = closes[-1] - closes[-4] if len(closes) >= 4 else 0
        mom_dir  = '⬆️' if momentum > 0 else '⬇️'

        return {
            'bias':        bias,
            'emoji':       emoji,
            'bull_score':  bull_score,
            'bear_score':  bear_score,
            'momentum':    round(float(momentum), 5),
            'momentum_dir': mom_dir,
        }

    except Exception as e:
        logger.error(f'[SESSION] bias erro: {e}')
        return {}


# ─────────────────────────────
# ANÁLISE COMPLETA DE SESSÃO
# ─────────────────────────────

def analyze_sessions(asset: str, timeframes_data: dict) -> dict:
    """
    Análise completa de sessões para um ativo.
    """
    df_1h  = timeframes_data.get('1H')
    df_15m = timeframes_data.get('15M')
    df_4h  = timeframes_data.get('4H')

    result = {
        'asset':          asset,
        'active_sessions': get_active_sessions(),
        'quality':         get_session_quality(asset),
        'session_ranges':  calc_session_ranges(df_1h),
        'current_range':   calc_current_session_range(df_1h),
        'volatility':      calc_session_volatility(df_1h),
        'bias':            calc_session_bias(df_1h, df_15m),
    }

    return result


# ─────────────────────────────
# SCORE PARA CONFLUENCE ENGINE
# ─────────────────────────────

def session_confluence_score(session: dict, direction: str) -> tuple:
    """
    Converte análise de sessão em pontos para o confluence_engine.
    Returns: (score_bull, score_bear, factors)
    """
    score_bull = 0
    score_bear = 0
    factors    = []

    quality = session.get('quality', {})
    bias    = session.get('bias', {})
    vol     = session.get('volatility', {})

    # ── Qualidade da sessão ──
    activity = quality.get('quality', 'BAIXA')
    if activity == 'MÁXIMA':
        # Sessão premium: reforça o viés dominante
        if direction == 'COMPRA':
            score_bull += 2
        elif direction == 'VENDA':
            score_bear += 2
        factors.append(f"Sessão MÁXIMA ({quality.get('session')}) — alta probabilidade (+2)")
    elif activity == 'ALTA':
        if direction == 'COMPRA':
            score_bull += 1
        elif direction == 'VENDA':
            score_bear += 1
        factors.append(f"Sessão ALTA ({quality.get('session')}) (+1)")
    elif activity in ('BAIXA', 'INATIVA'):
        # Penaliza setups fora de horário
        if direction == 'COMPRA':
            score_bull -= 1
        elif direction == 'VENDA':
            score_bear -= 1
        factors.append(f"Sessão {activity} — baixa probabilidade (-1)")

    # ── Bias da sessão alinhado com direção ──
    sess_bias = bias.get('bias', 'LATERAL')
    if sess_bias == 'ALTA' and direction == 'COMPRA':
        score_bull += 1
        factors.append(f"Bias intraday ALTA alinhado com viés de compra (+1)")
    elif sess_bias == 'BAIXA' and direction == 'VENDA':
        score_bear += 1
        factors.append(f"Bias intraday BAIXA alinhado com viés de venda (+1)")
    elif sess_bias != 'LATERAL' and sess_bias != direction:
        factors.append(f"Bias intraday diverge do viés macro (atenção)")

    return score_bull, score_bear, factors


# ─────────────────────────────
# FORMATAÇÃO
# ─────────────────────────────

def format_session_message(session: dict) -> str:
    """Formata bloco de sessões para a mensagem do ativo."""
    lines = ["─────────────────────────────", "🕐 SESSÕES"]

    # Sessões ativas
    active = session.get('active_sessions', {})
    if active.get('active'):
        sess_names = ', '.join([f"{s['emoji']} {s['name']}" for s in active['active']])
        lines.append(f"Ativa: {sess_names}")
    else:
        nxt = active.get('next', {})
        if nxt:
            lines.append(f"Fora de sessão | Próxima: {nxt['emoji']} {nxt['name']} em {nxt['hours_until']}h ({nxt['starts_at']})")

    # Overlap
    if active.get('is_overlap'):
        ov = active['overlaps'][0]
        lines.append(f"⚡ OVERLAP: {ov['name']} — {ov['desc']}")

    # Qualidade para o ativo
    quality = session.get('quality', {})
    act     = quality.get('quality', 'N/D')
    act_emoji = {'MÁXIMA': '🟢', 'ALTA': '🟡', 'MODERADA': '🟠', 'BAIXA': '🔴', 'INATIVA': '⚪'}.get(act, '')
    lines.append(f"Atividade: {act_emoji} {act} — {quality.get('note', '')}")

    # Range atual da sessão
    curr = session.get('current_range', {})
    if curr:
        lines.append(f"Range sessão: {curr.get('session_low')} — {curr.get('session_high')} ({curr.get('range_position')}% do range)")

    # Volatilidade
    vol = session.get('volatility', {})
    if vol:
        lines.append(f"Volatilidade: {vol.get('emoji')} {vol.get('state')} (ratio: {vol.get('ratio')}x)")

    # Bias intraday
    bias = session.get('bias', {})
    if bias:
        lines.append(f"Bias intraday: {bias.get('emoji')} {bias.get('bias')} | Momentum: {bias.get('momentum_dir')}")

    # Ranges históricos das sessões
    hist = session.get('session_ranges', {})
    if hist:
        lines.append("Ranges médios históricos:")
        for sess_name, r in hist.items():
            s = SESSIONS.get(sess_name, {})
            lines.append(f"  {s.get('emoji','')} {sess_name}: {r['avg_range']} (max: {r['max_range']})")

    return '\n'.join(lines)
