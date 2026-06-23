"""
ML ENGINE — Bot V11
Random Forest para predição de direção e score de probabilidade.
Integra com technical_engine e confluence_engine.
"""

import numpy as np
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────

def _extract_features(df: pd.DataFrame) -> Optional[np.ndarray]:
    """
    Extrai features do OHLCV para o modelo.
    Retorna array 2D (n_samples, n_features) ou None se dados insuficientes.
    """
    if df is None or len(df) < 50:
        return None

    closes  = df['Close'].values
    highs   = df['High'].values
    lows    = df['Low'].values
    opens   = df['Open'].values
    volumes = df['Volume'].values if 'Volume' in df.columns else np.ones(len(df))

    features = []

    for i in range(20, len(df)):
        c = closes[i]
        h = highs[i]
        l = lows[i]
        o = opens[i]

        # ── Momentum ──
        roc_5  = (c - closes[i-5])  / closes[i-5]   if closes[i-5]  != 0 else 0
        roc_10 = (c - closes[i-10]) / closes[i-10]  if closes[i-10] != 0 else 0
        roc_20 = (c - closes[i-20]) / closes[i-20]  if closes[i-20] != 0 else 0

        # ── Médias móveis ──
        sma5  = np.mean(closes[i-5:i])
        sma10 = np.mean(closes[i-10:i])
        sma20 = np.mean(closes[i-20:i])

        ma_cross_5_20  = (sma5  - sma20) / sma20  if sma20 != 0 else 0
        ma_cross_10_20 = (sma10 - sma20) / sma20  if sma20 != 0 else 0

        # ── Volatilidade ──
        returns   = np.diff(closes[i-20:i+1]) / closes[i-20:i]
        vol_20    = np.std(returns) if len(returns) > 1 else 0
        atr_range = np.mean(highs[i-14:i] - lows[i-14:i]) if i >= 14 else 0
        atr_norm  = atr_range / c if c != 0 else 0

        # ── RSI (14) ──
        rsi = _calc_rsi(closes[max(0, i-14):i+1])

        # ── Candle body ──
        body      = (c - o) / (h - l + 1e-10)       # -1 a 1
        wick_up   = (h - max(o, c)) / (h - l + 1e-10)
        wick_down = (min(o, c) - l) / (h - l + 1e-10)

        # ── Posição no range dos últimos 20 candles ──
        high_20   = np.max(highs[i-20:i])
        low_20    = np.min(lows[i-20:i])
        range_pos = (c - low_20) / (high_20 - low_20 + 1e-10)

        # ── Volume relativo ──
        vol_mean = np.mean(volumes[i-10:i]) if i >= 10 else 1
        vol_rel  = volumes[i] / (vol_mean + 1e-10)

        # ── Distância de suportes/resistências ──
        sr_dist_up   = (np.max(highs[i-20:i]) - c) / c if c != 0 else 0
        sr_dist_down = (c - np.min(lows[i-20:i]))  / c if c != 0 else 0

        row = [
            roc_5, roc_10, roc_20,
            ma_cross_5_20, ma_cross_10_20,
            vol_20, atr_norm,
            rsi / 100.0,
            body, wick_up, wick_down,
            range_pos,
            vol_rel,
            sr_dist_up, sr_dist_down,
        ]
        features.append(row)

    return np.array(features, dtype=np.float32)


def _calc_rsi(prices: np.ndarray, period: int = 14) -> float:
    """RSI simplificado."""
    if len(prices) < 2:
        return 50.0
    deltas = np.diff(prices)
    gains  = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_g  = np.mean(gains)
    avg_l  = np.mean(losses)
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def _create_labels(closes: np.ndarray, lookahead: int = 5) -> np.ndarray:
    """
    Labels: 1 (alta) se preço subir >= 0.3% em `lookahead` candles, else 0.
    """
    labels = []
    for i in range(len(closes) - lookahead):
        future_ret = (closes[i + lookahead] - closes[i]) / closes[i]
        labels.append(1 if future_ret >= 0.003 else 0)
    return np.array(labels)


# ─────────────────────────────
# RANDOM FOREST MANUAL
# (sem sklearn — compatível com qualquer ambiente)
# ─────────────────────────────

