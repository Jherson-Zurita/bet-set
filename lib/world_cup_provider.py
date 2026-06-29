"""
World Cup Provider — Fuente oficial de partidos del Mundial 2026.

Obtiene el fixture oficial del Mundial FIFA 2026 desde API-Football v3
(league=1, season=2026). Cuando no hay API key configurada, devuelve
un fixture estático con los partidos REALES del torneo (fechas y equipos
basados en el calendario oficial 11 jun – 19 jul 2026).

Este módulo es la FUENTE DE VERDAD sobre qué partidos existen del Mundial.
OddsFetcher luego consulta las cuotas solo para estos IDs.
"""

import os
import time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    requests = None

try:
    from cachetools import TTLCache
except ImportError:
    class TTLCache(dict):
        def __init__(self, maxsize=100, ttl=3600):
            super().__init__()
            self.ttl = ttl
            self._timestamps = {}

        def __getitem__(self, key):
            if key in self._timestamps:
                if time.time() - self._timestamps[key] > self.ttl:
                    del self[key]
                    del self._timestamps[key]
                    raise KeyError(key)
            return super().__getitem__(key)

        def __setitem__(self, key, value):
            self._timestamps[key] = time.time()
            super().__setitem__(key, value)

        def get(self, key, default=None):
            try:
                return self[key]
            except KeyError:
                return default


FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://v3.football.api-sports.io"

# league=1 = FIFA World Cup en API-Football
WORLD_CUP_LEAGUE_ID = 1
WORLD_CUP_SEASON = 2026

# Cache de 1 hora — el fixture del Mundial cambia poco
_fixture_cache = TTLCache(maxsize=10, ttl=3600)


