"""
API Endpoint: GET /api/matches

Devuelve los partidos del Mundial 2026 con cuotas de bet365 y Pinnacle,
incluyendo el edge calculado por mercado.

Flujo híbrido:
  1. WorldCupProvider → fixture oficial del Mundial 2026
  2. OddsFetcher → cuotas de The Odds API (filtradas por IDs del Mundial)
  3. ValueCalculator → edge por mercado
  4. Cruce: partidos del Mundial con sus cuotas + edge
"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.odds_fetcher import OddsFetcher
from lib.value_calculator import ValueCalculator
from lib.world_cup_provider import WorldCupProvider


def _merge_world_cup_with_odds(
    wc_matches: list[dict],
    odds_matches: list[dict],
) -> list[dict]:
    """Cruza los partidos del Mundial (WorldCupProvider) con las cuotas (OddsFetcher).

    Lógica de matching:
      1. Por ID exacto (si OddsFetcher devuelve IDs del Mundial)
      2. Por nombre de equipos (Home + Away) — útil si los IDs difieren entre APIs

    Args:
        wc_matches: Partidos del Mundial (fuente de verdad)
        odds_matches: Partidos con cuotas de The Odds API

    Returns:
        Lista de partidos del Mundial con cuotas añadidas (si están disponibles).
    """
    # Indexar cuotas por (home, away) para matching flexible
    odds_by_teams = {}
    for om in odds_matches:
        key = (om["home_team"].lower().strip(), om["away_team"].lower().strip())
        odds_by_teams[key] = om

    merged = []
    for wc in wc_matches:
        home = wc["home_team"]
        away = wc["away_team"]
        key = (home.lower().strip(), away.lower().strip())

        # Buscar cuotas coincidentes
        odds_match = odds_by_teams.get(key)
        if not odds_match:
            # Intento fuzzy: buscar match parcial
            for (h, a), om in odds_by_teams.items():
                if (h in home.lower() or home.lower() in h) and (a in away.lower() or away.lower() in a):
                    odds_match = om
                    break

        if odds_match:
            wc_with_odds = {
                **wc,
                "sport_title": "FIFA World Cup 2026",
                "bookmakers": odds_match.get("bookmakers", {}),
            }
            merged.append(wc_with_odds)
        else:
            # Sin cuotas — partido pendiente de cuotas
            merged.append({
                **wc,
                "sport_title": "FIFA World Cup 2026",
                "bookmakers": {},
                "odds_pending": True,
            })

    return merged


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            wc_provider = WorldCupProvider()
            fetcher = OddsFetcher()
            calculator = ValueCalculator()

            # 1. Obtener partidos oficiales del Mundial (próximos 7 días)
            wc_matches = wc_provider.get_fixture(
                only_upcoming=True,
                window_days=7,
            )

            # 2. Obtener cuotas y cruzar con partidos del Mundial
            odds_matches = fetcher.get_matches()
            wc_with_odds = _merge_world_cup_with_odds(wc_matches, odds_matches)

            # 3. Calcular edge para cada partido
            analyzed = calculator.analyze_matches(wc_with_odds)

            # 4. Enriquecer con metadatos del Mundial
            for match in analyzed:
                wc_orig = next((m for m in wc_matches if m["id"] == match["match_id"]), None)
                if wc_orig:
                    match["group"] = wc_orig.get("group")
                    match["stage"] = wc_orig.get("stage")
                    match["matchday"] = wc_orig.get("matchday")
                    match["venue"] = wc_orig.get("venue")
                    match["is_tbd"] = wc_orig.get("is_tbd", False)

            response = {
                "success": True,
                "count": len(analyzed),
                "is_mock": {
                    "world_cup": wc_provider.is_mock,
                    "odds": fetcher.is_mock,
                },
                "remaining_requests": fetcher.remaining_requests,
                "competition": "FIFA World Cup 2026",
                "matches": analyzed,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "s-maxage=300, stale-while-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_response = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(error_response).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
