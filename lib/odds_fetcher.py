"""
Odds Fetcher — Módulo para obtener cuotas de The Odds API.

Obtiene cuotas en tiempo real de múltiples bookmakers (bet365, Pinnacle, Betfair)
y las normaliza en un formato uniforme para consumo por el ValueCalculator.

Incluye datos mock para desarrollo sin API key.
"""

import os
import time
import json
import hashlib
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    requests = None

try:
    from cachetools import TTLCache
except ImportError:
    # Fallback simple cache si cachetools no está instalado
    class TTLCache(dict):
        def __init__(self, maxsize=100, ttl=300):
            super().__init__()
            self.ttl = ttl
            self.maxsize = maxsize
            self._timestamps = {}
        
        def __getitem__(self, key):
            if key in self._timestamps:
                if time.time() - self._timestamps[key] > self.ttl:
                    del self[key]
                    del self._timestamps[key]
                    raise KeyError(key)
            return super().__getitem__(key)
        
        def __setitem__(self, key, value):
            if len(self) >= self.maxsize:
                # Evict oldest
                oldest = min(self._timestamps, key=self._timestamps.get)
                del self[oldest]
                del self._timestamps[oldest]
            super().__setitem__(key, value)
            self._timestamps[key] = time.time()
        
        def get(self, key, default=None):
            try:
                return self[key]
            except KeyError:
                return default


