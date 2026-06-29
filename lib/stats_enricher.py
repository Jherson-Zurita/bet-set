"""
Stats Enricher — Módulo para enriquecer el análisis con estadísticas.

Integra datos de API-Football (H2H, forma, lesiones) y CornerPro
(corners, tiros, presión) para complementar el análisis de cuotas.
"""

import os
import time

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from cachetools import TTLCache
except ImportError:
    class TTLCache(dict):
        def __init__(self, maxsize=100, ttl=300):
            super().__init__()
            self.ttl = ttl
        def get(self, key, default=None):
            return super().get(key, default)


FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://v3.football.api-sports.io"

# Cache de 24h para stats pre-partido
_stats_cache = TTLCache(maxsize=100, ttl=86400)

# Datos mock de stats para desarrollo
_MOCK_STATS = {
    # ====== Conmebol / Sudamérica ======
    "Argentina": {"form": "WWDWW", "goals_scored_avg": 2.1, "goals_conceded_avg": 0.6, "corners_avg": 5.8, "shots_avg": 14.2, "possession_avg": 58, "clean_sheets_pct": 45, "btts_pct": 55},
    "Brasil": {"form": "WWWDW", "goals_scored_avg": 2.4, "goals_conceded_avg": 0.7, "corners_avg": 6.1, "shots_avg": 15.8, "possession_avg": 62, "clean_sheets_pct": 50, "btts_pct": 50},
    "Uruguay": {"form": "WDWWD", "goals_scored_avg": 1.5, "goals_conceded_avg": 0.7, "corners_avg": 4.8, "shots_avg": 11.5, "possession_avg": 48, "clean_sheets_pct": 45, "btts_pct": 48},
    "Colombia": {"form": "DWWDW", "goals_scored_avg": 1.7, "goals_conceded_avg": 0.8, "corners_avg": 5.1, "shots_avg": 12.0, "possession_avg": 52, "clean_sheets_pct": 38, "btts_pct": 55},
    "Chile": {"form": "DLWDW", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.0, "corners_avg": 4.7, "shots_avg": 11.8, "possession_avg": 51, "clean_sheets_pct": 32, "btts_pct": 50},
    "Perú": {"form": "WDLDD", "goals_scored_avg": 1.2, "goals_conceded_avg": 1.1, "corners_avg": 4.4, "shots_avg": 10.5, "possession_avg": 47, "clean_sheets_pct": 30, "btts_pct": 52},
    "Paraguay": {"form": "DLWWD", "goals_scored_avg": 1.3, "goals_conceded_avg": 1.0, "corners_avg": 4.6, "shots_avg": 11.0, "possession_avg": 49, "clean_sheets_pct": 35, "btts_pct": 48},
    "Ecuador": {"form": "WDLDW", "goals_scored_avg": 1.5, "goals_conceded_avg": 1.1, "corners_avg": 4.9, "shots_avg": 11.7, "possession_avg": 50, "clean_sheets_pct": 32, "btts_pct": 55},

    # ====== Concacaf ======
    "México": {"form": "WDLDW", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.0, "corners_avg": 4.5, "shots_avg": 10.8, "possession_avg": 50, "clean_sheets_pct": 28, "btts_pct": 60},
    "Estados Unidos": {"form": "WWWDL", "goals_scored_avg": 1.8, "goals_conceded_avg": 0.9, "corners_avg": 5.3, "shots_avg": 13.0, "possession_avg": 53, "clean_sheets_pct": 32, "btts_pct": 58},
    "Canadá": {"form": "LDWWD", "goals_scored_avg": 1.3, "goals_conceded_avg": 1.2, "corners_avg": 4.3, "shots_avg": 10.5, "possession_avg": 46, "clean_sheets_pct": 28, "btts_pct": 55},
    "Costa Rica": {"form": "LDDLW", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.4, "corners_avg": 4.0, "shots_avg": 9.8, "possession_avg": 45, "clean_sheets_pct": 22, "btts_pct": 58},
    "Panamá": {"form": "DLWLD", "goals_scored_avg": 1.1, "goals_conceded_avg": 1.3, "corners_avg": 4.1, "shots_avg": 9.5, "possession_avg": 44, "clean_sheets_pct": 25, "btts_pct": 52},
    "Curazao": {"form": "WLDWD", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.4, "corners_avg": 3.8, "shots_avg": 9.2, "possession_avg": 43, "clean_sheets_pct": 20, "btts_pct": 55},

    # ====== UEFA ======
    "Francia": {"form": "WDWWL", "goals_scored_avg": 1.8, "goals_conceded_avg": 0.9, "corners_avg": 5.2, "shots_avg": 13.5, "possession_avg": 55, "clean_sheets_pct": 35, "btts_pct": 60},
    "Alemania": {"form": "WDWLW", "goals_scored_avg": 2.0, "goals_conceded_avg": 1.1, "corners_avg": 5.5, "shots_avg": 13.0, "possession_avg": 56, "clean_sheets_pct": 30, "btts_pct": 65},
    "España": {"form": "WWWWW", "goals_scored_avg": 2.6, "goals_conceded_avg": 0.4, "corners_avg": 7.2, "shots_avg": 16.5, "possession_avg": 68, "clean_sheets_pct": 60, "btts_pct": 40},
    "Inglaterra": {"form": "WDWDW", "goals_scored_avg": 1.6, "goals_conceded_avg": 0.8, "corners_avg": 5.0, "shots_avg": 12.8, "possession_avg": 54, "clean_sheets_pct": 40, "btts_pct": 55},
    "Portugal": {"form": "DWWWW", "goals_scored_avg": 2.2, "goals_conceded_avg": 0.9, "corners_avg": 5.4, "shots_avg": 14.0, "possession_avg": 57, "clean_sheets_pct": 35, "btts_pct": 58},
    "Países Bajos": {"form": "WWDWL", "goals_scored_avg": 1.9, "goals_conceded_avg": 1.0, "corners_avg": 5.6, "shots_avg": 13.2, "possession_avg": 59, "clean_sheets_pct": 30, "btts_pct": 62},
    "Italia": {"form": "DWWDL", "goals_scored_avg": 1.7, "goals_conceded_avg": 0.9, "corners_avg": 5.8, "shots_avg": 13.8, "possession_avg": 58, "clean_sheets_pct": 38, "btts_pct": 55},
    "Bélgica": {"form": "LWDWW", "goals_scored_avg": 1.8, "goals_conceded_avg": 1.1, "corners_avg": 5.0, "shots_avg": 12.5, "possession_avg": 54, "clean_sheets_pct": 30, "btts_pct": 60},
    "Croacia": {"form": "WDLWD", "goals_scored_avg": 1.5, "goals_conceded_avg": 1.0, "corners_avg": 4.8, "shots_avg": 11.8, "possession_avg": 53, "clean_sheets_pct": 32, "btts_pct": 52},
    "Suiza": {"form": "WWLDW", "goals_scored_avg": 1.6, "goals_conceded_avg": 1.0, "corners_avg": 4.9, "shots_avg": 12.0, "possession_avg": 52, "clean_sheets_pct": 35, "btts_pct": 53},
    "Dinamarca": {"form": "DWWDW", "goals_scored_avg": 1.7, "goals_conceded_avg": 0.9, "corners_avg": 5.1, "shots_avg": 12.3, "possession_avg": 53, "clean_sheets_pct": 38, "btts_pct": 55},
    "Serbia": {"form": "WLDWW", "goals_scored_avg": 1.6, "goals_conceded_avg": 1.1, "corners_avg": 4.7, "shots_avg": 11.5, "possession_avg": 50, "clean_sheets_pct": 30, "btts_pct": 58},
    "Polonia": {"form": "DWLWL", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.2, "corners_avg": 4.5, "shots_avg": 11.0, "possession_avg": 49, "clean_sheets_pct": 28, "btts_pct": 55},
    "Gales": {"form": "LDDLW", "goals_scored_avg": 1.2, "goals_conceded_avg": 1.3, "corners_avg": 4.2, "shots_avg": 10.2, "possession_avg": 47, "clean_sheets_pct": 25, "btts_pct": 58},
    "Austria": {"form": "WDLDW", "goals_scored_avg": 1.5, "goals_conceded_avg": 1.1, "corners_avg": 4.8, "shots_avg": 11.7, "possession_avg": 51, "clean_sheets_pct": 30, "btts_pct": 55},
    "Ucrania": {"form": "WDLWW", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.2, "corners_avg": 4.5, "shots_avg": 11.0, "possession_avg": 48, "clean_sheets_pct": 28, "btts_pct": 55},
    "Suecia": {"form": "DWLWL", "goals_scored_avg": 1.5, "goals_conceded_avg": 1.1, "corners_avg": 4.9, "shots_avg": 11.8, "possession_avg": 50, "clean_sheets_pct": 30, "btts_pct": 55},
    "Noruega": {"form": "WWDWD", "goals_scored_avg": 1.8, "goals_conceded_avg": 1.0, "corners_avg": 5.0, "shots_avg": 12.3, "possession_avg": 52, "clean_sheets_pct": 35, "btts_pct": 55},
    "Escocia": {"form": "LWWLD", "goals_scored_avg": 1.3, "goals_conceded_avg": 1.2, "corners_avg": 4.4, "shots_avg": 10.8, "possession_avg": 47, "clean_sheets_pct": 28, "btts_pct": 55},
    "Eslovaquia": {"form": "WLWLD", "goals_scored_avg": 1.3, "goals_conceded_avg": 1.2, "corners_avg": 4.3, "shots_avg": 10.5, "possession_avg": 46, "clean_sheets_pct": 27, "btts_pct": 55},
    "Rumania": {"form": "WDLWD", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.1, "corners_avg": 4.6, "shots_avg": 11.2, "possession_avg": 49, "clean_sheets_pct": 30, "btts_pct": 53},
    "Macedonia del Norte": {"form": "LDLDW", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.5, "corners_avg": 3.9, "shots_avg": 9.5, "possession_avg": 44, "clean_sheets_pct": 22, "btts_pct": 58},

    # ====== CAF / África ======
    "Marruecos": {"form": "WWDWD", "goals_scored_avg": 1.5, "goals_conceded_avg": 0.9, "corners_avg": 4.7, "shots_avg": 11.5, "possession_avg": 52, "clean_sheets_pct": 35, "btts_pct": 50},
    "Senegal": {"form": "WDLDW", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.0, "corners_avg": 4.5, "shots_avg": 11.2, "possession_avg": 50, "clean_sheets_pct": 32, "btts_pct": 52},
    "Camerún": {"form": "DLWLD", "goals_scored_avg": 1.2, "goals_conceded_avg": 1.2, "corners_avg": 4.2, "shots_avg": 10.5, "possession_avg": 48, "clean_sheets_pct": 28, "btts_pct": 55},
    "Ghana": {"form": "LWDLD", "goals_scored_avg": 1.1, "goals_conceded_avg": 1.3, "corners_avg": 4.0, "shots_avg": 10.0, "possession_avg": 46, "clean_sheets_pct": 25, "btts_pct": 55},
    "Egipto": {"form": "WDLWD", "goals_scored_avg": 1.5, "goals_conceded_avg": 1.0, "corners_avg": 4.8, "shots_avg": 11.8, "possession_avg": 52, "clean_sheets_pct": 35, "btts_pct": 52},
    "Argelia": {"form": "WDWLD", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.1, "corners_avg": 4.5, "shots_avg": 11.2, "possession_avg": 50, "clean_sheets_pct": 30, "btts_pct": 53},
    "Túnez": {"form": "DLWLD", "goals_scored_avg": 1.1, "goals_conceded_avg": 1.2, "corners_avg": 4.1, "shots_avg": 10.2, "possession_avg": 47, "clean_sheets_pct": 28, "btts_pct": 52},
    "Costa de Marfil": {"form": "WDWLD", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.0, "corners_avg": 4.6, "shots_avg": 11.5, "possession_avg": 50, "clean_sheets_pct": 32, "btts_pct": 52},
    "Sudáfrica": {"form": "LDLDW", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.4, "corners_avg": 3.9, "shots_avg": 9.5, "possession_avg": 44, "clean_sheets_pct": 22, "btts_pct": 55},
    "Cabo Verde": {"form": "WLWLD", "goals_scored_avg": 1.2, "goals_conceded_avg": 1.2, "corners_avg": 4.2, "shots_avg": 10.3, "possession_avg": 47, "clean_sheets_pct": 28, "btts_pct": 53},

    # ====== AFC / Asia ======
    "Japón": {"form": "WDWWD", "goals_scored_avg": 1.5, "goals_conceded_avg": 1.0, "corners_avg": 4.8, "shots_avg": 11.8, "possession_avg": 50, "clean_sheets_pct": 32, "btts_pct": 52},
    "Corea del Sur": {"form": "DLWWD", "goals_scored_avg": 1.4, "goals_conceded_avg": 1.1, "corners_avg": 4.5, "shots_avg": 11.2, "possession_avg": 49, "clean_sheets_pct": 30, "btts_pct": 53},
    "Arabia Saudita": {"form": "LDWLD", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.4, "corners_avg": 3.9, "shots_avg": 9.5, "possession_avg": 45, "clean_sheets_pct": 22, "btts_pct": 55},
    "Irán": {"form": "WDLWD", "goals_scored_avg": 1.2, "goals_conceded_avg": 1.1, "corners_avg": 4.3, "shots_avg": 10.7, "possession_avg": 48, "clean_sheets_pct": 28, "btts_pct": 52},
    "Irak": {"form": "LDWLD", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.3, "corners_avg": 4.0, "shots_avg": 9.8, "possession_avg": 46, "clean_sheets_pct": 25, "btts_pct": 53},
    "Australia": {"form": "DWLDW", "goals_scored_avg": 1.3, "goals_conceded_avg": 1.1, "corners_avg": 4.5, "shots_avg": 11.0, "possession_avg": 48, "clean_sheets_pct": 30, "btts_pct": 53},
    "Qatar": {"form": "DLWLD", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.4, "corners_avg": 3.9, "shots_avg": 9.5, "possession_avg": 45, "clean_sheets_pct": 22, "btts_pct": 55},

    # ====== OFC / Oceanía ======
    "Nueva Zelanda": {"form": "LDLDW", "goals_scored_avg": 0.9, "goals_conceded_avg": 1.5, "corners_avg": 3.7, "shots_avg": 9.0, "possession_avg": 42, "clean_sheets_pct": 18, "btts_pct": 58},

    # ====== Otros ======
    "Haití": {"form": "WLDLD", "goals_scored_avg": 1.0, "goals_conceded_avg": 1.5, "corners_avg": 3.8, "shots_avg": 9.3, "possession_avg": 43, "clean_sheets_pct": 20, "btts_pct": 58},
}

