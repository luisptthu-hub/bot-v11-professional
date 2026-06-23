"""
CONFLUENCE ENGINE — Bot V11
Calcula score de confluência e gera recomendação final
"""

import logging

logger = logging.getLogger(__name__)


def calculate_confluence(asset: str, macro: dict, tech: dict, intermarket: dict,
                         ml: dict = None, ict: dict = None, session: dict = None) -> dict:
    """
    Calcula confluência entre macro, técnico e intermarket.
    Retorna score 0-100 e recomendação.
    """
    score_bull = 0  # pontos altistas
    score_bear = 0  # pontos baixistas
    factors    = []

    # ─── MACRO ───
    fed_stance = macro.get('fed_stance', '')
    risk_env   = macro.get('risk_environment', '')
    usd_bias   = macro.get('usd_bias', '')
    jpy_bias   = macro.get('jpy_bias', '')

    if asset == 'EURUSD':
        if fed_stance == 'HAWKISH':
            score_bear += 3
            factors.append('Fed hawkish → USD forte → EUR fraco (-3)')
        elif fed_stance == 'DOVISH':
            score_bull += 3
            factors.append('Fed dovish → USD fraco → EUR forte (+3)')

        if 'RISK-OFF' in risk_env:
            score_bear += 2
            factors.append('Risk-off → fuga pro USD (-2)')
        elif 'RISK-ON' in risk_env:
            score_bull += 2
            factors.append('Risk-on → fluxo pra risco (+2)')

    elif asset == 'USDJPY':
        if fed_stance == 'HAWKISH':
            score_bull += 3
            factors.append('Fed hawkish → USD forte → USDJPY sobe (+3)')
        elif fed_stance == 'DOVISH':
            score_bear += 3
            factors.append('Fed dovish → USD fraco → USDJPY cai (-3)')

        yield_real = macro.get('yield_real')
        if yield_real and yield_real > 1.0:
            score_bull += 2
            factors.append(f'Yields reais altos ({yield_real:.2f}%) → USDJPY sobe (+2)')
        elif yield_real and yield_real < 0:
            score_bear += 2
            factors.append(f'Yields reais negativos ({yield_real:.2f}%) → USDJPY cai (-2)')

    elif asset == 'XAUUSD':
        yield_real = macro.get('yield_real')
        if yield_real and yield_real > 1.5:
            score_bear += 3
            factors.append(f'Yields reais altos ({yield_real:.2f}%) → Ouro sob pressão (-3)')
        elif yield_real and yield_real < 0:
            score_bull += 3
            factors.append(f'Yields reais negativos → Ouro favorecido (+3)')

        if 'FORTE' in usd_bias:
            score_bear += 2
            factors.append('USD forte → Ouro fraco (-2)')

        cpi = macro.get('cpi_yoy')
        if cpi and cpi > 4.0:
            score_bull += 1
            factors.append(f'Inflação alta ({cpi:.1f}%) → Ouro como hedge (+1)')

        if 'RISK-OFF' in risk_env:
            score_bull += 1
            factors.append('Risk-off → Safe haven parcial (+1)')

    elif asset == 'BTCUSD':
        if 'RISK-OFF' in risk_env:
            score_bear += 3
            factors.append('Risk-off → BTC sofre (-3)')
        elif 'RISK-ON' in risk_env:
            score_bull += 3
            factors.append('Risk-on → BTC beneficiado (+3)')

        if fed_stance == 'HAWKISH':
            score_bear += 2
            factors.append('Fed hawkish → Liquidez escassa → BTC fraco (-2)')
        elif fed_stance == 'DOVISH':
            score_bull += 2
            factors.append('Fed dovish → Liquidez abundante → BTC forte (+2)')

        cpi = macro.get('cpi_yoy')
        if cpi and cpi > 4.0:
            score_bull += 1
            factors.append(f'Inflação alta → BTC como hedge (longo prazo) (+1)')

    # ─── TÉCNICO ───
    bias  = tech.get('bias', '')
    trend = tech.get('trend', '')

    if bias == 'COMPRA':
        score_bull += 2
        factors.append('Tendência técnica D1: ALTA (+2)')
    elif bias == 'VENDA':
        score_bear += 2
        factors.append('Tendência técnica D1: BAIXA (+2)')

    # Wyckoff D1
    d1 = tech.get('timeframes', {}).get('D1', {})
    wyc = d1.get('wyckoff', '')
    if 'ACUMULAÇÃO' in wyc:
        score_bull += 2
        factors.append('Wyckoff D1: Acumulação (+2)')
    elif 'DISTRIBUIÇÃO' in wyc:
        score_bear += 2
        factors.append('Wyckoff D1: Distribuição (+2)')

    # BOS H1
    h1  = tech.get('timeframes', {}).get('1H', {})
    bos = h1.get('bos', {}).get('type')
    if bos == 'bullish':
        score_bull += 1
        factors.append('BOS altista no H1 (+1)')
    elif bos == 'bearish':
        score_bear += 1
        factors.append('BOS baixista no H1 (+1)')

    # ─── ML ENGINE ───
    if ml:
        ml_dir  = ml.get('direction', 'NEUTRO')
        ml_conf = ml.get('confidence', 'BAIXA')
        ml_prob = ml.get('probability', 50.0)
        base    = {'ALTA': 3, 'MODERADA': 2, 'BAIXA': 1}.get(ml_conf, 0)

        if ml_dir == 'COMPRA':
            score_bull += base
            factors.append(f'ML Random Forest: COMPRA {ml_prob:.0f}% (confiança {ml_conf}) (+{base})')
        elif ml_dir == 'VENDA':
            score_bear += base
            factors.append(f'ML Random Forest: VENDA {100-ml_prob:.0f}% (confiança {ml_conf}) (+{base})')

    # ─── ICT ENGINE ───
    if ict:
        from ict_engine import ict_confluence_score
        direction_now = 'COMPRA' if score_bull > score_bear else 'VENDA'
        ict_bull, ict_bear, ict_factors = ict_confluence_score(ict, direction_now)
        score_bull += ict_bull
        score_bear += ict_bear
        factors.extend(ict_factors)

    # ─── SESSION ENGINE ───
    if session:
        from session_engine import session_confluence_score
        direction_now = 'COMPRA' if score_bull > score_bear else 'VENDA'
        sess_bull, sess_bear, sess_factors = session_confluence_score(session, direction_now)
        score_bull += sess_bull
        score_bear += sess_bear
        factors.extend(sess_factors)

    # ─── SCORE FINAL ───
    total = score_bull + score_bear
    if total == 0:
        confluence_pct = 50
        direction = 'NEUTRO'
    elif score_bull > score_bear:
        confluence_pct = min(int((score_bull / total) * 100), 99)
        direction = 'COMPRA'
    else:
        confluence_pct = min(int((score_bear / total) * 100), 99)
        direction = 'VENDA'

    # Recomendação
    if confluence_pct >= 70:
        recommendation = f'SETUP FORTE — AGUARDAR TRIGGER ✅'
        rec_emoji = '✅'
    elif confluence_pct >= 55:
        recommendation = f'SETUP MODERADO — MONITORAR ⚠️'
        rec_emoji = '⚠️'
    else:
        recommendation = f'SEM SETUP CLARO — AGUARDAR 🚫'
        rec_emoji = '🚫'

    return {
        'asset':          asset,
        'direction':      direction,
        'confluence_pct': confluence_pct,
        'recommendation': recommendation,
        'rec_emoji':      rec_emoji,
        'factors':        factors,
        'score_bull':     score_bull,
        'score_bear':     score_bear,
    }


