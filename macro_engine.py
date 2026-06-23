"""
MACRO ENGINE — Bot V11
Puxa dados econômicos reais via FRED API
Fed, CPI, Yields, Emprego, etc.
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Optional
import os

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# Séries FRED — IDs corretos e testados
FRED_SERIES = {
    'CPI':          'CPIAUCSL',     # CPI All Items
    'CORE_CPI':     'CPILFESL',     # Core CPI (sem food/energy)
    'PCE':          'PCEPI',        # PCE inflation
    'CORE_PCE':     'PCEPILFE',     # Core PCE
    'FED_RATE':     'FEDFUNDS',     # Taxa do Fed
    'UNEMPLOYMENT': 'UNRATE',       # Desemprego
    'NFP':          'PAYEMS',       # Non-Farm Payrolls
    'GDP':          'GDP',          # PIB
    'YIELD_10Y':    'DGS10',        # Yield 10Y
    'YIELD_2Y':     'DGS2',         # Yield 2Y
    'YIELD_REAL':   'DFII10',       # Yield real 10Y (TIPS)
    'DXY':          'DTWEXBGS',     # Dólar Index (broad)
}


def _fred_fetch(series_id: str, fred_key: str, limit: int = 5) -> list:
    """Busca observações de uma série FRED."""
    try:
        params = {
            'series_id':        series_id,
            'api_key':          fred_key,
            'file_type':        'json',
            'sort_order':       'desc',
            'limit':            limit,
            'observation_start': (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
        }
        r = requests.get(FRED_BASE, params=params, timeout=10)
        data = r.json()
        obs = data.get('observations', [])
        # Filtra valores válidos
        valid = [o for o in obs if o.get('value') not in ('.', '', None)]
        return valid
    except Exception as e:
        logger.error(f"FRED erro ({series_id}): {e}")
        return []


def _get_latest(series_id: str, fred_key: str) -> Optional[float]:
    """Retorna o valor mais recente de uma série."""
    obs = _fred_fetch(series_id, fred_key, limit=2)
    if obs:
        try:
            return float(obs[0]['value'])
        except:
            return None
    return None


def _get_yoy_change(series_id: str, fred_key: str) -> Optional[float]:
    """Calcula variação YoY de uma série."""
    obs = _fred_fetch(series_id, fred_key, limit=15)
    if len(obs) >= 13:
        try:
            current = float(obs[0]['value'])
            year_ago = float(obs[12]['value'])
            return round(((current - year_ago) / year_ago) * 100, 2)
        except:
            return None
    return None


def analyze_macro(fred_key: str) -> dict:
    """Análise macro completa via FRED."""
    result = {}

    # --- FED ---
    fed_rate = _get_latest('FEDFUNDS', fred_key)
    result['fed_rate'] = fed_rate

    # Hawkish/Dovish baseado na taxa e tendência
    fed_obs = _fred_fetch('FEDFUNDS', fred_key, limit=6)
    if len(fed_obs) >= 3:
        rates = [float(o['value']) for o in fed_obs[:3]]
        if rates[0] > rates[2]:
            result['fed_stance'] = 'HAWKISH'
            result['fed_stance_emoji'] = '🔴'
        elif rates[0] < rates[2]:
            result['fed_stance'] = 'DOVISH'
            result['fed_stance_emoji'] = '🟢'
        else:
            result['fed_stance'] = 'NEUTRO'
            result['fed_stance_emoji'] = '🟡'
    else:
        result['fed_stance'] = 'N/D'
        result['fed_stance_emoji'] = '⚪'

    # --- INFLAÇÃO ---
    # CPI YoY direto (série já em percentual)
    cpi_yoy  = _get_latest('CPALTT01USM657N', fred_key)
    # Core CPI YoY direto
    core_cpi = _get_latest('CORESTICKM159SFRBATL', fred_key)
    result['cpi_yoy']  = cpi_yoy
    result['core_cpi'] = core_cpi

    # --- EMPREGO ---
    unemployment = _get_latest('UNRATE', fred_key)
    result['unemployment'] = unemployment

    # NFP — variação mensal
    nfp_obs = _fred_fetch('PAYEMS', fred_key, limit=2)
    if len(nfp_obs) >= 2:
        try:
            nfp_change = (float(nfp_obs[0]['value']) - float(nfp_obs[1]['value'])) * 1000
            result['nfp'] = round(nfp_change)
        except:
            result['nfp'] = None
    else:
        result['nfp'] = None

    # --- YIELDS ---
    yield_10y = _get_latest('DGS10', fred_key)
    yield_2y  = _get_latest('DGS2', fred_key)
    yield_real = _get_latest('DFII10', fred_key)

    result['yield_10y']  = yield_10y
    result['yield_2y']   = yield_2y
    result['yield_real'] = yield_real

    # Curva de juros: invertida ou normal
    if yield_10y and yield_2y:
        spread = round(yield_10y - yield_2y, 2)
        result['yield_spread'] = spread
        result['yield_curve'] = 'INVERTIDA ⚠️' if spread < 0 else 'NORMAL ✅'
    else:
        result['yield_spread'] = None
        result['yield_curve'] = 'N/D'

    # --- AMBIENTE MACRO ---
    # Risk-on vs Risk-off
    risk_score = 0

    if result.get('fed_stance') == 'HAWKISH':
        risk_score -= 2
    elif result.get('fed_stance') == 'DOVISH':
        risk_score += 2

    if cpi_yoy and cpi_yoy > 3.0:
        risk_score -= 1  # Inflação alta = Fed restritivo = risk-off

    if yield_real and yield_real > 1.5:
        risk_score -= 1  # Real yields altos = risk-off

    if unemployment and unemployment < 4.5:
        risk_score += 1  # Emprego forte = risk-on

    if risk_score <= -2:
        result['risk_environment'] = 'RISK-OFF 🔴'
        result['usd_bias'] = 'FORTE ✅'
        result['jpy_bias'] = 'FORTE ✅'
        result['commodity_bias'] = 'FRACO ❌'
    elif risk_score >= 2:
        result['risk_environment'] = 'RISK-ON 🟢'
        result['usd_bias'] = 'FRACO ❌'
        result['jpy_bias'] = 'FRACO ❌'
        result['commodity_bias'] = 'FORTE ✅'
    else:
        result['risk_environment'] = 'NEUTRO 🟡'
        result['usd_bias'] = 'NEUTRO'
        result['jpy_bias'] = 'NEUTRO'
        result['commodity_bias'] = 'NEUTRO'

    result['risk_score'] = risk_score
    return result


def format_macro_message(macro: dict) -> str:
    """Formata mensagem macro pro Telegram."""
    now = datetime.utcnow().strftime('%d %b %Y | %H:%M UTC')

    fed_rate  = f"{macro['fed_rate']:.2f}%" if macro.get('fed_rate') else 'N/D'
    cpi       = f"{macro['cpi_yoy']:.1f}% YoY" if macro.get('cpi_yoy') else 'N/D'
    core_cpi  = f"{macro['core_cpi']:.1f}%" if macro.get('core_cpi') else 'N/D'
    unemp     = f"{macro['unemployment']:.1f}%" if macro.get('unemployment') else 'N/D'
    nfp       = f"{macro['nfp']:,}k" if macro.get('nfp') else 'N/D'
    y10       = f"{macro['yield_10y']:.2f}%" if macro.get('yield_10y') else 'N/D'
    y2        = f"{macro['yield_2y']:.2f}%" if macro.get('yield_2y') else 'N/D'
    y_real    = f"{macro['yield_real']:.2f}%" if macro.get('yield_real') else 'N/D'
    spread    = f"{macro['yield_spread']:.2f}%" if macro.get('yield_spread') is not None else 'N/D'

    msg = f"""📊 MACRO GLOBAL — {now}

─────────────────────────────
🏦 FED (Banco Central dos EUA)
Juros em {fed_rate} — {macro.get('fed_stance', 'N/D')} {macro.get('fed_stance_emoji', '')}

📈 Inflação
CPI: {cpi}
Núcleo: {core_cpi}

💼 Emprego
NFP: {nfp}
Desemprego: {unemp}

📉 Yields (Juros dos Títulos)
10Y: {y10} | 2Y: {y2}
Real (TIPS): {y_real}
Curva: {macro.get('yield_curve', 'N/D')} (spread: {spread})

─────────────────────────────
⚡ AMBIENTE AGORA
{macro.get('risk_environment', 'N/D')}

✅ USD: {macro.get('usd_bias', 'N/D')}
✅ JPY: {macro.get('jpy_bias', 'N/D')}
❌ Commodities: {macro.get('commodity_bias', 'N/D')}
─────────────────────────────"""

    return msg