_MOCK_H2H = {
    "Argentina_Francia": {
        "matches_total": 12,
        "home_wins": 6,
        "draws": 3,
        "away_wins": 3,
        "goals_avg": 2.8,
        "last_5": [
            {"date": "2022-12-18", "home": "Argentina", "away": "Francia", "score": "3-3 (4-2p)", "competition": "World Cup Final"},
            {"date": "2018-06-30", "home": "Francia", "away": "Argentina", "score": "4-3", "competition": "World Cup R16"},
        ]
    },
    "Brasil_Alemania": {
        "matches_total": 24,
        "home_wins": 12,
        "draws": 5,
        "away_wins": 7,
        "goals_avg": 3.1,
        "last_5": [
            {"date": "2023-03-28", "home": "Alemania", "away": "Brasil", "score": "2-3", "competition": "Friendly"},
            {"date": "2018-03-27", "home": "Alemania", "away": "Brasil", "score": "0-1", "competition": "Friendly"},
        ]
    }
}


def _get_mock_stats(team_name: str) -> dict:
    """Devuelve stats mock para un equipo."""
    if team_name in _MOCK_STATS:
        return _MOCK_STATS[team_name]
    # Generar stats genéricas para equipos no listados
    return {
        "form": "WDWDW",
        "goals_scored_avg": 1.5,
        "goals_conceded_avg": 1.0,
        "corners_avg": 5.0,
        "shots_avg": 12.0,
        "possession_avg": 50,
        "clean_sheets_pct": 30,
        "btts_pct": 55
    }


