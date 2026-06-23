"""
NEWS ENGINE — Bot V11
Combina Forex Factory RSS + NewsAPI + Dados do Gráfico
Interpretação do que pode acontecer 15min antes das notícias
"""

import requests
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ─────────────────────────────
# ANÁLISE DE SENTIMENTO
# ─────────────────────────────

# Palavras-chave por polaridade (sem dependência de libs externas)
BULLISH_WORDS = [
    'surge', 'surges', 'rally', 'rallies', 'rise', 'rises', 'rose', 'jump', 'jumps',
    'gain', 'gains', 'soar', 'soars', 'climb', 'climbs', 'boost', 'boosted',
    'strong', 'strength', 'bullish', 'upside', 'breakout', 'recovery', 'recovers',
    'high', 'highs', 'record', 'buy', 'buying', 'demand', 'inflow', 'inflows',
    'optimism', 'optimistic', 'positive', 'support', 'outperform', 'above',
    'beat', 'beats', 'exceeds', 'exceeded', 'upgrade', 'upgraded', 'accelerate',
    'dovish', 'cut', 'cuts', 'stimulus', 'easing',  # dovish = bullish pra risco
]

BEARISH_WORDS = [
    'fall', 'falls', 'fell', 'drop', 'drops', 'dropped', 'decline', 'declines',
    'sink', 'sinks', 'tumble', 'tumbles', 'crash', 'crashes', 'plunge', 'plunges',
    'weak', 'weakness', 'bearish', 'downside', 'breakdown', 'selloff', 'sell-off',
    'low', 'lows', 'sell', 'selling', 'outflow', 'outflows', 'pressure', 'pressured',
    'pessimism', 'pessimistic', 'negative', 'resistance', 'underperform', 'below',
    'miss', 'misses', 'missed', 'downgrade', 'downgraded', 'slowdown', 'contraction',
    'hawkish', 'hike', 'hikes', 'tightening',  # hawkish = bearish pra risco
]

UNCERTAINTY_WORDS = [
    'uncertain', 'uncertainty', 'volatile', 'volatility', 'mixed', 'cautious',
    'caution', 'wait', 'waiting', 'pause', 'paused', 'unclear', 'undecided',
    'risk', 'risks', 'concern', 'concerns', 'worry', 'worries', 'fear', 'fears',
    'warning', 'warns', 'threat', 'threats',
]

# Modificadores de intensidade
INTENSIFIERS = ['very', 'highly', 'strongly', 'significantly', 'sharply', 'rapidly', 'massive']
NEGATORS     = ['not', "n't", 'no', 'never', 'neither', 'nor', 'without', 'despite']


def _score_text(text: str) -> dict:
    """
    Pontua sentimento de um texto sem libs externas.
    Retorna score bull, bear, uncertainty e sentimento final.
    """
    if not text:
        return {'bull': 0, 'bear': 0, 'uncertainty': 0, 'sentiment': 'NEUTRO', 'score': 0}

    words = text.lower().split()
    bull  = 0
    bear  = 0
    unc   = 0

    for i, word in enumerate(words):
        # Janela de contexto para negadores (2 palavras antes)
        window = words[max(0, i-2):i]
        negated = any(n in window for n in NEGATORS)

        # Intensificador na janela anterior
        intensified = any(iv in window for iv in INTENSIFIERS)
        weight = 1.5 if intensified else 1.0

        clean = word.strip('.,!?;:()"\'')

        if clean in BULLISH_WORDS:
            if negated:
                bear += weight
            else:
                bull += weight

        elif clean in BEARISH_WORDS:
            if negated:
                bull += weight
            else:
                bear += weight

        elif clean in UNCERTAINTY_WORDS:
            unc += weight

    total = bull + bear + unc
    if total == 0:
        return {'bull': 0, 'bear': 0, 'uncertainty': 0, 'sentiment': 'NEUTRO', 'score': 0}

    score = round((bull - bear) / (total + 1e-10), 3)  # -1 a +1

    if score >= 0.2:
        sentiment = 'BULLISH'
    elif score <= -0.2:
        sentiment = 'BEARISH'
    elif unc / (total + 1e-10) > 0.4:
        sentiment = 'INCERTO'
    else:
        sentiment = 'NEUTRO'

    return {
        'bull':        round(bull, 1),
        'bear':        round(bear, 1),
        'uncertainty': round(unc, 1),
        'sentiment':   sentiment,
        'score':       score,
    }


