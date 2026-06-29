"""
Value Calculator — Módulo de cálculo de edge y detección de value bets.

Compara la probabilidad implícita de bet365 contra la probabilidad "real"
derivada de Pinnacle para detectar apuestas con ventaja positiva.
"""

import os


# Umbral mínimo de edge configurable (default 3%)
MIN_EDGE_THRESHOLD = float(os.environ.get("MIN_EDGE_THRESHOLD", 3))


def implied_probability(odds: float) -> float:
    """Calcula la probabilidad implícita a partir de cuotas decimales.
    
    Args:
        odds: Cuota decimal (e.g., 2.50)
    
    Returns:
        Probabilidad entre 0 y 1 (e.g., 0.40 para cuota 2.50)
    """
    if odds <= 0:
        return 0.0
    return 1.0 / odds


def remove_margin(probabilities: list[float]) -> list[float]:
    """Elimina el margen (overround) de las probabilidades de un bookmaker.
    
    Pinnacle tiene ~2% de margen. Para obtener probabilidades "justas",
    normalizamos dividiendo cada probabilidad por la suma total.
    
    Args:
        probabilities: Lista de probabilidades implícitas (suman > 1.0 por el margen)
    
    Returns:
        Lista de probabilidades normalizadas (suman ~1.0)
    """
    total = sum(probabilities)
    if total == 0:
        return probabilities
    return [p / total for p in probabilities]


def calculate_edge(bet365_odds: float, fair_probability: float) -> float:
    """Calcula el edge (ventaja) del apostador.
    
    Fórmula: edge = (probabilidad_real × cuota_bet365) - 1
    
    Args:
        bet365_odds: Cuota decimal ofrecida por bet365
        fair_probability: Probabilidad "justa" derivada de Pinnacle (entre 0 y 1)
    
    Returns:
        Edge como porcentaje (e.g., 5.2 significa 5.2% de ventaja)
    """
    if bet365_odds <= 0 or fair_probability <= 0:
        return 0.0
    edge = (fair_probability * bet365_odds) - 1
    return round(edge * 100, 2)  # Convertir a porcentaje


def classify_edge(edge: float) -> dict:
    """Clasifica el edge según niveles de confianza.
    
    Args:
        edge: Edge en porcentaje
    
    Returns:
        Dict con clasificación, emoji, color y acción recomendada
    """
    if edge > 8:
        return {
            "level": "excellent",
            "label": "Excelente",
            "emoji": "🟢",
            "color": "#22c55e",
            "action": "Apuesta recomendada",
            "stake_pct": 3.0  # 3% del bankroll
        }
    elif edge > 5:
        return {
            "level": "good",
            "label": "Buena",
            "emoji": "🟢",
            "color": "#4ade80",
            "action": "Apuesta recomendada",
            "stake_pct": 2.0
        }
    elif edge >= MIN_EDGE_THRESHOLD:
        return {
            "level": "acceptable",
            "label": "Aceptable",
            "emoji": "🟡",
            "color": "#eab308",
            "action": "Apuesta con stake bajo",
            "stake_pct": 1.0
        }
    else:
        return {
            "level": "insufficient",
            "label": "Insuficiente",
            "emoji": "⚪",
            "color": "#6b7280",
            "action": "No apostar",
            "stake_pct": 0.0
        }


def suggested_stake(edge: float, bankroll: float = 100.0) -> float:
    """Calcula el stake sugerido usando criterio de Kelly simplificado.
    
    Usa una fracción conservadora (1/4 de Kelly) para reducir varianza.
    
    Args:
        edge: Edge en porcentaje
        bankroll: Bankroll total del apostador
    
    Returns:
        Stake sugerido en la misma moneda que el bankroll
    """
    classification = classify_edge(edge)
    stake_pct = classification["stake_pct"]
    return round(bankroll * (stake_pct / 100), 2)