def _get_mock_h2h(home_team: str, away_team: str) -> dict:
    """Devuelve H2H mock entre dos equipos."""
    key1 = f"{home_team}_{away_team}"
    key2 = f"{away_team}_{home_team}"
    
    if key1 in _MOCK_H2H:
        return _MOCK_H2H[key1]
    elif key2 in _MOCK_H2H:
        return _MOCK_H2H[key2]
    
    return {
        "matches_total": 5,
        "home_wins": 2,
        "draws": 1,
        "away_wins": 2,
        "goals_avg": 2.4,
        "last_5": []
    }


class StatsEnricher:
    """Enriquece los datos de partidos con estadísticas de API-Football y CornerPro."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or FOOTBALL_API_KEY
        self.use_mock = not bool(self.api_key)
    
    def enrich_match(self, match_data: dict) -> dict:
        """Añade estadísticas al datos de un partido.
        
        Args:
            match_data: Dict con datos del partido (home_team, away_team, etc.)
        
        Returns:
            Dict con estadísticas añadidas bajo la key 'stats'.
        """
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")
        
        cache_key = f"stats_{home_team}_{away_team}"
        cached = _stats_cache.get(cache_key)
        if cached:
            return cached
        
        if self.use_mock:
            stats = self._get_mock_enrichment(home_team, away_team)
        else:
            stats = self._fetch_real_stats(home_team, away_team)
        
        enriched = {
            "home": self._get_team_stats(home_team),
            "away": self._get_team_stats(away_team),
            "h2h": self._get_h2h(home_team, away_team),
            "insights": self._generate_insights(home_team, away_team)
        }
        
        _stats_cache[cache_key] = enriched
        return enriched
    
    def _get_team_stats(self, team_name: str) -> dict:
        """Obtiene estadísticas de un equipo."""
        if self.use_mock:
            return _get_mock_stats(team_name)
        return self._fetch_team_stats_api(team_name)
    
    def _get_h2h(self, home_team: str, away_team: str) -> dict:
        """Obtiene historial de enfrentamientos directos."""
        if self.use_mock:
            return _get_mock_h2h(home_team, away_team)
        return self._fetch_h2h_api(home_team, away_team)
    
    def _generate_insights(self, home_team: str, away_team: str) -> list[str]:
        """Genera insights textuales basados en las estadísticas."""
        home_stats = self._get_team_stats(home_team)
        away_stats = self._get_team_stats(away_team)
        h2h = self._get_h2h(home_team, away_team)
        
        insights = []
        
        # Insight de forma
        home_form = home_stats.get("form", "")
        away_form = away_stats.get("form", "")
        home_wins = home_form.count("W")
        away_wins = away_form.count("W")
        
        if home_wins >= 4:
            insights.append(f"🔥 {home_team} en racha excelente ({home_form})")
        elif away_wins >= 4:
            insights.append(f"🔥 {away_team} en racha excelente ({away_form})")
        
        # Insight de goles
        total_goals_avg = home_stats.get("goals_scored_avg", 0) + away_stats.get("goals_scored_avg", 0)
        if total_goals_avg > 3.5:
            insights.append(f"⚽ Promedio combinado alto de goles ({total_goals_avg:.1f})")
        elif total_goals_avg < 2.5:
            insights.append(f"🛡️ Partidos con pocos goles esperados ({total_goals_avg:.1f} avg)")
        
        # Insight de BTTS
        avg_btts = (home_stats.get("btts_pct", 50) + away_stats.get("btts_pct", 50)) / 2
        if avg_btts > 60:
            insights.append(f"🎯 Alta probabilidad de que ambos marquen ({avg_btts:.0f}%)")
        
        # Insight de corners
        corners_combined = home_stats.get("corners_avg", 5) + away_stats.get("corners_avg", 5)
        if corners_combined > 11:
            insights.append(f"🚩 Muchos corners esperados ({corners_combined:.1f} avg)")
        
        # Insight de posesión
        poss_diff = abs(home_stats.get("possession_avg", 50) - away_stats.get("possession_avg", 50))
        if poss_diff > 10:
            dominant = home_team if home_stats.get("possession_avg", 50) > away_stats.get("possession_avg", 50) else away_team
            insights.append(f"📊 {dominant} domina la posesión ({poss_diff:.0f}% diferencia)")
        
        # Insight de H2H
        if h2h.get("matches_total", 0) > 0:
            insights.append(f"📋 {h2h['matches_total']} enfrentamientos históricos ({h2h.get('home_wins', 0)}W-{h2h.get('draws', 0)}D-{h2h.get('away_wins', 0)}L)")
        
        return insights
    
    def _get_mock_enrichment(self, home_team: str, away_team: str) -> dict:
        """Genera enrichment con datos mock."""
        return {
            "home": _get_mock_stats(home_team),
            "away": _get_mock_stats(away_team),
            "h2h": _get_mock_h2h(home_team, away_team)
        }
    
    def _fetch_real_stats(self, home_team: str, away_team: str) -> dict:
        """Obtiene stats reales de API-Football."""
        if requests is None:
            return self._get_mock_enrichment(home_team, away_team)
        
        # TODO: Implementar llamada real a API-Football
        return self._get_mock_enrichment(home_team, away_team)
    
    def _fetch_team_stats_api(self, team_name: str) -> dict:
        """Obtiene stats de un equipo desde API-Football."""
        if requests is None:
            return _get_mock_stats(team_name)
        
        try:
            headers = {
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": "v3.football.api-sports.io"
            }
            # Buscar el equipo primero
            search_url = f"{FOOTBALL_API_BASE}/teams"
            params = {"search": team_name}
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                return _get_mock_stats(team_name)
            
            data = response.json()
            teams = data.get("response", [])
            if not teams:
                return _get_mock_stats(team_name)
            
            team_id = teams[0].get("team", {}).get("id")
            if not team_id:
                return _get_mock_stats(team_name)
            
            # Obtener estadísticas
            stats_url = f"{FOOTBALL_API_BASE}/teams/statistics"
            stats_params = {
                "team": team_id,
                "season": 2026,
                "league": 1  # World Cup
            }
            stats_response = requests.get(stats_url, headers=headers, params=stats_params, timeout=10)
            
            if stats_response.status_code != 200:
                return _get_mock_stats(team_name)
            
            stats_data = stats_response.json().get("response", {})
            
            # Parsear estadísticas
            form = stats_data.get("form", "")[:5]
            fixtures = stats_data.get("fixtures", {})
            goals = stats_data.get("goals", {})
            
            played = fixtures.get("played", {}).get("total", 1) or 1
            goals_for = goals.get("for", {}).get("total", {}).get("total", 0) or 0
            goals_against = goals.get("against", {}).get("total", {}).get("total", 0) or 0
            clean_sheets = stats_data.get("clean_sheet", {}).get("total", 0) or 0
            
            return {
                "form": form,
                "goals_scored_avg": round(goals_for / played, 1),
                "goals_conceded_avg": round(goals_against / played, 1),
                "corners_avg": 5.0,  # API-Football no da corners en stats generales
                "shots_avg": 12.0,
                "possession_avg": 50,
                "clean_sheets_pct": round((clean_sheets / played) * 100),
                "btts_pct": 50
            }
            
        except Exception as e:
            print(f"[StatsEnricher] Error fetching team stats: {e}")
            return _get_mock_stats(team_name)
    
    def _fetch_h2h_api(self, home_team: str, away_team: str) -> dict:
        """Obtiene H2H desde API-Football."""
        # TODO: Implementar búsqueda de IDs de equipos y llamada a /fixtures/headtohead
        return _get_mock_h2h(home_team, away_team)
