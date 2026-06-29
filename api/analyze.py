"""
API Endpoint: POST /api/analyze

Fuerza la regeneración del análisis AI para un partido del Mundial 2026.
Invalida el cache y genera un nuevo análisis con datos frescos.
"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.odds_fetcher import OddsFetcher
from lib.value_calculator import ValueCalculator
from lib.stats_enricher import StatsEnricher
from lib.ai_analyzer import AIAnalyzer
from lib.world_cup_provider import WorldCupProvider


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Leer body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            data = json.loads(body)

            match_id = data.get("match_id")

            if not match_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Missing required field: match_id"
                }).encode("utf-8"))
                return

            wc_provider = WorldCupProvider()
            fetcher = OddsFetcher()

            wc_match = wc_provider.get_match_by_id(match_id)
            odds_match = fetcher.get_match_by_id(match_id)

            if not wc_match and not odds_match:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": f"Match not found: {match_id}"
                }).encode("utf-8"))
                return

            if wc_match:
                match_data = {
                    "id": wc_match["id"],
                    "home_team": wc_match["home_team"],
                    "away_team": wc_match["away_team"],
                    "commence_time": wc_match["commence_time"],
                    "sport_key": "soccer_fifa_world_cup",
                    "sport_title": "FIFA World Cup 2026",
                    "bookmakers": (odds_match or {}).get("bookmakers", {}),
                    "stage": wc_match.get("stage"),
                    "group": wc_match.get("group"),
                    "venue": wc_match.get("venue"),
                }
            else:
                match_data = odds_match

            # Recalcular todo
            calculator = ValueCalculator()
            value_data = calculator.analyze_match(match_data)

            enricher = StatsEnricher()
            stats = enricher.enrich_match(match_data)

            # Forzar nuevo análisis AI (ignora cache)
            analyzer = AIAnalyzer()
            ai_analysis = analyzer.analyze_match(
                match_data, value_data, stats, force_refresh=True
            )

            response = {
                "success": True,
                "message": "Analysis regenerated successfully",
                "ai_analysis": ai_analysis,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
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
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
