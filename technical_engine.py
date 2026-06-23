"""
TECHNICAL ENGINE — Bot V11
SMC, ICT, Wyckoff, Suporte/Resistência
Analisa D1 → 4H → 2H → 1H → 15M → 5M → 1M
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────
# WYCKOFF
# ─────────────────────────────

def detect_wyckoff(df: pd.DataFrame) -> str:
    """Detecta fase Wyckoff: Acumulação, Distribuição ou Tendência."""
    if df is None or len(df) < 30:
        return 'N/D'

    closes = df['Close'].values
    volumes = df['Volume'].values if 'Volume' in df.columns else None

    # Tendência recente (últimos 20 candles)
    recent = closes[-20:]
    trend = recent[-1] - recent[0]
    high_20 = np.max(recent)
    low_20  = np.min(recent)
    range_20 = high_20 - low_20

    # Lateral = range pequeno em relação ao preço
    lateral_threshold = closes[-1] * 0.02  # 2% de range = lateral

    if range_20 < lateral_threshold:
        # Está lateral — verifica se acumula ou distribui
        # Acumulação = vem de baixa e estabiliza
        prev_trend = closes[-30] - closes[-20]
        if prev_trend < 0:
            return 'ACUMULAÇÃO'
        else:
            return 'DISTRIBUIÇÃO'
    elif trend > 0:
        return 'TENDÊNCIA DE ALTA'
    else:
        return 'TENDÊNCIA DE BAIXA'


# ─────────────────────────────
# SUPORTE E RESISTÊNCIA
# ─────────────────────────────

def find_support_resistance(df: pd.DataFrame, n: int = 3) -> dict:
    """Encontra níveis de suporte e resistência chave."""
    if df is None or len(df) < 20:
        return {'supports': [], 'resistances': []}

    highs  = df['High'].values
    lows   = df['Low'].values
    closes = df['Close'].values

    supports    = []
    resistances = []

    for i in range(n, len(df) - n):
        # Suporte: low mais baixo que os n vizinhos
        if lows[i] == min(lows[i-n:i+n+1]):
            supports.append(round(lows[i], 5))

        # Resistência: high mais alto que os n vizinhos
        if highs[i] == max(highs[i-n:i+n+1]):
            resistances.append(round(highs[i], 5))

    # Remove duplicatas próximas (dentro de 0.1%)
    current_price = closes[-1]

    def dedupe(levels, threshold=0.001):
        result = []
        for lvl in sorted(set(levels)):
            if not result or abs(lvl - result[-1]) / current_price > threshold:
                result.append(lvl)
        return result

    supports    = dedupe(supports)
    resistances = dedupe(resistances)

    # Suportes: apenas ABAIXO do preço atual
    supports    = sorted([s for s in supports    if s < current_price], reverse=True)[:3]
    # Resistencias: apenas ACIMA do preço atual
    resistances = sorted([r for r in resistances if r > current_price])[:3]

    return {
        'supports':    supports,
        'resistances': resistances,
        'current':     round(current_price, 5),
    }


# ─────────────────────────────
# SMC — ORDER BLOCKS E FVG
# ─────────────────────────────

def find_order_blocks(df: pd.DataFrame) -> list:
    """Encontra Order Blocks relevantes."""
    if df is None or len(df) < 10:
        return []

    obs = []
    closes = df['Close'].values
    opens  = df['Open'].values
    highs  = df['High'].values
    lows   = df['Low'].values

    for i in range(1, len(df) - 2):
        # OB de alta: candle baixista seguido de forte alta
        if closes[i] < opens[i]:  # candle baixista
            if closes[i+1] > highs[i]:  # próximo candle quebra o high
                obs.append({
                    'type':  'BULLISH OB',
                    'high':  round(highs[i], 5),
                    'low':   round(lows[i], 5),
                    'index': i,
                })

        # OB de baixa: candle altista seguido de forte queda
        if closes[i] > opens[i]:  # candle altista
            if closes[i+1] < lows[i]:  # próximo candle quebra o low
                obs.append({
                    'type':  'BEARISH OB',
                    'high':  round(highs[i], 5),
                    'low':   round(lows[i], 5),
                    'index': i,
                })

    # Retorna os 3 mais recentes
    return obs[-3:] if obs else []


def find_fvg(df: pd.DataFrame) -> list:
    """Encontra Fair Value Gaps (imbalances)."""
    if df is None or len(df) < 5:
        return []

    fvgs   = []
    highs  = df['High'].values
    lows   = df['Low'].values
    closes = df['Close'].values

    for i in range(1, len(df) - 1):
        # FVG altista: low do candle atual > high de 2 candles atrás
        if lows[i+1] > highs[i-1]:
            fvgs.append({
                'type': 'BULLISH FVG',
                'top':  round(lows[i+1], 5),
                'bot':  round(highs[i-1], 5),
            })

        # FVG baixista: high do candle atual < low de 2 candles atrás
        if highs[i+1] < lows[i-1]:
            fvgs.append({
                'type': 'BEARISH FVG',
                'top':  round(lows[i-1], 5),
                'bot':  round(highs[i+1], 5),
            })

    return fvgs[-3:] if fvgs else []


def detect_bos_choch(df: pd.DataFrame) -> dict:
    """Detecta Break of Structure (BOS) e Change of Character (CHoCH)."""
    if df is None or len(df) < 20:
        return {'signal': 'N/D', 'type': None}

    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values

    # Últimos 20 candles
    recent_high = np.max(highs[-20:-5])
    recent_low  = np.min(lows[-20:-5])
    current     = closes[-1]

    if current > recent_high:
        return {'signal': 'BOS ALTISTA 📈', 'type': 'bullish'}
    elif current < recent_low:
        return {'signal': 'BOS BAIXISTA 📉', 'type': 'bearish'}
    else:
        return {'signal': 'Sem BOS/CHoCH', 'type': None}


# ─────────────────────────────
# ANÁLISE COMPLETA DE UM ATIVO
# ─────────────────────────────

def analyze_technical(asset: str, timeframes_data: dict) -> dict:
    """
    Análise técnica completa de um ativo.
    timeframes_data: dict com chaves D1, 4H, 2H, 1H, 15M, 5M, 1M
    """
    result = {
        'asset':      asset,
        'timeframes': {},
        'trend':      None,
        'bias':       None,
    }

    for tf, df in timeframes_data.items():
        if df is None or len(df) < 10:
            continue

        wyckoff = detect_wyckoff(df)
        sr      = find_support_resistance(df)
        obs     = find_order_blocks(df)
        fvgs    = find_fvg(df)
        bos     = detect_bos_choch(df)

        result['timeframes'][tf] = {
            'wyckoff':    wyckoff,
            'sr':         sr,
            'obs':        obs,
            'fvgs':       fvgs,
            'bos':        bos,
            'last_close': round(df['Close'].iloc[-1], 5),
        }

    # Tendência geral baseada no D1
    if 'D1' in result['timeframes']:
        wyc = result['timeframes']['D1']['wyckoff']
        if 'ALTA' in wyc or 'ACUMULAÇÃO' in wyc:
            result['trend'] = 'ALTA ⬆️'
            result['bias']  = 'COMPRA'
        elif 'BAIXA' in wyc or 'DISTRIBUIÇÃO' in wyc:
            result['trend'] = 'BAIXA ⬇️'
            result['bias']  = 'VENDA'
        else:
            result['trend'] = 'LATERAL ↔️'
            result['bias']  = 'NEUTRO'

    return result


def format_technical_summary(tech: dict) -> str:
    """Formata resumo técnico simplificado pro Telegram."""
    asset = tech.get('asset', '')
    trend = tech.get('trend', 'N/D')
    bias  = tech.get('bias', 'N/D')

    lines = [f"📊 TÉCNICO — {asset}", f"Tendência: {trend}", f"Viés: {bias}", ""]

    # D1 e 4H são os mais importantes
    for tf in ['D1', '4H', '1H']:
        tf_data = tech['timeframes'].get(tf)
        if not tf_data:
            continue

        sr      = tf_data['sr']
        wyckoff = tf_data['wyckoff']
        bos     = tf_data['bos']['signal']
        price   = tf_data['last_close']

        res_str = ' | '.join([str(r) for r in tf_data['sr'].get('resistances', [])[:2]])
        sup_str = ' | '.join([str(s) for s in tf_data['sr'].get('supports', [])[:2]])

        lines.append(f"⏱ {tf} — Wyckoff: {wyckoff}")
        lines.append(f"   Preço: {price}")
        lines.append(f"   Resistência: {res_str or 'N/D'}")
        lines.append(f"   Suporte: {sup_str or 'N/D'}")
        lines.append(f"   Estrutura: {bos}")
        lines.append("")

    # FVG do D1
    d1 = tech['timeframes'].get('D1')
    if d1 and d1.get('fvgs'):
        fvg = d1['fvgs'][-1]
        lines.append(f"💧 FVG ({fvg['type']}): {fvg['bot']} — {fvg['top']}")

    return '\n'.join(lines)
