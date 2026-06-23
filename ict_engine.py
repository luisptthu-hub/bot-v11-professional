"""
ICT ENGINE — Bot V11
Killzones, NWOG, MMXM, Optimal Trade Entry, Liquidity Pools
Conceitos: Inner Circle Trader (ICT)
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────
# KILLZONES
# ─────────────────────────────

# Horários UTC das killzones ICT
KILLZONES = {
    'Asian Range':     {'start': 20, 'end': 0,  'emoji': '🌏'},  # 20:00-00:00 UTC (dom-sex)
    'London Open':     {'start': 2,  'end': 5,  'emoji': '🇬🇧'},  # 02:00-05:00 UTC
    'London Close':    {'start': 10, 'end': 12, 'emoji': '🏴'},  # 10:00-12:00 UTC
    'NY Open':         {'start': 13, 'end': 16, 'emoji': '🇺🇸'},  # 13:00-16:00 UTC
    'NY Lunch':        {'start': 16, 'end': 18, 'emoji': '🍽️'},  # 16:00-18:00 UTC (evitar)
    'NY PM Session':   {'start': 18, 'end': 20, 'emoji': '🌆'},  # 18:00-20:00 UTC
}

# Killzones de maior probabilidade por ativo
PRIME_KILLZONES = {
    'XAUUSD': ['London Open', 'NY Open'],
    'EURUSD': ['London Open', 'NY Open'],
    'USDJPY': ['Asian Range', 'London Open', 'NY Open'],
    'BTCUSD': ['London Open', 'NY Open', 'NY PM Session'],
}


def get_current_killzone() -> dict:
    """Identifica em qual killzone estamos agora."""
    now_utc = datetime.now(timezone.utc)
    hour    = now_utc.hour

    active = []
    for name, kz in KILLZONES.items():
        s, e = kz['start'], kz['end']
        if s < e:
            in_zone = s <= hour < e
        else:  # passa da meia-noite (ex: Asian 20:00-00:00)
            in_zone = hour >= s or hour < e

        if in_zone:
            active.append({'name': name, 'emoji': kz['emoji']})

    if not active:
        # Calcula próxima killzone
        next_kz = _next_killzone(hour)
        return {
            'active':  False,
            'zones':   [],
            'next':    next_kz,
            'current_hour': hour,
        }

    return {
        'active': True,
        'zones':  active,
        'next':   None,
        'current_hour': hour,
    }


def _next_killzone(current_hour: int) -> dict:
    """Retorna a próxima killzone e horas até ela."""
    starts = []
    for name, kz in KILLZONES.items():
        h = kz['start']
        diff = (h - current_hour) % 24
        starts.append((diff, name, kz['emoji']))

    starts.sort()
    diff, name, emoji = starts[0]
    return {'name': name, 'emoji': emoji, 'hours_until': diff}


def is_prime_killzone(asset: str) -> bool:
    """Verifica se o ativo está em sua killzone de maior probabilidade."""
    kz = get_current_killzone()
    if not kz['active']:
        return False
    prime = PRIME_KILLZONES.get(asset, [])
    return any(z['name'] in prime for z in kz['zones'])


# ─────────────────────────────
# ASIAN RANGE
# ─────────────────────────────

def calc_asian_range(df_1h: pd.DataFrame) -> dict:
    """
    Calcula o range asiático (20:00-00:00 UTC) do dia atual.
    Usado para identificar alvos de liquidez londrinos/NY.
    """
    if df_1h is None or len(df_1h) < 10:
        return {}

    try:
        df = df_1h.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            return {}

        df.index = pd.to_datetime(df.index, utc=True)
        now = datetime.now(timezone.utc)

        # Range asiático da última sessão (últimas 24h)
        cutoff = now - timedelta(hours=28)
        recent = df[df.index >= cutoff]

        # Filtra horas asiáticas (20:00-00:00 UTC)
        asian = recent[recent.index.hour >= 20]

        if len(asian) < 2:
            return {}

        asian_high = round(float(asian['High'].max()), 5)
        asian_low  = round(float(asian['Low'].min()), 5)
        asian_mid  = round((asian_high + asian_low) / 2, 5)
        current    = round(float(df['Close'].iloc[-1]), 5)

        return {
            'high':    asian_high,
            'low':     asian_low,
            'mid':     asian_mid,
            'range':   round(asian_high - asian_low, 5),
            'current': current,
            'broken_high': current > asian_high,
            'broken_low':  current < asian_low,
        }
    except Exception as e:
        logger.error(f'[ICT] Asian range erro: {e}')
        return {}


# ─────────────────────────────
# NWOG — New Week Opening Gap
# ─────────────────────────────

def calc_nwog(df_1h: pd.DataFrame) -> dict:
    """
    New Week Opening Gap: diferença entre fechamento de sexta e
    abertura de domingo (mercado Forex/Ouro/BTC).
    Gap = zona de liquidez a ser preenchida.
    """
    if df_1h is None or len(df_1h) < 20:
        return {}

    try:
        df = df_1h.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            return {}

        df.index = pd.to_datetime(df.index, utc=True)

        # Fechamento de sexta (última vela de sexta)
        fridays = df[df.index.dayofweek == 4]
        if len(fridays) < 1:
            return {}

        friday_close = round(float(fridays['Close'].iloc[-1]), 5)

        # Abertura de domingo (primeira vela de domingo ou segunda)
        sundays = df[df.index.dayofweek == 6]
        mondays = df[df.index.dayofweek == 0]

        if len(sundays) >= 1:
            week_open = round(float(sundays['Open'].iloc[0]), 5)
        elif len(mondays) >= 1:
            week_open = round(float(mondays['Open'].iloc[0]), 5)
        else:
            return {}

        gap = round(week_open - friday_close, 5)
        gap_pct = round((gap / friday_close) * 100, 4) if friday_close != 0 else 0

        current = round(float(df['Close'].iloc[-1]), 5)
        gap_filled = (
            (gap > 0 and current >= week_open) or
            (gap < 0 and current <= week_open)
        )

        if abs(gap_pct) < 0.01:
            return {}  # gap insignificante

        return {
            'friday_close': friday_close,
            'week_open':    week_open,
            'gap':          gap,
            'gap_pct':      gap_pct,
            'gap_filled':   gap_filled,
            'direction':    'BULLISH' if gap > 0 else 'BEARISH',
            'current':      current,
            'zone_top':     max(friday_close, week_open),
            'zone_bot':     min(friday_close, week_open),
        }
    except Exception as e:
        logger.error(f'[ICT] NWOG erro: {e}')
        return {}


# ─────────────────────────────
# NDOG — New Day Opening Gap
# ─────────────────────────────

def calc_ndog(df_1h: pd.DataFrame) -> dict:
    """
    New Day Opening Gap: gap entre fechamento de ontem e abertura de hoje.
    Versão intraday do NWOG.
    """
    if df_1h is None or len(df_1h) < 5:
        return {}

    try:
        df = df_1h.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            return {}

        df.index = pd.to_datetime(df.index, utc=True)
        now  = datetime.now(timezone.utc)
        today = now.date()

        yesterday_data = df[df.index.date < today]
        today_data     = df[df.index.date == today]

        if len(yesterday_data) < 1 or len(today_data) < 1:
            return {}

        prev_close = round(float(yesterday_data['Close'].iloc[-1]), 5)
        day_open   = round(float(today_data['Open'].iloc[0]), 5)
        gap        = round(day_open - prev_close, 5)
        gap_pct    = round((gap / prev_close) * 100, 4) if prev_close != 0 else 0

        if abs(gap_pct) < 0.005:
            return {}

        current = round(float(df['Close'].iloc[-1]), 5)

        return {
            'prev_close': prev_close,
            'day_open':   day_open,
            'gap':        gap,
            'gap_pct':    gap_pct,
            'direction':  'BULLISH' if gap > 0 else 'BEARISH',
            'current':    current,
            'zone_top':   max(prev_close, day_open),
            'zone_bot':   min(prev_close, day_open),
            'filled':     min(prev_close, day_open) <= current <= max(prev_close, day_open),
        }
    except Exception as e:
        logger.error(f'[ICT] NDOG erro: {e}')
        return {}


# ─────────────────────────────
# MMXM — Market Maker Buy/Sell Model
# ─────────────────────────────

def detect_mmxm(df: pd.DataFrame) -> dict:
    """
    Market Maker Model (MMXM):
    Identifica se o preço está na fase de acumulação (buy model)
    ou distribuição (sell model) do market maker.

    Fases do Buy Model:  Consolidação → Raid baixo → Reversão → Rally
    Fases do Sell Model: Consolidação → Raid alto  → Reversão → Queda
    """
    if df is None or len(df) < 40:
        return {}

    try:
        closes = df['Close'].values
        highs  = df['High'].values
        lows   = df['Low'].values

        # ── Fase 1: Consolidação (range lateral) ──
        range_20  = np.max(highs[-40:-20]) - np.min(lows[-40:-20])
        range_now = np.max(highs[-20:])    - np.min(lows[-20:])
        price     = closes[-1]
        prev_avg  = np.mean(closes[-40:-20])

        was_ranging = range_20 < (price * 0.025)  # < 2.5% = lateral

        # ── Fase 2: Raid (liquidez varrida) ──
        raid_low  = lows[-1]  < np.min(lows[-40:-5])   # quebrou mínima anterior
        raid_high = highs[-1] > np.max(highs[-40:-5])  # quebrou máxima anterior

        # ── Fase 3: Reversão (CHoCH após o raid) ──
        # Buy model: raid do low + reversão pra cima
        # Sell model: raid do high + reversão pra baixo
        reversal_up   = closes[-1] > closes[-3] and lows[-1] < lows[-5]
        reversal_down = closes[-1] < closes[-3] and highs[-1] > highs[-5]

        # ── Fase 4: Direção do move ──
        move_up   = closes[-1] > np.mean(closes[-10:])
        move_down = closes[-1] < np.mean(closes[-10:])

        model      = 'INDEFINIDO'
        phase      = 'N/D'
        confidence = 'BAIXA'

        if was_ranging and raid_low and reversal_up and move_up:
            model      = 'BUY MODEL'
            phase      = 'Fase 4 — Rally (entrada compra)'
            confidence = 'ALTA'
        elif was_ranging and raid_low and reversal_up:
            model      = 'BUY MODEL'
            phase      = 'Fase 3 — Reversão (confirmar CHoCH)'
            confidence = 'MODERADA'
        elif was_ranging and raid_low:
            model      = 'BUY MODEL'
            phase      = 'Fase 2 — Raid do Low (aguardar reversão)'
            confidence = 'MODERADA'
        elif was_ranging and raid_high and reversal_down and move_down:
            model      = 'SELL MODEL'
            phase      = 'Fase 4 — Queda (entrada venda)'
            confidence = 'ALTA'
        elif was_ranging and raid_high and reversal_down:
            model      = 'SELL MODEL'
            phase      = 'Fase 3 — Reversão (confirmar CHoCH)'
            confidence = 'MODERADA'
        elif was_ranging and raid_high:
            model      = 'SELL MODEL'
            phase      = 'Fase 2 — Raid do High (aguardar reversão)'
            confidence = 'MODERADA'
        elif was_ranging:
            model  = 'CONSOLIDAÇÃO'
            phase  = 'Fase 1 — Aguardando raid de liquidez'
        else:
            model = 'TENDÊNCIA'
            phase = 'Alta' if closes[-1] > prev_avg else 'Baixa'

        return {
            'model':      model,
            'phase':      phase,
            'confidence': confidence,
            'raid_low':   bool(raid_low),
            'raid_high':  bool(raid_high),
            'was_ranging': bool(was_ranging),
        }
    except Exception as e:
        logger.error(f'[ICT] MMXM erro: {e}')
        return {}


# ─────────────────────────────
# OTE — Optimal Trade Entry (Fibonacci 61.8%–79%)
# ─────────────────────────────

def calc_ote(df: pd.DataFrame) -> dict:
    """
    Optimal Trade Entry: zona de 61.8%–79% de retração Fibonacci
    do último swing significativo. ICT usa como zona de entrada premium.
    """
    if df is None or len(df) < 20:
        return {}

    try:
        highs  = df['High'].values
        lows   = df['Low'].values
        closes = df['Close'].values

        # Swing high e low dos últimos 20 candles
        swing_high = np.max(highs[-20:])
        swing_low  = np.min(lows[-20:])
        current    = closes[-1]
        swing_range = swing_high - swing_low

        if swing_range < 1e-8:
            return {}

        # Zonas OTE
        fib_618  = round(swing_high - (swing_range * 0.618), 5)
        fib_705  = round(swing_high - (swing_range * 0.705), 5)
        fib_79   = round(swing_high - (swing_range * 0.79),  5)

        # OTE de venda (retração de alta)
        sell_ote_top = round(swing_low + (swing_range * 0.79),  5)
        sell_ote_bot = round(swing_low + (swing_range * 0.618), 5)

        in_buy_ote  = fib_79  <= current <= fib_618
        in_sell_ote = sell_ote_bot <= current <= sell_ote_top

        trend_up = closes[-1] > closes[-10]

        return {
            'swing_high': round(swing_high, 5),
            'swing_low':  round(swing_low, 5),
            'buy_ote': {
                'top':    fib_618,
                'mid':    fib_705,
                'bot':    fib_79,
                'active': in_buy_ote,
            },
            'sell_ote': {
                'top':    sell_ote_top,
                'bot':    sell_ote_bot,
                'active': in_sell_ote,
            },
            'current':  round(current, 5),
            'in_ote':   in_buy_ote or in_sell_ote,
            'ote_type': 'COMPRA' if in_buy_ote else ('VENDA' if in_sell_ote else 'FORA DA ZONA'),
        }
    except Exception as e:
        logger.error(f'[ICT] OTE erro: {e}')
        return {}


# ─────────────────────────────
# LIQUIDITY POOLS
# ─────────────────────────────

def find_liquidity_pools(df: pd.DataFrame) -> dict:
    """
    Identifica pools de liquidez: Equal Highs/Lows (EQH/EQL)
    onde stops ficam acumulados. Alvos prioritários do market maker.
    """
    if df is None or len(df) < 20:
        return {}

    try:
        highs  = df['High'].values
        lows   = df['Low'].values
        closes = df['Close'].values
        current = closes[-1]

        threshold = current * 0.001  # 0.1% de tolerância para "iguais"

        eqh = []  # Equal Highs (sell-side liquidity)
        eql = []  # Equal Lows  (buy-side liquidity)

        for i in range(5, len(df) - 1):
            for j in range(i - 5, i):
                # Equal Highs
                if abs(highs[i] - highs[j]) < threshold:
                    level = round((highs[i] + highs[j]) / 2, 5)
                    if level > current and level not in eqh:
                        eqh.append(level)

                # Equal Lows
                if abs(lows[i] - lows[j]) < threshold:
                    level = round((lows[i] + lows[j]) / 2, 5)
                    if level < current and level not in eql:
                        eql.append(level)

        # Ordena: EQH mais próximos acima, EQL mais próximos abaixo
        eqh = sorted(set(eqh))[:3]
        eql = sorted(set(eql), reverse=True)[:3]

        return {
            'buy_side':  eql,   # Liquidity abaixo (stops de comprados = alvo de venda)
            'sell_side': eqh,   # Liquidity acima  (stops de vendidos = alvo de compra)
            'current':   round(current, 5),
            'nearest_target_up':   eqh[0] if eqh else None,
            'nearest_target_down': eql[0] if eql else None,
        }
    except Exception as e:
        logger.error(f'[ICT] Liquidity pools erro: {e}')
        return {}


# ─────────────────────────────
# ANÁLISE ICT COMPLETA
# ─────────────────────────────

def analyze_ict(asset: str, timeframes_data: dict) -> dict:
    """
    Análise ICT completa para um ativo.
    Usa D1 para MMXM/OTE e 1H para killzones/NWOG/NDOG.
    """
    df_d1 = timeframes_data.get('D1')
    df_4h = timeframes_data.get('4H')
    df_1h = timeframes_data.get('1H')

    result = {
        'asset':      asset,
        'killzone':   get_current_killzone(),
        'prime_kz':   is_prime_killzone(asset),
        'asian':      calc_asian_range(df_1h),
        'nwog':       calc_nwog(df_1h),
        'ndog':       calc_ndog(df_1h),
        'mmxm':       detect_mmxm(df_d1 if df_d1 is not None else df_4h),
        'ote':        calc_ote(df_4h if df_4h is not None else df_d1),
        'liquidity':  find_liquidity_pools(df_4h if df_4h is not None else df_d1),
    }

    return result


# ─────────────────────────────
# SCORE PARA CONFLUENCE ENGINE
# ─────────────────────────────

def ict_confluence_score(ict: dict, direction: str) -> tuple[int, list]:
    """
    Converte análise ICT em pontos para o confluence_engine.

    Returns:
        (score_bull_add, score_bear_add, factors)
    """
    score_bull = 0
    score_bear = 0
    factors    = []

    # ── Killzone premium ──
    if ict.get('prime_kz'):
        kz_names = [z['name'] for z in ict['killzone'].get('zones', [])]
        factors.append(f"ICT Killzone premium: {', '.join(kz_names)} (+1)")
        if direction == 'COMPRA':
            score_bull += 1
        elif direction == 'VENDA':
            score_bear += 1

    # ── MMXM ──
    mmxm = ict.get('mmxm', {})
    model = mmxm.get('model', '')
    conf  = mmxm.get('confidence', 'BAIXA')
    pts   = {'ALTA': 2, 'MODERADA': 1, 'BAIXA': 0}.get(conf, 0)

    if 'BUY MODEL' in model and pts > 0:
        score_bull += pts
        factors.append(f"ICT MMXM: {model} — {mmxm.get('phase')} (+{pts})")
    elif 'SELL MODEL' in model and pts > 0:
        score_bear += pts
        factors.append(f"ICT MMXM: {model} — {mmxm.get('phase')} (+{pts})")

    # ── OTE ──
    ote = ict.get('ote', {})
    if ote.get('in_ote'):
        ote_type = ote.get('ote_type')
        if ote_type == 'COMPRA':
            score_bull += 2
            factors.append(f"ICT OTE zona de compra ativa (61.8%-79%) (+2)")
        elif ote_type == 'VENDA':
            score_bear += 2
            factors.append(f"ICT OTE zona de venda ativa (61.8%-79%) (+2)")

    # ── NWOG ──
    nwog = ict.get('nwog', {})
    if nwog and not nwog.get('gap_filled'):
        nwog_dir = nwog.get('direction', '')
        if nwog_dir == 'BULLISH' and direction == 'COMPRA':
            score_bull += 1
            factors.append(f"ICT NWOG gap bullish não preenchido (+1)")
        elif nwog_dir == 'BEARISH' and direction == 'VENDA':
            score_bear += 1
            factors.append(f"ICT NWOG gap bearish não preenchido (+1)")

    return score_bull, score_bear, factors


# ─────────────────────────────
# FORMATAÇÃO
# ─────────────────────────────

def format_ict_message(ict: dict) -> str:
    """Formata bloco ICT para inserir na mensagem do ativo."""
    lines = ["─────────────────────────────", "🎯 ICT CONCEPTS"]

    # Killzone
    kz = ict.get('killzone', {})
    if kz.get('active'):
        zones = ', '.join([f"{z['emoji']} {z['name']}" for z in kz['zones']])
        prime = ' ⭐ PRIME' if ict.get('prime_kz') else ''
        lines.append(f"Killzone: {zones}{prime}")
    else:
        nxt = kz.get('next', {})
        if nxt:
            lines.append(f"Killzone: Fora de zona | Próxima: {nxt['emoji']} {nxt['name']} em {nxt['hours_until']}h")

    # Asian Range
    asian = ict.get('asian', {})
    if asian:
        broken = ''
        if asian.get('broken_high'):
            broken = ' ⬆️ ROMPEU HIGH'
        elif asian.get('broken_low'):
            broken = ' ⬇️ ROMPEU LOW'
        lines.append(f"Asian Range: {asian.get('low')} — {asian.get('high')}{broken}")

    # NWOG
    nwog = ict.get('nwog', {})
    if nwog:
        filled = '✅ Preenchido' if nwog.get('gap_filled') else '⏳ Aberto'
        lines.append(f"NWOG ({nwog.get('direction')}): {nwog.get('zone_bot')} — {nwog.get('zone_top')} | {filled}")

    # NDOG
    ndog = ict.get('ndog', {})
    if ndog:
        filled = '✅' if ndog.get('filled') else '⏳'
        lines.append(f"NDOG ({ndog.get('direction')}): {ndog.get('zone_bot')} — {ndog.get('zone_top')} {filled}")

    # MMXM
    mmxm = ict.get('mmxm', {})
    if mmxm and mmxm.get('model') != 'INDEFINIDO':
        conf_emoji = {'ALTA': '🟢', 'MODERADA': '🟡', 'BAIXA': '🔴'}.get(mmxm.get('confidence'), '')
        lines.append(f"MMXM: {mmxm.get('model')} {conf_emoji}")
        lines.append(f"  Fase: {mmxm.get('phase')}")

    # OTE
    ote = ict.get('ote', {})
    if ote:
        if ote.get('in_ote'):
            lines.append(f"OTE: ⭐ DENTRO DA ZONA ({ote.get('ote_type')}) — {ote['buy_ote']['bot'] if ote.get('ote_type')=='COMPRA' else ote['sell_ote']['bot']} — {ote['buy_ote']['top'] if ote.get('ote_type')=='COMPRA' else ote['sell_ote']['top']}")
        else:
            buy = ote.get('buy_ote', {})
            lines.append(f"OTE Compra: {buy.get('bot')} — {buy.get('top')}")

    # Liquidity
    liq = ict.get('liquidity', {})
    if liq:
        up   = liq.get('nearest_target_up')
        down = liq.get('nearest_target_down')
        if up:
            lines.append(f"Liquidez acima (alvo): {up}")
        if down:
            lines.append(f"Liquidez abaixo (alvo): {down}")

    return '\n'.join(lines)