def process_match_odds(match_data: dict) -> dict:
    """Procesa las cuotas de un partido y calcula edge para todos los mercados.
    
    Args:
        match_data: Dict con formato normalizado del OddsFetcher, incluyendo
                    cuotas de bet365 y Pinnacle por mercado.
    
    Returns:
        Dict enriquecido con edge, clasificación y recomendación por mercado.
    """
    result = {
        "match_id": match_data.get("id", ""),
        "home_team": match_data.get("home_team", ""),
        "away_team": match_data.get("away_team", ""),
        "commence_time": match_data.get("commence_time", ""),
        "sport": match_data.get("sport_key", ""),
        "markets": {},
        "best_bet": None,
        "has_value": False
    }
    
    bet365 = match_data.get("bookmakers", {}).get("bet365", {})
    pinnacle = match_data.get("bookmakers", {}).get("pinnacle", {})
    
    # Si no hay Pinnacle, intentar Betfair como fallback
    if not pinnacle:
        pinnacle = match_data.get("bookmakers", {}).get("betfair", {})
    
    if not bet365 or not pinnacle:
        return result
    
    best_edge = -999
    best_market = None
    best_outcome = None
    
    # Procesar cada mercado disponible
    for market_key in ["h2h", "totals", "btts"]:
        bet365_market = bet365.get(market_key, {})
        pinnacle_market = pinnacle.get(market_key, {})
        
        if not bet365_market or not pinnacle_market:
            continue
        
        market_result = {"outcomes": []}
        
        # Obtener probabilidades justas de Pinnacle (sin margen)
        pinnacle_probs = []
        pinnacle_outcomes = list(pinnacle_market.keys())
        for outcome_key in pinnacle_outcomes:
            pinnacle_probs.append(implied_probability(pinnacle_market[outcome_key]))
        
        fair_probs = remove_margin(pinnacle_probs)
        
        # Calcular edge para cada outcome
        for i, outcome_key in enumerate(pinnacle_outcomes):
            if outcome_key not in bet365_market:
                continue
            
            b365_odds = bet365_market[outcome_key]
            fair_prob = fair_probs[i] if i < len(fair_probs) else 0
            edge = calculate_edge(b365_odds, fair_prob)
            classification = classify_edge(edge)
            
            outcome_data = {
                "name": outcome_key,
                "bet365_odds": b365_odds,
                "pinnacle_odds": pinnacle_market[outcome_key],
                "implied_prob_bet365": round(implied_probability(b365_odds) * 100, 1),
                "fair_probability": round(fair_prob * 100, 1),
                "edge": edge,
                "classification": classification
            }
            market_result["outcomes"].append(outcome_data)
            
            # Track best bet
            if edge > best_edge:
                best_edge = edge
                best_market = market_key
                best_outcome = outcome_data
        
        result["markets"][market_key] = market_result
    
    # Determinar mejor apuesta
    if best_edge >= MIN_EDGE_THRESHOLD and best_outcome:
        result["has_value"] = True
        result["best_bet"] = {
            "market": best_market,
            "outcome": best_outcome["name"],
            "odds": best_outcome["bet365_odds"],
            "edge": best_edge,
            "classification": classify_edge(best_edge),
            "stake_suggested": suggested_stake(best_edge)
        }
    
    return result


class ValueCalculator:
    """Clase wrapper para cálculos de value bet con configuración persistente."""
    
    def __init__(self, min_edge: float = None, bankroll: float = 100.0):
        self.min_edge = min_edge if min_edge is not None else MIN_EDGE_THRESHOLD
        self.bankroll = bankroll
    
    def analyze_match(self, match_data: dict) -> dict:
        """Analiza un partido y devuelve los value bets encontrados."""
        return process_match_odds(match_data)
    
    def analyze_matches(self, matches: list[dict]) -> list[dict]:
        """Analiza múltiples partidos y devuelve solo los que tienen value."""
        results = []
        for match in matches:
            analysis = self.analyze_match(match)
            results.append(analysis)
        return results
    
    def get_value_bets_only(self, matches: list[dict]) -> list[dict]:
        """Filtra y devuelve solo los partidos con value bets."""
        all_results = self.analyze_matches(matches)
        value_bets = [r for r in all_results if r["has_value"]]
        # Ordenar por edge descendente
        value_bets.sort(key=lambda x: x["best_bet"]["edge"] if x["best_bet"] else 0, reverse=True)
        return value_bets