# Configuración
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_KEY_SEGUNDO = os.environ.get("ODDS_API_KEY_SEGUNDO", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
DEFAULT_SPORT = os.environ.get("SPORT_KEY", "soccer_fifa_world_cup")

# Variables globales para control de claves API (failover)
_exhausted_keys = set()
_active_api_key = ODDS_API_KEY or ODDS_API_KEY_SEGUNDO or ""

# Cache con TTL de 5 minutos (300 segundos)
_cache = TTLCache(maxsize=50, ttl=300)

# Bookmakers objetivo
TARGET_BOOKMAKERS = ["bet365", "pinnacle", "betfair_ex_eu", "betfair"]
MARKET_KEYS = ["h2h", "totals"]


def _generate_mock_data(match_filter: set[str] | None = None) -> list[dict]:
    """DEPRECATED — Solo se usa como fallback si WorldCupProvider falla.

    En el flujo normal, los partidos vienen de WorldCupProvider (fixture
    oficial del Mundial 2026) y OddsFetcher solo aporta las cuotas. Este
    fallback existe únicamente como red de seguridad.

    Args:
        match_filter: Si se pasa, solo devuelve partidos cuyo ID esté en el set.
    """
    now = datetime.now(timezone.utc)

    # Partido genérico de fallback (NO inventado con equipos específicos)
    fallback_match = {
        "id": "wc26_fallback_001",
        "sport_key": "soccer_fifa_world_cup",
        "sport_title": "FIFA World Cup 2026",
        "commence_time": (now + timedelta(hours=2)).isoformat(),
        "home_team": "TBD",
        "away_team": "TBD",
        "bookmakers": {
            "bet365": {
                "h2h": {"Home": 1.85, "Draw": 3.50, "Away": 4.20},
                "totals": {"Over 2.5": 1.80, "Under 2.5": 2.00}
            },
            "pinnacle": {
                "h2h": {"Home": 1.80, "Draw": 3.60, "Away": 4.30},
                "totals": {"Over 2.5": 1.75, "Under 2.5": 2.10}
            }
        }
    }

    if match_filter is None or fallback_match["id"] in match_filter:
        return [fallback_match]
    return []


# Mapeo de equipos → "rating" relativo (1-100, mayor = más fuerte)
# Usado SOLO para generar cuotas mock dinámicas en modo demo
_TEAM_STRENGTH = {
    # Tier S (85-100)
    "Brasil": 92, "Francia": 90, "España": 91, "Argentina": 89, "Inglaterra": 87,
    # Tier A (78-86)
    "Alemania": 84, "Portugal": 83, "Países Bajos": 82, "Bélgica": 81, "Italia": 80,
    "Croacia": 79, "Uruguay": 78,
    # Tier B (70-77)
    "Estados Unidos": 76, "México": 74, "Colombia": 75, "Dinamarca": 73,
    "Suiza": 72, "Japón": 71, "Marruecos": 73, "Senegal": 70,
    # Tier C (60-69)
    "Corea del Sur": 68, "Australia": 67, "Polonia": 66, "Suecia": 65,
    "Egipto": 64, "Nigeria": 66, "Chile": 64, "Perú": 62,
    "Ucrania": 64, "Ecuador": 63, "Canadá": 65, "Austria": 62,
    # Tier D (50-59)
    "Paraguay": 58, "Argelia": 60, "Túnez": 57, "Costa de Marfil": 60,
    "Ghana": 58, "Camerún": 57, "Arabia Saudita": 55, "Qatar": 52,
    "Escocia": 59, "Noruega": 60, "Serbia": 61, "Rumania": 58,
    "Eslovaquia": 56, "Gales": 55, "Irak": 55, "Irán": 56,
    "Costa Rica": 53, "Panamá": 52, "Haití": 50, "Sudáfrica": 51,
    "Cabo Verde": 55, "Curazao": 48, "Nueva Zelanda": 47,
    "Macedonia del Norte": 52,
}


def _generate_realistic_mock_odds(home_team: str, away_team: str) -> dict:
    """Genera cuotas mock realistas basadas en el rating relativo de los equipos.

    Usado SOLO en modo demo. Estrategia:
      - Pinnacle da la "verdad" del mercado (margen bajo).
      - bet365 se basa en Pinnacle con variación aleatoria por outcome.
      - En ~30% de partidos, un outcome de bet365 estará significativamente
        por encima de Pinnacle → value bet detectado.
      - En el resto, bet365 ≈ Pinnacle → edge cercano a 0 (sin value bet).
    """
    import random

    home_rating = _TEAM_STRENGTH.get(home_team, 60)
    away_rating = _TEAM_STRENGTH.get(away_team, 60)

    diff = (home_rating + 3) - away_rating

    home_win_prob = 1 / (1 + 10 ** (-diff / 20))
    home_win_prob = max(0.10, min(0.85, home_win_prob))

    draw_prob = 0.28 - (abs(diff) / 100)
    draw_prob = max(0.15, draw_prob)

    away_win_prob = 1 - home_win_prob - draw_prob
    if away_win_prob < 0.08:
        excess = 0.08 - away_win_prob
        home_win_prob -= excess * 0.7
        draw_prob += excess * 0.3
        away_win_prob = 0.08

    total = home_win_prob + draw_prob + away_win_prob
    home_win_prob /= total
    draw_prob /= total
    away_win_prob /= total

    fair_probs = {"Home": home_win_prob, "Draw": draw_prob, "Away": away_win_prob}

    # Cuotas Pinnacle (margen bajo ~1.5%) — fuente de "verdad" del mercado
    # Con margen 1.5%, el edge normal sin value bet queda en ~1.5% (bajo threshold)
    pin_margin = 1.015
    pinnacle_odds = {
        "Home": round(pin_margin / fair_probs["Home"], 2),
        "Draw": round(pin_margin / fair_probs["Draw"], 2),
        "Away": round(pin_margin / fair_probs["Away"], 2),
    }

    # Decidir si este partido tendrá un value bet (~30% de probabilidad)
    has_value_bet = random.random() < 0.30

    # Cuotas bet365 basadas en Pinnacle con variación aleatoria por outcome
    # Variación típica: -2% a +2% (mercado eficiente)
    # Cuando hay value bet: un outcome tiene +5% a +12%
    bet365_odds = {}
    for outcome in ["Home", "Draw", "Away"]:
        # Variación pequeña ±1% — el mercado tiende a ser eficiente
        variation = random.uniform(-0.01, 0.01)
        bet365_odds[outcome] = round(pinnacle_odds[outcome] * (1 + variation), 2)

    if has_value_bet:
        if random.random() < 0.7:
            chosen = random.choice(["Home", "Away"])
        else:
            chosen = "Draw"
        # Subir la cuota de bet365 significativamente → edge 5-12%
        boost = random.uniform(0.05, 0.12)
        bet365_odds[chosen] = round(pinnacle_odds[chosen] * (1 + boost), 2)

    # Cap defensivo
    for k in ["Home", "Draw", "Away"]:
        bet365_odds[k] = max(1.01, min(bet365_odds[k], 50.0))
        pinnacle_odds[k] = max(1.01, min(pinnacle_odds[k], 50.0))

    # Totals Over/Under 2.5
    combined_strength = (home_rating + away_rating) / 200
    over_prob = 0.45 + (combined_strength * 0.25)
    if abs(diff) > 15:
        over_prob -= 0.05
    over_prob = max(0.40, min(0.75, over_prob))
    under_prob = 1 - over_prob

    fair_totals = {"Over 2.5": over_prob, "Under 2.5": under_prob}
    pin_totals = {k: round(1.015 / v, 2) for k, v in fair_totals.items()}

    bet365_totals = {}
    for k, v in fair_totals.items():
        variation = random.uniform(-0.01, 0.01)
        bet365_totals[k] = round(pin_totals[k] * (1 + variation), 2)
        bet365_totals[k] = max(1.01, min(bet365_totals[k], 50.0))
        pin_totals[k] = max(1.01, min(pin_totals[k], 50.0))

    # 30% de los partidos con value bet también tendrán value en totals
    if has_value_bet and random.random() < 0.4:
        chosen = random.choice(["Over 2.5", "Under 2.5"])
        boost = random.uniform(0.05, 0.12)
        bet365_totals[chosen] = round(pin_totals[chosen] * (1 + boost), 2)
        bet365_totals[chosen] = max(1.01, min(bet365_totals[chosen], 50.0))

    return {
        "h2h": bet365_odds,
        "totals": bet365_totals,
        "_pinnacle_h2h": pinnacle_odds,
        "_pinnacle_totals": pin_totals,
    }


def _mock_odds_response_for_world_cup() -> list[dict]:
    """Genera cuotas mock para TODOS los partidos del Mundial 2026.

    Se usa cuando WorldCupProvider funciona (modo demo del Mundial) pero
    The Odds API no está disponible. Devuelve cuotas en el formato crudo
    de The Odds API para que pasen por _normalize_api_response.
    """
    try:
        from lib.world_cup_provider import _real_world_cup_fixture
        wc_matches = _real_world_cup_fixture()
    except ImportError:
        return []

    # Filtrar partidos placeholder (TBD, "1A", "2B", etc.)
    import re
    placeholder_pattern = re.compile(r"^[1-8][A-L]$|^TBD$", re.IGNORECASE)

    api_format = []
    for m in wc_matches:
        home = m["home_team"]
        away = m["away_team"]
        if placeholder_pattern.match(home) or placeholder_pattern.match(away):
            continue  # No generar cuotas para partidos sin equipos definidos

        odds = _generate_realistic_mock_odds(home, away)

        api_format.append({
            "id": m["id"],
            "sport_key": "soccer_fifa_world_cup",
            "sport_title": "FIFA World Cup 2026",
            "commence_time": m["commence_time"],
            "home_team": home,
            "away_team": away,
            "bookmakers": [
                {
                    "key": "bet365",
                    "title": "Bet365",
                    "markets": [
                        {"key": "h2h", "outcomes": [
                            {"name": home, "price": odds["h2h"]["Home"]},
                            {"name": "Draw", "price": odds["h2h"]["Draw"]},
                            {"name": away, "price": odds["h2h"]["Away"]},
                        ]},
                        {"key": "totals", "outcomes": [
                            {"name": "Over", "price": odds["totals"]["Over 2.5"], "point": 2.5},
                            {"name": "Under", "price": odds["totals"]["Under 2.5"], "point": 2.5},
                        ]},
                    ]
                },
                {
                    "key": "pinnacle",
                    "title": "Pinnacle",
                    "markets": [
                        {"key": "h2h", "outcomes": [
                            {"name": home, "price": odds["_pinnacle_h2h"]["Home"]},
                            {"name": "Draw", "price": odds["_pinnacle_h2h"]["Draw"]},
                            {"name": away, "price": odds["_pinnacle_h2h"]["Away"]},
                        ]},
                        {"key": "totals", "outcomes": [
                            {"name": "Over", "price": odds["_pinnacle_totals"]["Over 2.5"], "point": 2.5},
                            {"name": "Under", "price": odds["_pinnacle_totals"]["Under 2.5"], "point": 2.5},
                        ]},
                    ]
                },
            ]
        })

    return api_format


def _normalize_api_response(api_data: list[dict]) -> list[dict]:
    """Normaliza la respuesta de The Odds API al formato interno.
    
    The Odds API devuelve bookmakers como array; nosotros lo convertimos
    a dict keyed por nombre del bookmaker para acceso O(1).
    """
    normalized = []
    
    for event in api_data:
        match = {
            "id": event.get("id", ""),
            "sport_key": event.get("sport_key", ""),
            "sport_title": event.get("sport_title", ""),
            "commence_time": event.get("commence_time", ""),
            "home_team": event.get("home_team", ""),
            "away_team": event.get("away_team", ""),
            "bookmakers": {}
        }
        
        for bookmaker in event.get("bookmakers", []):
            bk_key = bookmaker.get("key", "").lower()
            
            # Solo procesar bookmakers que nos interesan
            if bk_key not in TARGET_BOOKMAKERS:
                continue
            
            # Normalizar nombre del bookmaker
            display_key = bk_key
            if "betfair" in bk_key:
                display_key = "betfair"
            
            bk_data = {}
            
            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                outcomes = {}
                
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    price = outcome.get("price", 0)
                    point = outcome.get("point", None)
                    
                    # Para totals, agregar el punto (Over 2.5, Under 2.5)
                    if market_key == "totals" and point is not None:
                        label = f"{name} {point}"
                    elif market_key == "h2h":
                        # Mapear Home/Away/Draw
                        if name == event.get("home_team", ""):
                            label = "Home"
                        elif name == event.get("away_team", ""):
                            label = "Away"
                        else:
                            label = "Draw"
                    else:
                        label = name
                    
                    outcomes[label] = price
                
                bk_data[market_key] = outcomes
            
            match["bookmakers"][display_key] = bk_data
        
        normalized.append(match)
    
    return normalized


class OddsFetcher:
    """Wrapper para The Odds API con cache y fallback a datos mock."""
    
    def __init__(self, api_key: str = None, sport_key: str = None):
        self.api_key = api_key or _active_api_key
        self.sport_key = sport_key or DEFAULT_SPORT
        self.use_mock = not bool(self.api_key)
        self._remaining_requests = None
    
    def get_matches(
        self,
        markets: list[str] = None,
        match_ids: set[str] | None = None,
    ) -> list[dict]:
        """Obtiene partidos con cuotas normalizadas.

        Args:
            markets: Lista de mercados a obtener (default: ["h2h", "totals"])
            match_ids: Si se pasa, solo devuelve partidos cuyo ID esté en este set.
                       Útil para cruzar con WorldCupProvider.

        Returns:
            Lista de partidos con cuotas normalizadas por bookmaker.
        """
        if markets is None:
            markets = MARKET_KEYS

        # Generar cache key
        cache_key = f"{self.sport_key}_{','.join(markets)}"

        # Revisar cache
        cached = _cache.get(cache_key)
        if cached is not None:
            if match_ids is None:
                return cached
            return [m for m in cached if m["id"] in match_ids]

        if self.use_mock:
            # En modo demo: si es Mundial, generar cuotas dinámicas para partidos reales
            if self.sport_key == "soccer_fifa_world_cup":
                raw = _mock_odds_response_for_world_cup()
                data = _normalize_api_response(raw) if raw else _generate_mock_data()
            else:
                data = _generate_mock_data()
        else:
            data = self._fetch_from_api(markets)

        _cache[cache_key] = data

        if match_ids is not None:
            return [m for m in data if m["id"] in match_ids]
        return data
    
    def get_match_by_id(self, match_id: str) -> dict | None:
        """Obtiene un partido específico por su ID.

        Args:
            match_id: ID del evento (puede ser de The Odds API o del WorldCupProvider)

        Returns:
            Dict del partido con cuotas o None si no se encuentra.
        """
        # Intentar primero con cuotas reales (si hay ID en The Odds API)
        matches = self.get_matches()
        for match in matches:
            if match["id"] == match_id:
                return match

        # Si no está, intentar matchear por equipos desde WorldCupProvider
        try:
            from lib.world_cup_provider import WorldCupProvider
            wc_provider = WorldCupProvider()
            wc_match = wc_provider.get_match_by_id(match_id)
            if wc_match:
                # Devolver el partido del WC sin cuotas (se mostrarán vacías)
                return {
                    "id": wc_match["id"],
                    "sport_key": "soccer_fifa_world_cup",
                    "sport_title": "FIFA World Cup 2026",
                    "commence_time": wc_match["commence_time"],
                    "home_team": wc_match["home_team"],
                    "away_team": wc_match["away_team"],
                    "bookmakers": {},
                    "stage": wc_match.get("stage"),
                    "group": wc_match.get("group"),
                    "venue": wc_match.get("venue"),
                }
        except Exception as e:
            print(f"[OddsFetcher] WorldCup lookup failed: {e}")

        return None
    
    def _fetch_from_api(self, markets: list[str]) -> list[dict]:
        """Realiza la llamada real a The Odds API.

        Args:
            markets: Lista de mercados a obtener

        Returns:
            Lista normalizada de partidos con cuotas.
        """
        if requests is None:
            print("[OddsFetcher] requests library not available, using mock data")
            return _generate_mock_data()

        url = f"{ODDS_API_BASE}/sports/{self.sport_key}/odds"
        
        # Determinar claves a intentar
        keys_to_try = []
        if self.api_key and self.api_key not in _exhausted_keys:
            keys_to_try.append(self.api_key)
            
        # Si la clave actual no es la secundaria y la secundaria está configurada y no agotada,
        # la agregamos como fallback.
        if (
            ODDS_API_KEY_SEGUNDO
            and ODDS_API_KEY_SEGUNDO not in _exhausted_keys
            and ODDS_API_KEY_SEGUNDO not in keys_to_try
        ):
            keys_to_try.append(ODDS_API_KEY_SEGUNDO)

        if not keys_to_try:
            print("[OddsFetcher] No active/valid API keys available (all exhausted or empty). Falling back to mock data.")
            return _generate_mock_data()

        global _active_api_key
        for current_key in keys_to_try:
            params = {
                "apiKey": current_key,
                "regions": "eu",
                "markets": ",".join(markets),
                "bookmakers": ",".join(TARGET_BOOKMAKERS),
                "oddsFormat": "decimal"
            }

            key_preview = f"{current_key[:6]}..." if len(current_key) > 6 else "empty"
            try:
                print(f"[OddsFetcher] Fetching odds from API using key {key_preview}")
                response = requests.get(url, params=params, timeout=10)

                # Tracking de requests restantes
                self._remaining_requests = response.headers.get(
                    "x-requests-remaining", None
                )

                if response.status_code == 200:
                    raw_data = response.json()
                    # Si tuvimos éxito con una clave diferente a la inicial de la instancia, actualizamos
                    if current_key != self.api_key:
                        print(f"[OddsFetcher] Switched and succeeded with backup key {key_preview}")
                        self.api_key = current_key
                    _active_api_key = current_key
                    return _normalize_api_response(raw_data)
                
                # Si falló, determinar si es por límite de uso/error de clave
                is_exhausted = response.status_code in (401, 403, 429)
                if not is_exhausted and response.text and "OUT_OF_USAGE_CREDITS" in response.text:
                    is_exhausted = True
                
                if is_exhausted:
                    print(f"[OddsFetcher] API key {key_preview} exhausted or invalid (status {response.status_code}). Marking as exhausted.")
                    _exhausted_keys.add(current_key)
                    # Si la clave fallida era la activa global, actualizamos _active_api_key al fallback
                    if _active_api_key == current_key:
                        if current_key == ODDS_API_KEY and ODDS_API_KEY_SEGUNDO and ODDS_API_KEY_SEGUNDO not in _exhausted_keys:
                            _active_api_key = ODDS_API_KEY_SEGUNDO
                        else:
                            _active_api_key = ""
                else:
                    print(f"[OddsFetcher] API error {response.status_code} with key {key_preview}: {response.text}")

            except requests.exceptions.Timeout:
                print(f"[OddsFetcher] Request timeout with key {key_preview}")
            except requests.exceptions.RequestException as e:
                print(f"[OddsFetcher] Request failed with key {key_preview}: {e}")

        # Si todas las claves fallaron o no retornamos éxito
        print("[OddsFetcher] All attempted API keys failed or exhausted, using mock data")
        return _generate_mock_data()
    
    @property
    def remaining_requests(self) -> str | None:
        """Devuelve la cantidad de requests restantes en el plan free."""
        return self._remaining_requests
    
    @property
    def is_mock(self) -> bool:
        """Indica si está usando datos mock."""
        if self.use_mock:
            return True
        if self.api_key in _exhausted_keys:
            if not ODDS_API_KEY_SEGUNDO or ODDS_API_KEY_SEGUNDO in _exhausted_keys:
                return True
        return False