class SimpleDecisionTree:
    """Árvore de decisão simples via thresholds aleatórios."""

    def __init__(self, max_depth=5, n_features_per_split=None, seed=42):
        self.max_depth = max_depth
        self.n_feats   = n_features_per_split
        self.seed      = seed
        self.tree      = None

    def fit(self, X: np.ndarray, y: np.ndarray, depth=0, rng=None):
        if rng is None:
            rng = np.random.default_rng(self.seed)
        self.tree = self._build(X, y, depth, rng)

    def _build(self, X, y, depth, rng):
        n, p = X.shape
        if depth >= self.max_depth or n < 5 or len(np.unique(y)) == 1:
            return {'leaf': True, 'value': float(np.mean(y))}

        n_feats = self.n_feats or max(1, int(np.sqrt(p)))
        feat_idx = rng.choice(p, size=min(n_feats, p), replace=False)

        best_feat, best_thresh, best_gain = None, None, -np.inf

        for f in feat_idx:
            vals = X[:, f]
            thresholds = np.unique(vals)
            if len(thresholds) < 2:
                continue
            thresholds = thresholds[:-1]

            for t in thresholds:
                left_mask  = vals <= t
                right_mask = ~left_mask
                if left_mask.sum() < 2 or right_mask.sum() < 2:
                    continue

                gain = self._gini_gain(y, y[left_mask], y[right_mask])
                if gain > best_gain:
                    best_gain  = gain
                    best_feat  = f
                    best_thresh = t

        if best_feat is None:
            return {'leaf': True, 'value': float(np.mean(y))}

        left_mask = X[:, best_feat] <= best_thresh
        return {
            'leaf':   False,
            'feat':   best_feat,
            'thresh': best_thresh,
            'left':   self._build(X[left_mask],  y[left_mask],  depth+1, rng),
            'right':  self._build(X[~left_mask], y[~left_mask], depth+1, rng),
        }

    def _gini_gain(self, parent, left, right):
        def gini(arr):
            if len(arr) == 0:
                return 0
            p = np.mean(arr)
            return 1 - p**2 - (1-p)**2

        n = len(parent)
        return (gini(parent)
                - (len(left)/n)  * gini(left)
                - (len(right)/n) * gini(right))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.array([self._traverse(x, self.tree) for x in X])

    def _traverse(self, x, node):
        if node['leaf']:
            return node['value']
        if x[node['feat']] <= node['thresh']:
            return self._traverse(x, node['left'])
        return self._traverse(x, node['right'])