def format_asset_message(asset: str, price_data: dict, macro: dict,
                         tech: dict, confluence: dict) -> str:
    """Formata mensagem completa de análise por ativo."""

    # Emojis por ativo
    emojis = {
        'XAUUSD': '🥇',
        'EURUSD': '💶',
        'USDJPY': '💴',
        'BTCUSD': '₿',
    }
    emoji = emojis.get(asset, '📊')

    price   = price_data.get('price', 'N/D')
    chg     = price_data.get('change_pct', 0)
    chg_dir = price_data.get('direction', '')

    direction = confluence.get('direction', 'N/D')
    conf_pct  = confluence.get('confluence_pct', 0)
    rec       = confluence.get('recommendation', 'N/D')

    # Técnico D1
    d1      = tech.get('timeframes', {}).get('D1', {})
    sr      = d1.get('sr', {})
    wyckoff = d1.get('wyckoff', 'N/D')
    bos_d1  = d1.get('bos', {}).get('signal', 'N/D')

    res_list = sr.get('resistances', [])
    sup_list = sr.get('supports', [])
    res_str  = str(res_list[0]) if res_list else 'N/D'
    sup_str  = str(sup_list[0]) if sup_list else 'N/D'

    # FVG D1
    fvg_str = 'N/D'
    if d1.get('fvgs'):
        fvg     = d1['fvgs'][-1]
        fvg_str = f"{fvg['type']}: {fvg['bot']} — {fvg['top']}"

    # Por que sobe ou cai
    why = _get_macro_reason(asset, macro)

    trigger = _get_trigger(direction, res_str, sup_str, fvg_str)

    msg = f"""{emoji} {asset} — Análise Completa

─────────────────────────────
📌 SITUAÇÃO ATUAL
Preço: {price} {chg_dir} ({chg:+.2f}%)

🧠 POR QUÊ?
{why}

─────────────────────────────
📊 GRÁFICO (D1)
Tendência: {tech.get('trend', 'N/D')}
Wyckoff: {wyckoff}
Estrutura: {bos_d1}

Resistência: {res_str}
Suporte: {sup_str}
FVG: {fvg_str}

─────────────────────────────
⚡ CONFLUÊNCIA: {conf_pct}% {confluence.get('rec_emoji', '')}

🎯 VIÉS: {direction}
{rec}

🔔 TRIGGER A ESPERAR:
{trigger}
─────────────────────────────"""

    return msg