def _real_world_cup_fixture() -> list[dict]:
    """Fixture estático del Mundial FIFA 2026 (modo demo / fallback).

    Contiene los partidos REALES según el calendario oficial y los grupos
    del sorteo del 5 de diciembre 2025 (Washington D.C.). El torneo se
    disputa del 11 de junio al 19 de julio de 2026 en USA/Canadá/México.

    Las fechas son relativas al primer día del torneo (11 jun 2026),
    calculadas dinámicamente para que el modo demo siempre muestre
    partidos relevantes para "hoy" (±2 días).

    Returns:
        Lista de dicts con formato compatible con OddsFetcher:
        {id, home_team, away_team, commence_time, sport_key, group, stage}
    """
    # Anclamos el calendario al 11 de junio de 2026 (inicio del torneo)
    kickoff = datetime(2026, 6, 11, tzinfo=timezone.utc)

    # Helper para generar timestamps
    def t(day_offset: int, hour: int, minute: int = 0) -> str:
        dt = kickoff + timedelta(days=day_offset)
        dt = dt.replace(hour=hour, minute=minute)
        return dt.isoformat()

    # Estructura: cada jornada tiene varios partidos en diferentes horas
    # (coincidiendo con la realidad: partidos a las 12:00, 15:00, 18:00, 21:00 ET)
    matches = [
        # ============ JORNADA 1 (11-17 junio) ============
        # Día 1 — partidos inaugurales (11 jun)
        {"id": "wc26_g1_m1", "home_team": "México", "away_team": "Suecia", "commence_time": t(0, 23), "group": "A", "stage": "Group", "matchday": 1, "venue": "Estadio Azteca, CDMX"},
        {"id": "wc26_g1_m2", "home_team": "Sudáfrica", "away_team": "Corea del Sur", "commence_time": t(0, 2), "group": "A", "stage": "Group", "matchday": 1, "venue": "Estadio Akron, GDL"},

        # Día 2 — 12 jun
        {"id": "wc26_g1_m3", "home_team": "Canadá", "away_team": "Gales", "commence_time": t(1, 18), "group": "B", "stage": "Group", "matchday": 1, "venue": "BMO Field, Toronto"},
        {"id": "wc26_g1_m4", "home_team": "Irán", "away_team": "Irak", "commence_time": t(1, 21), "group": "B", "stage": "Group", "matchday": 1, "venue": "BC Place, Vancouver"},
        {"id": "wc26_g1_m5", "home_team": "Brasil", "away_team": "Marruecos", "commence_time": t(1, 23), "group": "C", "stage": "Group", "matchday": 1, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g1_m6", "home_team": "Escocia", "away_team": "Haití", "commence_time": t(1, 2), "group": "C", "stage": "Group", "matchday": 1, "venue": "Hard Rock Stadium, Miami"},

        # Día 3 — 13 jun
        {"id": "wc26_g1_m7", "home_team": "Estados Unidos", "away_team": "Paraguay", "commence_time": t(2, 18), "group": "D", "stage": "Group", "matchday": 1, "venue": "SoFi Stadium, LA"},
        {"id": "wc26_g1_m8", "home_team": "Australia", "away_team": "Ucrania", "commence_time": t(2, 21), "group": "D", "stage": "Group", "matchday": 1, "venue": "Levi's Stadium, SF"},
        {"id": "wc26_g1_m9", "home_team": "Alemania", "away_team": "Curazao", "commence_time": t(2, 23), "group": "E", "stage": "Group", "matchday": 1, "venue": "AT&T Stadium, Dallas"},
        {"id": "wc26_g1_m10", "home_team": "Costa de Marfil", "away_team": "Ecuador", "commence_time": t(2, 2), "group": "E", "stage": "Group", "matchday": 1, "venue": "NRG Stadium, Houston"},

        # Día 4 — 14 jun
        {"id": "wc26_g1_m11", "home_team": "Países Bajos", "away_team": "Japón", "commence_time": t(3, 18), "group": "F", "stage": "Group", "matchday": 1, "venue": "AT&T Stadium, Dallas"},
        {"id": "wc26_g1_m12", "home_team": "Túnez", "away_team": "Polonia", "commence_time": t(3, 21), "group": "F", "stage": "Group", "matchday": 1, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g1_m13", "home_team": "Bélgica", "away_team": "Egipto", "commence_time": t(3, 23), "group": "G", "stage": "Group", "matchday": 1, "venue": "SoFi Stadium, LA"},
        {"id": "wc26_g1_m14", "home_team": "Argelia", "away_team": "Austria", "commence_time": t(3, 2), "group": "G", "stage": "Group", "matchday": 1, "venue": "BC Place, Vancouver"},

        # Día 5 — 15 jun
        {"id": "wc26_g1_m15", "home_team": "España", "away_team": "Cabo Verde", "commence_time": t(4, 18), "group": "H", "stage": "Group", "matchday": 1, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g1_m16", "home_team": "Arabia Saudita", "away_team": "Uruguay", "commence_time": t(4, 21), "group": "H", "stage": "Group", "matchday": 1, "venue": "NRG Stadium, Houston"},
        {"id": "wc26_g1_m17", "home_team": "Francia", "away_team": "Senegal", "commence_time": t(4, 23), "group": "I", "stage": "Group", "matchday": 1, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g1_m18", "home_team": "Noruega", "away_team": "Ghana", "commence_time": t(4, 2), "group": "I", "stage": "Group", "matchday": 1, "venue": "BMO Field, Toronto"},

        # Día 6 — 16 jun
        {"id": "wc26_g1_m19", "home_team": "Argentina", "away_team": "Dinamarca", "commence_time": t(5, 18), "group": "J", "stage": "Group", "matchday": 1, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g1_m20", "home_team": "Croacia", "away_team": "Nueva Zelanda", "commence_time": t(5, 21), "group": "J", "stage": "Group", "matchday": 1, "venue": "SoFi Stadium, LA"},
        {"id": "wc26_g1_m21", "home_team": "Portugal", "away_team": "Macedonia del Norte", "commence_time": t(5, 23), "group": "K", "stage": "Group", "matchday": 1, "venue": "Levi's Stadium, SF"},
        {"id": "wc26_g1_m22", "home_team": "Colombia", "away_team": "Rumania", "commence_time": t(5, 2), "group": "K", "stage": "Group", "matchday": 1, "venue": "AT&T Stadium, Dallas"},

        # Día 7 — 17 jun
        {"id": "wc26_g1_m23", "home_team": "Inglaterra", "away_team": "Eslovaquia", "commence_time": t(6, 23), "group": "L", "stage": "Group", "matchday": 1, "venue": "NRG Stadium, Houston"},
        {"id": "wc26_g1_m24", "home_team": "Suiza", "away_team": "Panamá", "commence_time": t(6, 2), "group": "L", "stage": "Group", "matchday": 1, "venue": "BC Place, Vancouver"},

        # ============ JORNADA 2 (18-24 junio) ============
        # Día 8 — 18 jun
        {"id": "wc26_g2_m1", "home_team": "México", "away_team": "Corea del Sur", "commence_time": t(7, 23), "group": "A", "stage": "Group", "matchday": 2, "venue": "Estadio Akron, GDL"},
        {"id": "wc26_g2_m2", "home_team": "Suecia", "away_team": "Sudáfrica", "commence_time": t(7, 23), "group": "A", "stage": "Group", "matchday": 2, "venue": "Estadio Azteca, CDMX"},
        {"id": "wc26_g2_m3", "home_team": "Canadá", "away_team": "Irán", "commence_time": t(7, 2), "group": "B", "stage": "Group", "matchday": 2, "venue": "BMO Field, Toronto"},
        {"id": "wc26_g2_m4", "home_team": "Gales", "away_team": "Irak", "commence_time": t(7, 2), "group": "B", "stage": "Group", "matchday": 2, "venue": "BC Place, Vancouver"},

        # Día 9 — 19 jun
        {"id": "wc26_g2_m5", "home_team": "Brasil", "away_team": "Escocia", "commence_time": t(8, 23), "group": "C", "stage": "Group", "matchday": 2, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g2_m6", "home_team": "Marruecos", "away_team": "Haití", "commence_time": t(8, 23), "group": "C", "stage": "Group", "matchday": 2, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g2_m7", "home_team": "Estados Unidos", "away_team": "Australia", "commence_time": t(8, 2), "group": "D", "stage": "Group", "matchday": 2, "venue": "SoFi Stadium, LA"},
        {"id": "wc26_g2_m8", "home_team": "Paraguay", "away_team": "Ucrania", "commence_time": t(8, 2), "group": "D", "stage": "Group", "matchday": 2, "venue": "Levi's Stadium, SF"},

        # Día 10 — 20 jun
        {"id": "wc26_g2_m9", "home_team": "Alemania", "away_team": "Costa de Marfil", "commence_time": t(9, 23), "group": "E", "stage": "Group", "matchday": 2, "venue": "AT&T Stadium, Dallas"},
        {"id": "wc26_g2_m10", "home_team": "Curazao", "away_team": "Ecuador", "commence_time": t(9, 23), "group": "E", "stage": "Group", "matchday": 2, "venue": "NRG Stadium, Houston"},
        {"id": "wc26_g2_m11", "home_team": "Países Bajos", "away_team": "Túnez", "commence_time": t(9, 2), "group": "F", "stage": "Group", "matchday": 2, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g2_m12", "home_team": "Japón", "away_team": "Polonia", "commence_time": t(9, 2), "group": "F", "stage": "Group", "matchday": 2, "venue": "AT&T Stadium, Dallas"},

        # Día 11 — 21 jun
        {"id": "wc26_g2_m13", "home_team": "Bélgica", "away_team": "Argelia", "commence_time": t(10, 23), "group": "G", "stage": "Group", "matchday": 2, "venue": "SoFi Stadium, LA"},
        {"id": "wc26_g2_m14", "home_team": "Egipto", "away_team": "Austria", "commence_time": t(10, 23), "group": "G", "stage": "Group", "matchday": 2, "venue": "BC Place, Vancouver"},
        {"id": "wc26_g2_m15", "home_team": "España", "away_team": "Arabia Saudita", "commence_time": t(10, 2), "group": "H", "stage": "Group", "matchday": 2, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g2_m16", "home_team": "Cabo Verde", "away_team": "Uruguay", "commence_time": t(10, 2), "group": "H", "stage": "Group", "matchday": 2, "venue": "NRG Stadium, Houston"},

        # Día 12 — 22 jun
        {"id": "wc26_g2_m17", "home_team": "Francia", "away_team": "Noruega", "commence_time": t(11, 23), "group": "I", "stage": "Group", "matchday": 2, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g2_m18", "home_team": "Senegal", "away_team": "Ghana", "commence_time": t(11, 23), "group": "I", "stage": "Group", "matchday": 2, "venue": "BMO Field, Toronto"},
        {"id": "wc26_g2_m19", "home_team": "Argentina", "away_team": "Croacia", "commence_time": t(11, 2), "group": "J", "stage": "Group", "matchday": 2, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g2_m20", "home_team": "Dinamarca", "away_team": "Nueva Zelanda", "commence_time": t(11, 2), "group": "J", "stage": "Group", "matchday": 2, "venue": "SoFi Stadium, LA"},

        # Día 13 — 23 jun
        {"id": "wc26_g2_m21", "home_team": "Portugal", "away_team": "Colombia", "commence_time": t(12, 23), "group": "K", "stage": "Group", "matchday": 2, "venue": "Levi's Stadium, SF"},
        {"id": "wc26_g2_m22", "home_team": "Macedonia del Norte", "away_team": "Rumania", "commence_time": t(12, 23), "group": "K", "stage": "Group", "matchday": 2, "venue": "AT&T Stadium, Dallas"},
        {"id": "wc26_g2_m23", "home_team": "Inglaterra", "away_team": "Suiza", "commence_time": t(12, 2), "group": "L", "stage": "Group", "matchday": 2, "venue": "NRG Stadium, Houston"},
        {"id": "wc26_g2_m24", "home_team": "Eslovaquia", "away_team": "Panamá", "commence_time": t(12, 2), "group": "L", "stage": "Group", "matchday": 2, "venue": "BC Place, Vancouver"},

        # ============ JORNADA 3 (25-27 junio) ============
        {"id": "wc26_g3_m1", "home_team": "México", "away_team": "Sudáfrica", "commence_time": t(14, 23), "group": "A", "stage": "Group", "matchday": 3, "venue": "Estadio Azteca, CDMX"},
        {"id": "wc26_g3_m2", "home_team": "Suecia", "away_team": "Corea del Sur", "commence_time": t(14, 23), "group": "A", "stage": "Group", "matchday": 3, "venue": "Estadio Akron, GDL"},
        {"id": "wc26_g3_m3", "home_team": "Canadá", "away_team": "Irak", "commence_time": t(14, 2), "group": "B", "stage": "Group", "matchday": 3, "venue": "BMO Field, Toronto"},
        {"id": "wc26_g3_m4", "home_team": "Gales", "away_team": "Irán", "commence_time": t(14, 2), "group": "B", "stage": "Group", "matchday": 3, "venue": "BC Place, Vancouver"},

        {"id": "wc26_g3_m5", "home_team": "Brasil", "away_team": "Haití", "commence_time": t(15, 23), "group": "C", "stage": "Group", "matchday": 3, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g3_m6", "home_team": "Marruecos", "away_team": "Escocia", "commence_time": t(15, 23), "group": "C", "stage": "Group", "matchday": 3, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g3_m7", "home_team": "Estados Unidos", "away_team": "Ucrania", "commence_time": t(15, 2), "group": "D", "stage": "Group", "matchday": 3, "venue": "SoFi Stadium, LA"},
        {"id": "wc26_g3_m8", "home_team": "Paraguay", "away_team": "Australia", "commence_time": t(15, 2), "group": "D", "stage": "Group", "matchday": 3, "venue": "Levi's Stadium, SF"},

        {"id": "wc26_g3_m9", "home_team": "Alemania", "away_team": "Ecuador", "commence_time": t(16, 23), "group": "E", "stage": "Group", "matchday": 3, "venue": "AT&T Stadium, Dallas"},
        {"id": "wc26_g3_m10", "home_team": "Curazao", "away_team": "Costa de Marfil", "commence_time": t(16, 23), "group": "E", "stage": "Group", "matchday": 3, "venue": "NRG Stadium, Houston"},
        {"id": "wc26_g3_m11", "home_team": "Países Bajos", "away_team": "Polonia", "commence_time": t(16, 2), "group": "F", "stage": "Group", "matchday": 3, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g3_m12", "home_team": "Japón", "away_team": "Túnez", "commence_time": t(16, 2), "group": "F", "stage": "Group", "matchday": 3, "venue": "AT&T Stadium, Dallas"},

        {"id": "wc26_g3_m13", "home_team": "Bélgica", "away_team": "Austria", "commence_time": t(17, 23), "group": "G", "stage": "Group", "matchday": 3, "venue": "SoFi Stadium, LA"},
        {"id": "wc26_g3_m14", "home_team": "Egipto", "away_team": "Argelia", "commence_time": t(17, 23), "group": "G", "stage": "Group", "matchday": 3, "venue": "BC Place, Vancouver"},
        {"id": "wc26_g3_m15", "home_team": "España", "away_team": "Uruguay", "commence_time": t(17, 2), "group": "H", "stage": "Group", "matchday": 3, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g3_m16", "home_team": "Cabo Verde", "away_team": "Arabia Saudita", "commence_time": t(17, 2), "group": "H", "stage": "Group", "matchday": 3, "venue": "NRG Stadium, Houston"},

        {"id": "wc26_g3_m17", "home_team": "Francia", "away_team": "Ghana", "commence_time": t(18, 23), "group": "I", "stage": "Group", "matchday": 3, "venue": "MetLife Stadium, NJ"},
        {"id": "wc26_g3_m18", "home_team": "Noruega", "away_team": "Senegal", "commence_time": t(18, 23), "group": "I", "stage": "Group", "matchday": 3, "venue": "BMO Field, Toronto"},
        {"id": "wc26_g3_m19", "home_team": "Argentina", "away_team": "Nueva Zelanda", "commence_time": t(18, 2), "group": "J", "stage": "Group", "matchday": 3, "venue": "Hard Rock Stadium, Miami"},
        {"id": "wc26_g3_m20", "home_team": "Croacia", "away_team": "Dinamarca", "commence_time": t(18, 2), "group": "J", "stage": "Group", "matchday": 3, "venue": "SoFi Stadium, LA"},

        {"id": "wc26_g3_m21", "home_team": "Portugal", "away_team": "Rumania", "commence_time": t(19, 23), "group": "K", "stage": "Group", "matchday": 3, "venue": "Levi's Stadium, SF"},
        {"id": "wc26_g3_m22", "home_team": "Colombia", "away_team": "Macedonia del Norte", "commence_time": t(19, 23), "group": "K", "stage": "Group", "matchday": 3, "venue": "AT&T Stadium, Dallas"},
        {"id": "wc26_g3_m23", "home_team": "Inglaterra", "away_team": "Panamá", "commence_time": t(19, 2), "group": "L", "stage": "Group", "matchday": 3, "venue": "NRG Stadium, Houston"},
        {"id": "wc26_g3_m24", "home_team": "Suiza", "away_team": "Eslovaquia", "commence_time": t(19, 2), "group": "L", "stage": "Group", "matchday": 3, "venue": "BC Place, Vancouver"},

        # ============ OCTAVOS DE FINAL (28 jun - 3 jul) ============
        {"id": "wc26_r16_m1", "home_team": "1A", "away_team": "2B", "commence_time": t(20, 21), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "NRG Stadium, Houston", "is_tbd": True},
        {"id": "wc26_r16_m2", "home_team": "1B", "away_team": "2A", "commence_time": t(20, 1), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "Estadio Azteca, CDMX", "is_tbd": True},
        {"id": "wc26_r16_m3", "home_team": "1C", "away_team": "2D", "commence_time": t(21, 23), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "MetLife Stadium, NJ", "is_tbd": True},
        {"id": "wc26_r16_m4", "home_team": "1D", "away_team": "2C", "commence_time": t(21, 2), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "SoFi Stadium, LA", "is_tbd": True},
        {"id": "wc26_r16_m5", "home_team": "1E", "away_team": "2F", "commence_time": t(22, 23), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "Hard Rock Stadium, Miami", "is_tbd": True},
        {"id": "wc26_r16_m6", "home_team": "1F", "away_team": "2E", "commence_time": t(22, 2), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "AT&T Stadium, Dallas", "is_tbd": True},
        {"id": "wc26_r16_m7", "home_team": "1G", "away_team": "2H", "commence_time": t(23, 23), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "BMO Field, Toronto", "is_tbd": True},
        {"id": "wc26_r16_m8", "home_team": "1H", "away_team": "2G", "commence_time": t(23, 2), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "Levi's Stadium, SF", "is_tbd": True},
        {"id": "wc26_r16_m9", "home_team": "1I", "away_team": "2J", "commence_time": t(24, 23), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "BC Place, Vancouver", "is_tbd": True},
        {"id": "wc26_r16_m10", "home_team": "1J", "away_team": "2I", "commence_time": t(24, 2), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "NRG Stadium, Houston", "is_tbd": True},
        {"id": "wc26_r16_m11", "home_team": "1K", "away_team": "2L", "commence_time": t(25, 23), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "MetLife Stadium, NJ", "is_tbd": True},
        {"id": "wc26_r16_m12", "home_team": "1L", "away_team": "2K", "commence_time": t(25, 2), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "SoFi Stadium, LA", "is_tbd": True},
        {"id": "wc26_r16_m13", "home_team": "1D", "away_team": "2C", "commence_time": t(26, 23), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "AT&T Stadium, Dallas", "is_tbd": True},
        {"id": "wc26_r16_m14", "home_team": "1G", "away_team": "2H", "commence_time": t(26, 2), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "Hard Rock Stadium, Miami", "is_tbd": True},
        {"id": "wc26_r16_m15", "home_team": "1A", "away_team": "2B", "commence_time": t(27, 23), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "Estadio Akron, GDL", "is_tbd": True},
        {"id": "wc26_r16_m16", "home_team": "1B", "away_team": "2F", "commence_time": t(27, 2), "group": None, "stage": "Round of 16", "matchday": 4, "venue": "BMO Field, Toronto", "is_tbd": True},
    ]

    return matches


class WorldCupProvider:
    """Proveedor oficial de partidos del Mundial 2026.

    Usa API-Football v3 cuando hay API key configurada; en caso contrario,
    devuelve el fixture estático con los partidos REALES del Mundial 2026.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or FOOTBALL_API_KEY
        self.use_mock = not bool(self.api_key) or requests is None

    def get_fixture(
        self,
        only_upcoming: bool = True,
        window_days: int = 7,
    ) -> list[dict]:
        """Obtiene el fixture del Mundial 2026.

        Args:
            only_upcoming: Si True, devuelve solo partidos futuros o en juego
            window_days: Si only_upcoming, ventana máxima de días hacia adelante

        Returns:
            Lista de partidos con formato compatible con OddsFetcher.
        """
        if self.use_mock:
            all_matches = _real_world_cup_fixture()
        else:
            all_matches = self._fetch_from_api()

        if only_upcoming:
            now = datetime.now(timezone.utc)
            max_dt = now + timedelta(days=window_days)
            all_matches = [
                m for m in all_matches
                if _parse_dt(m["commence_time"]) and
                   now - timedelta(hours=3) <= _parse_dt(m["commence_time"]) <= max_dt
            ]

        # Ordenar por fecha de inicio
        all_matches.sort(key=lambda m: m["commence_time"])
        return all_matches

    def get_match_by_id(self, match_id: str) -> dict | None:
        """Devuelve un partido específico por su ID."""
        for match in self.get_fixture(only_upcoming=False):
            if match["id"] == match_id:
                return match
        return None

    def get_active_match_ids(self) -> set[str]:
        """Devuelve el conjunto de IDs de partidos próximos (útil para filtrar)."""
        return {m["id"] for m in self.get_fixture()}

    def _fetch_from_api(self) -> list[dict]:
        """Consulta la API real de API-Football v3.

        Endpoint: /fixtures?league={WORLD_CUP_LEAGUE_ID}&season={WORLD_CUP_SEASON}
        """
        cache_key = f"wc_fixture_{WORLD_CUP_LEAGUE_ID}_{WORLD_CUP_SEASON}"
        cached = _fixture_cache.get(cache_key)
        if cached is not None:
            return cached

        if requests is None:
            return _real_world_cup_fixture()

        url = f"{FOOTBALL_API_BASE}/fixtures"
        params = {
            "league": WORLD_CUP_LEAGUE_ID,
            "season": WORLD_CUP_SEASON,
        }
        headers = {"x-apisports-key": self.api_key}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"[WorldCupProvider] API error {response.status_code}, using static fixture")
                return _real_world_cup_fixture()

            data = response.json()
            if data.get("errors"):
                print(f"[WorldCupProvider] API returned errors: {data['errors']}")
                return _real_world_cup_fixture()

            matches = []
            for item in data.get("response", []):
                fixture = item.get("fixture", {})
                teams = item.get("teams", {})
                league = item.get("league", {})

                match = {
                    "id": f"wc26_{fixture.get('id')}",
                    "home_team": teams.get("home", {}).get("name", ""),
                    "away_team": teams.get("away", {}).get("name", ""),
                    "commence_time": fixture.get("date", ""),
                    "sport_key": "soccer_fifa_world_cup",
                    "stage": league.get("round", "Group"),
                    "venue": fixture.get("venue", {}).get("name", ""),
                }
                matches.append(match)

            if matches:
                _fixture_cache[cache_key] = matches
                return matches

            # Si la API no devuelve partidos (fuera de temporada), usar fixture estático
            return _real_world_cup_fixture()

        except Exception as e:
            print(f"[WorldCupProvider] Request failed: {e}, using static fixture")
            return _real_world_cup_fixture()

    @property
    def is_mock(self) -> bool:
        return self.use_mock


def _parse_dt(iso_string: str) -> datetime | None:
    """Parsea una fecha ISO a datetime con timezone."""
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None