class SimpleRandomForest:
    """Random Forest com n árvores, bootstrap e feature sampling."""

    def __init__(self, n_trees=30, max_depth=5, seed=42):
        self.n_trees   = n_trees
        self.max_depth = max_depth
        self.seed      = seed
        self.trees     = []
        self.trained   = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        rng = np.random.default_rng(self.seed)
        n, p = X.shape
        n_feats = max(1, int(np.sqrt(p)))

        self.trees = []
        for i in range(self.n_trees):
            idx  = rng.choice(n, size=n, replace=True)
            Xb   = X[idx]
            yb   = y[idx]
            tree = SimpleDecisionTree(max_depth=self.max_depth,
                                      n_features_per_split=n_feats,
                                      seed=self.seed + i)
            tree.fit(Xb, yb, rng=rng)
            self.trees.append(tree)

        self.trained = True
        logger.info(f"[ML] Random Forest treinado com {self.n_trees} árvores.")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Retorna probabilidade de alta (0-1) para cada amostra."""
        preds = np.array([t.predict_proba(X) for t in self.trees])
        return np.mean(preds, axis=0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X) >= 0.5).astype(int)


# ─────────────────────────────
# CACHE DE MODELOS (por ativo + timeframe)
# ─────────────────────────────

_model_cache: dict = {}


def _get_model_key(asset: str, tf: str) -> str:
    return f"{asset}_{tf}"


# ─────────────────────────────
# INTERFACE PRINCIPAL
# ─────────────────────────────

def train_and_predict(asset: str, timeframes_data: dict,
                      primary_tf: str = 'D1',
                      retrain: bool = False) -> dict:
    """
    Treina (ou reutiliza) Random Forest para o ativo e retorna predição atual.

    Args:
        asset:           'XAUUSD', 'EURUSD', 'USDJPY', 'BTCUSD'
        timeframes_data: dict com DataFrames por timeframe (mesmo formato do technical_engine)
        primary_tf:      Timeframe principal para treino ('D1' por padrão)
        retrain:         Força re-treino mesmo se modelo em cache

    Returns:
        dict com direction, probability, confidence, signal, factors
    """
    result = {
        'direction':   'NEUTRO',
        'probability': 50.0,
        'confidence':  'BAIXA',
        'signal':      'SEM SINAL ML',
        'factors':     [],
        'trained_on':  primary_tf,
    }

    df = timeframes_data.get(primary_tf)
    if df is None or len(df) < 60:
        result['signal'] = f'Dados insuficientes no {primary_tf} (mín: 60 candles)'
        return result

    # ── Features e labels ──
    X = _extract_features(df)
    if X is None or len(X) < 30:
        result['signal'] = 'Features insuficientes para treino'
        return result

    labels = _create_labels(df['Close'].values)
    min_len = min(len(X), len(labels))
    X = X[:min_len]
    y = labels[:min_len]

    # ── Treino / cache ──
    key = _get_model_key(asset, primary_tf)
    if key not in _model_cache or retrain:
        # Treina em 80% do histórico
        split   = int(len(X) * 0.8)
        X_train = X[:split]
        y_train = y[:split]

        if len(X_train) < 20:
            result['signal'] = 'Histórico insuficiente para treino'
            return result

        model = SimpleRandomForest(n_trees=30, max_depth=5, seed=42)
        model.fit(X_train, y_train)
        _model_cache[key] = model

        # Acurácia no conjunto de teste
        X_test = X[split:]
        y_test = y[split:]
        if len(X_test) > 0:
            y_pred = model.predict(X_test)
            acc    = np.mean(y_pred == y_test)
            result['factors'].append(f'Acurácia no teste ({primary_tf}): {acc*100:.1f}%')
    else:
        model = _model_cache[key]

    # ── Predição no candle atual ──
    last_features = X[-1:].copy()
    prob_up = float(model.predict_proba(last_features)[0])

    # ── Resultado ──
    result['probability'] = round(prob_up * 100, 1)

    if prob_up >= 0.65:
        result['direction'] = 'COMPRA'
        result['confidence'] = 'ALTA'
        result['signal']    = f'ML → COMPRA ({prob_up*100:.1f}% probabilidade de alta)'
    elif prob_up >= 0.55:
        result['direction'] = 'COMPRA'
        result['confidence'] = 'MODERADA'
        result['signal']    = f'ML → COMPRA FRACA ({prob_up*100:.1f}%)'
    elif prob_up <= 0.35:
        result['direction'] = 'VENDA'
        result['confidence'] = 'ALTA'
        result['signal']    = f'ML → VENDA ({(1-prob_up)*100:.1f}% probabilidade de queda)'
    elif prob_up <= 0.45:
        result['direction'] = 'VENDA'
        result['confidence'] = 'MODERADA'
        result['signal']    = f'ML → VENDA FRACA ({(1-prob_up)*100:.1f}%)'
    else:
        result['direction'] = 'NEUTRO'
        result['confidence'] = 'BAIXA'
        result['signal']    = f'ML → NEUTRO ({prob_up*100:.1f}%)'

    # ── Features mais relevantes (proxy via variância) ──
    feature_names = [
        'ROC-5', 'ROC-10', 'ROC-20',
        'MA-cross-5/20', 'MA-cross-10/20',
        'Volatilidade', 'ATR-norm',
        'RSI', 'Body', 'Wick-up', 'Wick-down',
        'Range-pos', 'Volume-rel',
        'Dist-resist', 'Dist-suporte',
    ]

    # Importância estimada: variância de predições com feature zerada
    importances = []
    base_prob   = prob_up
    for fi in range(last_features.shape[1]):
        perturbed         = last_features.copy()
        perturbed[0, fi]  = 0.0
        p_perturbed       = float(model.predict_proba(perturbed)[0])
        importances.append(abs(base_prob - p_perturbed))

    top_idx = np.argsort(importances)[::-1][:3]
    for idx in top_idx:
        if importances[idx] > 0.001:
            name = feature_names[idx] if idx < len(feature_names) else f'Feature-{idx}'
            result['factors'].append(f'Feature importante: {name} (impacto: {importances[idx]:.3f})')

    return result


def ml_confluence_score(ml_result: dict, direction: str) -> int:
    """
    Converte resultado ML em pontos para o confluence_engine.
    
    Args:
        ml_result: retorno de train_and_predict()
        direction: viés atual do confluence_engine ('COMPRA', 'VENDA', 'NEUTRO')
    
    Returns:
        score: positivo = altista, negativo = baixista, 0 = neutro
    """
    ml_dir  = ml_result.get('direction', 'NEUTRO')
    conf    = ml_result.get('confidence', 'BAIXA')
    prob    = ml_result.get('probability', 50.0)

    if ml_dir == 'NEUTRO':
        return 0

    # Pontuação base por confiança
    base = {'ALTA': 3, 'MODERADA': 2, 'BAIXA': 1}.get(conf, 0)

    # Bônus se alinhado com macro/técnico
    if ml_dir == direction:
        base += 1

    return base if ml_dir == 'COMPRA' else -base


def format_ml_message(asset: str, ml_result: dict) -> str:
    """Formata bloco ML para inserir na mensagem do ativo."""
    direction = ml_result.get('direction', 'NEUTRO')
    prob      = ml_result.get('probability', 50.0)
    conf      = ml_result.get('confidence', 'BAIXA')
    signal    = ml_result.get('signal', 'N/D')
    factors   = ml_result.get('factors', [])
    tf        = ml_result.get('trained_on', 'D1')

    dir_emoji = {'COMPRA': '📈', 'VENDA': '📉', 'NEUTRO': '➡️'}.get(direction, '')
    conf_emoji = {'ALTA': '🟢', 'MODERADA': '🟡', 'BAIXA': '🔴'}.get(conf, '')

    lines = [
        "─────────────────────────────",
        f"🤖 ML ENGINE (Random Forest | {tf})",
        f"Sinal: {signal} {dir_emoji}",
        f"Confiança: {conf} {conf_emoji}",
    ]

    if factors:
        lines.append("Fatores:")
        for f in factors:
            lines.append(f"  • {f}")

    return '\n'.join(lines)


# ─────────────────────────────
# ANÁLISE MULTI-TIMEFRAME
# ─────────────────────────────

def analyze_ml_multi_tf(asset: str, timeframes_data: dict) -> dict:
    """
    Roda ML em D1, 4H e 1H e combina os sinais por peso.
    
    Pesos: D1=50%, 4H=30%, 1H=20%
    """
    weights = {'D1': 0.50, '4H': 0.30, '1H': 0.20}
    results = {}

    weighted_prob = 0.0
    total_weight  = 0.0

    for tf, w in weights.items():
        df = timeframes_data.get(tf)
        if df is not None and len(df) >= 60:
            r = train_and_predict(asset, timeframes_data, primary_tf=tf)
            results[tf] = r
            weighted_prob += r['probability'] * w
            total_weight  += w

    if total_weight == 0:
        return {
            'direction':   'NEUTRO',
            'probability': 50.0,
            'confidence':  'BAIXA',
            'signal':      'Dados insuficientes para ML multi-TF',
            'factors':     [],
            'per_tf':      results,
        }

    final_prob = weighted_prob / total_weight

    if final_prob >= 62:
        direction = 'COMPRA'
        confidence = 'ALTA' if final_prob >= 68 else 'MODERADA'
    elif final_prob <= 38:
        direction = 'VENDA'
        confidence = 'ALTA' if final_prob <= 32 else 'MODERADA'
    else:
        direction = 'NEUTRO'
        confidence = 'BAIXA'

    signal = f"ML Multi-TF → {direction} ({final_prob:.1f}%)"

    return {
        'direction':   direction,
        'probability': round(final_prob, 1),
        'confidence':  confidence,
        'signal':      signal,
        'factors':     [f"D1: {results.get('D1', {}).get('probability', 'N/D')}% | "
                        f"4H: {results.get('4H', {}).get('probability', 'N/D')}% | "
                        f"1H: {results.get('1H', {}).get('probability', 'N/D')}%"],
        'per_tf':      results,
        'trained_on':  'Multi-TF',
    }