def analyze_sentiment(articles: list) -> dict:
    """
    Analisa sentimento de uma lista de artigos.
    Retorna sentimento agregado e score médio.
    """
    if not articles:
        return {
            'sentiment':   'NEUTRO',
            'score':       0.0,
            'bull_count':  0,
            'bear_count':  0,
            'total':       0,
            'emoji':       '➡️',
            'strength':    'FRACO',
        }

    scores    = []
    bull_count = 0
    bear_count = 0

    for a in articles:
        text   = f"{a.get('title', '')} {a.get('description', '')}"
        result = _score_text(text)
        scores.append(result['score'])
        if result['sentiment'] == 'BULLISH':
            bull_count += 1
        elif result['sentiment'] == 'BEARISH':
            bear_count += 1

    avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0

    if avg_score >= 0.3:
        sentiment = 'BULLISH'
        emoji     = '📈'
    elif avg_score >= 0.1:
        sentiment = 'LEVEMENTE BULLISH'
        emoji     = '↗️'
    elif avg_score <= -0.3:
        sentiment = 'BEARISH'
        emoji     = '📉'
    elif avg_score <= -0.1:
        sentiment = 'LEVEMENTE BEARISH'
        emoji     = '↘️'
    else:
        sentiment = 'NEUTRO'
        emoji     = '➡️'

    strength = 'FORTE' if abs(avg_score) >= 0.3 else ('MODERADO' if abs(avg_score) >= 0.1 else 'FRACO')

    return {
        'sentiment':   sentiment,
        'score':       avg_score,
        'bull_count':  bull_count,
        'bear_count':  bear_count,
        'total':       len(articles),
        'emoji':       emoji,
        'strength':    strength,
    }


def sentiment_vs_price(sentiment: dict, tech_bias: str) -> str:
    """
    Cruza sentimento das notícias com viés técnico.
    Retorna divergência ou confirmação.
    """
    sent = sentiment.get('sentiment', 'NEUTRO')

    bull_sent = sent in ('BULLISH', 'LEVEMENTE BULLISH')
    bear_sent = sent in ('BEARISH', 'LEVEMENTE BEARISH')
    bull_tech = tech_bias == 'COMPRA'
    bear_tech = tech_bias == 'VENDA'

    if bull_sent and bull_tech:
        return '✅ Sentimento CONFIRMA viés técnico de alta'
    elif bear_sent and bear_tech:
        return '✅ Sentimento CONFIRMA viés técnico de baixa'
    elif bull_sent and bear_tech:
        return '⚠️ DIVERGÊNCIA: Notícias bullish vs técnico baixista'
    elif bear_sent and bull_tech:
        return '⚠️ DIVERGÊNCIA: Notícias bearish vs técnico altista'
    else:
        return '➡️ Sentimento neutro — técnico domina'


# ─────────────────────────────
# FOREX FACTORY RSS
# ─────────────────────────────

FF_RSS = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

IMPACT_EMOJI = {
    'High':   '🔴',
    'Medium': '🟡',
    'Low':    '⚪',
    'Non-Economic': '⚫',
}

# Moedas que afetam nossos ativos
RELEVANT_CURRENCIES = ['USD', 'EUR', 'JPY', 'GBP', 'CNY', 'CHF']

# Eventos de alto impacto para USD que afetam ouro e btc
USD_HIGH_IMPACT = ['Non-Farm', 'NFP', 'CPI', 'Fed', 'FOMC', 'GDP', 'PCE',
                   'Unemployment', 'Retail Sales', 'ISM', 'PMI']


