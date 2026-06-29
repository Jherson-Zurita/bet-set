"""
API Endpoint: GET /api/match?id={match_id}

Devuelve el detalle completo de un partido del Mundial 2026 incluyendo:
- Cuotas y edge por mercado
- Estadísticas enriquecidas
- Análisis AI con recomendación
"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.odds_fetcher import OddsFetcher
from lib.value_calculator import ValueCalculator
from lib.stats_enricher import StatsEnricher
from lib.ai_analyzer import AIAnalyzer
from lib.world_cup_provider import WorldCupProvider


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parsear query params
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            match_id = params.get("id", [None])[0]

            if not match_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Missing required parameter: id"
                }).encode("utf-8"))
                return

            wc_provider = WorldCupProvider()
            fetcher = OddsFetcher()

            # 1. Buscar partido en WorldCupProvider primero (autoridad)
            wc_match = wc_provider.get_match_by_id(match_id)

            # 2. Buscar cuotas (puede que no estén disponibles)
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

            # Construir match_data combinado
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
                    "is_tbd": wc_match.get("is_tbd", False),
                }
            else:
                match_data = odds_match

            # Calcular edge
            calculator = ValueCalculator()
            value_data = calculator.analyze_match(match_data)

            # Enriquecer con estadísticas
            enricher = StatsEnricher()
            stats = enricher.enrich_match(match_data)

            # Generar análisis AI
            analyzer = AIAnalyzer()
            ai_analysis = analyzer.analyze_match(match_data, value_data, stats)

            # Construir respuesta completa
            response = {
                "success": True,
                "match": value_data,
                "stats": stats,
                "ai_analysis": ai_analysis,
                "is_mock": {
                    "odds": fetcher.is_mock,
                    "ai": analyzer.is_mock,
                    "world_cup": wc_provider.is_mock,
                },
                "odds_pending": not bool(odds_match),
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
