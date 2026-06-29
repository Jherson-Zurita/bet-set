"""
API Endpoint: GET /api/value-bets

Devuelve SOLO los partidos del Mundial 2026 que tienen value bets
(edge >= umbral), ordenados por edge descendente.
"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.odds_fetcher import OddsFetcher
from lib.value_calculator import ValueCalculator
from lib.world_cup_provider import WorldCupProvider
from api.matches import _merge_world_cup_with_odds


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parsear query params
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            # Umbral de edge personalizable via query param
            min_edge = float(params.get("min_edge", [3])[0])

            wc_provider = WorldCupProvider()
            fetcher = OddsFetcher()
            calculator = ValueCalculator(min_edge=min_edge)

            # 1. Fixture oficial del Mundial
            wc_matches = wc_provider.get_fixture(only_upcoming=True, window_days=7)

            # 2. Cruzar con cuotas
            odds_matches = fetcher.get_matches()
            wc_with_odds = _merge_world_cup_with_odds(wc_matches, odds_matches)

            # 3. Filtrar solo value bets (con cuotas disponibles)
            value_bets = calculator.get_value_bets_only(wc_with_odds)

            # 4. Enriquecer con metadatos del Mundial
            for vb in value_bets:
                wc_orig = next((m for m in wc_matches if m["id"] == vb["match_id"]), None)
                if wc_orig:
                    vb["group"] = wc_orig.get("group")
                    vb["stage"] = wc_orig.get("stage")
                    vb["venue"] = wc_orig.get("venue")
                    vb["matchday"] = wc_orig.get("matchday")

            response = {
                "success": True,
                "count": len(value_bets),
                "min_edge_threshold": min_edge,
                "is_mock": {
                    "world_cup": wc_provider.is_mock,
                    "odds": fetcher.is_mock,
                },
                "competition": "FIFA World Cup 2026",
                "value_bets": value_bets,
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