def _get_macro_reason(asset: str, macro: dict) -> str:
    """Gera explicação macro simples pra cada ativo."""
    fed   = macro.get('fed_stance', 'N/D')
    risk  = macro.get('risk_environment', 'N/D')
    cpi   = macro.get('cpi_yoy')
    yield_real = macro.get('yield_real')

    cpi_str   = f"{cpi:.1f}%" if cpi else 'N/D'
    yield_str = f"{yield_real:.2f}%" if yield_real else 'N/D'

    reasons = {
        'EURUSD': f"Fed {fed} → Dólar forte\nECB cortando juros → Euro fraco\nRisco: {risk}",
        'USDJPY': f"Fed {fed} → Dólar forte\nBoJ mantém juros baixos → Yen fraco\nYields reais: {yield_str}",
        'XAUUSD': f"Yields reais: {yield_str} (alto = ruim pro ouro)\nDólar: {macro.get('usd_bias', 'N/D')}\nInflação: {cpi_str}",
        'BTCUSD': f"Ambiente: {risk}\nFed {fed} → Liquidez {'escassa' if fed == 'HAWKISH' else 'abundante'}\nInflação: {cpi_str}",
    }
    return reasons.get(asset, 'N/D')


def format_summary_message(results: list) -> str:
    """Formata resumo dos 4 ativos."""
    from datetime import datetime
    now = datetime.utcnow().strftime('%d %b %Y | %H:%M UTC')

    lines = [f"📋 RESUMO — {now}", "─────────────────────────────"]

    for r in results:
        asset  = r.get('asset', '')
        conf   = r.get('confluence_pct', 0)
        direc  = r.get('direction', 'N/D')
        emoji  = r.get('rec_emoji', '')
        price  = r.get('price', 'N/D')

        lines.append(f"{asset}: {price} | {direc} | {conf}% {emoji}")

    lines.append("─────────────────────────────")
    lines.append("Use /xau /eur /jpy /btc para análise detalhada")

    return '\n'.join(lines)


def _get_trigger(direction: str, resistance: str, support: str, fvg: str) -> str:
    """Gera explicação do trigger a esperar baseado no viés."""
    if direction == 'VENDA':
        return (
            f"• Preço subir até resistência ({resistance}) ou FVG\n"
            f"• Aparecer candle de rejeição (wick longo, engolfo baixista) no H1 ou M15\n"
            f"• BOS baixista confirmado no H1\n"
            f"• Só então considerar entrada vendida"
        )
    elif direction == 'COMPRA':
        return (
            f"• Preço cair até suporte ({support}) ou FVG\n"
            f"• Aparecer candle de reversão (wick longo, engolfo altista) no H1 ou M15\n"
            f"• BOS altista confirmado no H1\n"
            f"• Só então considerar entrada comprada"
        )
    else:
        return (
            f"• Sem viés claro no momento\n"
            f"• Aguardar definição de direção no D1\n"
            f"• Não operar até confluência acima de 60%"
        )