def fetch_forex_factory() -> list:
    """Puxa calendário econômico do Forex Factory via RSS."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(FF_RSS, headers=headers, timeout=15)

        if r.status_code != 200:
            logger.error(f"Forex Factory retornou {r.status_code}")
            return []

        root = ET.fromstring(r.content)
        events = []

        for item in root.findall('.//event'):
            title    = item.findtext('title', '').strip()
            country  = item.findtext('country', '').strip()
            date_str = item.findtext('date', '').strip()
            time_str = item.findtext('time', '').strip()
            impact   = item.findtext('impact', '').strip()
            forecast = item.findtext('forecast', '').strip()
            previous = item.findtext('previous', '').strip()

            # Filtra apenas impacto alto e médio
            if impact not in ['High', 'Medium']:
                continue

            # Filtra moedas relevantes
            if country not in RELEVANT_CURRENCIES:
                continue

            events.append({
                'title':    title,
                'currency': country,
                'date':     date_str,
                'time':     time_str,
                'impact':   impact,
                'forecast': forecast,
                'previous': previous,
            })

        # Ordena por data/hora
        return events[:10]

    except Exception as e:
        logger.error(f"Erro ao puxar Forex Factory: {e}")
        return []


# ─────────────────────────────
# NEWSAPI
# ─────────────────────────────

NEWS_BASE = "https://newsapi.org/v2/everything"

ASSET_QUERIES = {
    'XAUUSD': 'gold price XAU forecast',
    'EURUSD': 'euro dollar EUR USD forex',
    'USDJPY': 'dollar yen USD JPY Bank of Japan',
    'BTCUSD': 'bitcoin BTC price forecast',
}


def fetch_news(asset: str, news_key: str, max_articles: int = 3) -> list:
    """Busca notícias recentes de um ativo."""
    if not news_key:
        return []

    query     = ASSET_QUERIES.get(asset, asset)
    from_date = (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d')

    try:
        params = {
            'q':        query,
            'apiKey':   news_key,
            'language': 'en',
            'sortBy':   'publishedAt',
            'pageSize': max_articles,
            'from':     from_date,
        }
        r    = requests.get(NEWS_BASE, params=params, timeout=10)
        data = r.json()

        if data.get('status') != 'ok':
            return []

        result = []
        for a in data.get('articles', []):
            result.append({
                'title':       a.get('title', '')[:120],
                'description': a.get('description', '')[:200],
                'source':      a.get('source', {}).get('name', ''),
                'published':   a.get('publishedAt', '')[:10],
            })
        return result

    except Exception as e:
        logger.error(f"Erro NewsAPI {asset}: {e}")
        return []


# ─────────────────────────────
# INTERPRETAÇÃO
# ─────────────────────────────

def _interpret_event(event: dict, asset: str, tech: dict) -> str:
    """
    Gera interpretação do que pode acontecer no gráfico
    cruzando evento econômico + dados técnicos.
    """
    title    = event['title']
    currency = event['currency']
    forecast = event.get('forecast', '')
    previous = event.get('previous', '')

    # Dados técnicos
    d1         = tech.get('timeframes', {}).get('D1', {}) if tech else {}
    trend      = tech.get('trend', 'N/D') if tech else 'N/D'
    sr         = d1.get('sr', {})
    res_list   = sr.get('resistances', [])
    sup_list   = sr.get('supports', [])
    fvg_list   = d1.get('fvgs', [])
    price      = d1.get('last_close', 0)

    res = str(res_list[0]) if res_list else 'N/D'
    sup = str(sup_list[0]) if sup_list else 'N/D'
    fvg_str = f"{fvg_list[-1]['bot']} — {fvg_list[-1]['top']}" if fvg_list else 'N/D'

    lines = []

    # Cenário baseado no tipo de evento e ativo
    if 'Non-Farm' in title or 'NFP' in title:
        if asset == 'XAUUSD':
            lines.append(f"NFP abaixo do esperado → USD fraco → Ouro tende a SUBIR")
            lines.append(f"→ Alvo: resistência em {res} ou FVG {fvg_str}")
            lines.append(f"NFP acima do esperado → USD forte → Ouro tende a CAIR")
            lines.append(f"→ Alvo: suporte em {sup}")
        elif asset == 'EURUSD':
            lines.append(f"NFP fraco → USD cai → EUR/USD tende a SUBIR")
            lines.append(f"NFP forte → USD sobe → EUR/USD tende a CAIR para {sup}")
        elif asset == 'USDJPY':
            lines.append(f"NFP forte → USD sobe → USDJPY tende a SUBIR para {res}")
            lines.append(f"NFP fraco → USD cai → USDJPY tende a CAIR para {sup}")
        elif asset == 'BTCUSD':
            lines.append(f"NFP fraco → risk-on → BTC pode SUBIR para {res}")
            lines.append(f"NFP forte → risk-off → BTC pode CAIR para {sup}")

    elif 'CPI' in title or 'Inflation' in title:
        if asset == 'XAUUSD':
            lines.append(f"CPI acima do esperado → inflação alta → Ouro tende a SUBIR")
            lines.append(f"→ Alvo: {res} | FVG: {fvg_str}")
            lines.append(f"CPI abaixo → Fed pode cortar → Ouro neutro a BAIXISTA")
        elif asset in ['EURUSD', 'USDJPY']:
            lines.append(f"CPI USD alto → Fed hawkish → USD FORTE")
            lines.append(f"→ EUR/USD cai | USDJPY sobe")
        elif asset == 'BTCUSD':
            lines.append(f"CPI alto → Fed hawkish → BTC sob pressão, suporte em {sup}")

    elif 'Fed' in title or 'FOMC' in title or 'Interest Rate' in title and currency == 'USD':
        if asset == 'XAUUSD':
            lines.append(f"Fed hawkish (subir juros) → Ouro CAIR para {sup}")
            lines.append(f"Fed dovish (cortar juros) → Ouro SUBIR para {res}")
        elif asset == 'USDJPY':
            lines.append(f"Fed hawkish → USDJPY SUBIR para {res}")
            lines.append(f"Fed dovish → USDJPY CAIR para {sup}")
        elif asset == 'EURUSD':
            lines.append(f"Fed hawkish → USD forte → EURUSD CAIR para {sup}")
        elif asset == 'BTCUSD':
            lines.append(f"Fed hawkish → liquidez escassa → BTC CAIR para {sup}")
            lines.append(f"Fed dovish → liquidez abundante → BTC SUBIR para {res}")

    elif 'ECB' in title or ('Interest Rate' in title and currency == 'EUR'):
        if asset == 'EURUSD':
            lines.append(f"ECB corta juros → EUR fraco → EURUSD CAIR para {sup}")
            lines.append(f"ECB hawkish → EUR forte → EURUSD SUBIR para {res}")
        elif asset == 'XAUUSD':
            lines.append(f"ECB dovish → risk-on parcial → Ouro neutro")

    elif 'BoJ' in title or ('Interest Rate' in title and currency == 'JPY'):
        if asset == 'USDJPY':
            lines.append(f"BoJ hawkish (subir juros) → JPY forte → USDJPY CAIR para {sup}")
            lines.append(f"BoJ dovish (manter) → JPY fraco → USDJPY SUBIR para {res}")

    elif 'GDP' in title or 'PMI' in title:
        lines.append(f"Dado acima do esperado → {currency} FORTE")
        lines.append(f"Dado abaixo do esperado → {currency} FRACO")
        if trend:
            lines.append(f"Tendência atual: {trend} — dado confirma ou reverte")

    # Fallback genérico
    if not lines:
        lines.append(f"Evento de impacto para {currency}")
        lines.append(f"Tendência atual: {trend}")
        lines.append(f"Resistência: {res} | Suporte: {sup}")

    # Adiciona contexto do gráfico
    lines.append(f"📊 Preço atual: {price} | Tendência: {trend}")

    return '\n   '.join(lines)


# ─────────────────────────────
# FORMATAR MENSAGEM FINAL
# ─────────────────────────────

def format_news_calendar_message(news_key: str, all_tech: dict) -> str:
    """
    Formata mensagem completa combinando:
    - Forex Factory (eventos)
    - NewsAPI (notícias)
    - Dados técnicos (interpretação)
    """
    now   = datetime.utcnow().strftime('%d %b %Y | %H:%M UTC')
    lines = [f"📰 NOTÍCIAS & CALENDÁRIO — {now}", ""]

    # ── FOREX FACTORY ──
    events = fetch_forex_factory()

    if events:
        lines.append("📅 PRÓXIMOS EVENTOS ECONÔMICOS")
        lines.append("─────────────────────────────")

        for ev in events[:6]:
            emoji    = IMPACT_EMOJI.get(ev['impact'], '⚪')
            forecast = f"Esperado: {ev['forecast']}" if ev['forecast'] else ''
            previous = f"Anterior: {ev['previous']}" if ev['previous'] else ''
            extra    = ' | '.join(filter(None, [forecast, previous]))

            lines.append(f"{emoji} {ev['currency']} — {ev['title']}")
            lines.append(f"   📅 {ev['date']} {ev['time']}")
            if extra:
                lines.append(f"   {extra}")

            # Interpretação por ativo afetado
            currency = ev['currency']
            affected = []
            if currency == 'USD':
                affected = ['XAUUSD', 'EURUSD', 'USDJPY', 'BTCUSD']
            elif currency == 'EUR':
                affected = ['EURUSD']
            elif currency == 'JPY':
                affected = ['USDJPY']

            for asset in affected:
                tech   = all_tech.get(asset, {})
                interp = _interpret_event(ev, asset, tech)
                label  = {'XAUUSD': '🥇', 'EURUSD': '💶',
                          'USDJPY': '💴', 'BTCUSD': '₿'}.get(asset, '')
                lines.append(f"   {label} {interp}")

            lines.append("")

    else:
        lines.append("📅 Forex Factory: sem eventos disponíveis no momento")
        lines.append("")

    # ── NEWSAPI ──
    if news_key:
        lines.append("📰 NOTÍCIAS RECENTES")
        lines.append("─────────────────────────────")

        emojis = {'XAUUSD': '🥇 OURO', 'EURUSD': '💶 EUR/USD',
                  'USDJPY': '💴 USD/JPY', 'BTCUSD': '₿ BITCOIN'}

        for asset in ['XAUUSD', 'EURUSD', 'USDJPY', 'BTCUSD']:
            articles = fetch_news(asset, news_key, max_articles=3)
            tech      = all_tech.get(asset, {})
            tech_bias = tech.get('bias', 'NEUTRO')

            lines.append(emojis.get(asset, asset))

            if not articles:
                lines.append("• Sem notícias recentes")
            else:
                # Sentimento agregado
                sentiment = analyze_sentiment(articles)
                divergence = sentiment_vs_price(sentiment, tech_bias)

                lines.append(
                    f"🧠 Sentimento: {sentiment['emoji']} {sentiment['sentiment']} "
                    f"(score: {sentiment['score']:+.2f} | {sentiment['strength']}) "
                    f"— {sentiment['bull_count']}📈 {sentiment['bear_count']}📉 de {sentiment['total']}"
                )
                lines.append(f"   {divergence}")

                for a in articles:
                    # Sentimento individual do artigo
                    art_sent = _score_text(f"{a.get('title','')} {a.get('description','')}")
                    sent_tag = {
                        'BULLISH': '📈', 'BEARISH': '📉',
                        'INCERTO': '❓', 'NEUTRO': '➡️'
                    }.get(art_sent['sentiment'], '')

                    title = a['title'][:80] + '...' if len(a['title']) > 80 else a['title']
                    lines.append(f"• {sent_tag} {title}")
                    lines.append(f"  📅 {a['published']} — {a['source']}")

            lines.append("")

    return '\n'.join(lines)
