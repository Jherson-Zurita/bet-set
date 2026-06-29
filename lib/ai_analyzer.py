"""
AI Analyzer — Módulo de análisis inteligente con Gemini API.

Recibe datos crudos (cuotas + edge + stats) y produce un análisis
en lenguaje natural en español con la recomendación final.
"""

import os
import json
import time

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from cachetools import TTLCache
except ImportError:
    class TTLCache(dict):
        def __init__(self, maxsize=100, ttl=300):
            super().__init__()
            self.ttl = ttl
        def get(self, key, default=None):
            return super().get(key, default)


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Cache de 30 minutos para análisis
_analysis_cache = TTLCache(maxsize=50, ttl=1800)

# Prompt del sistema para análisis de apuestas
SYSTEM_PROMPT = """Eres un analista profesional de apuestas deportivas. Tu trabajo es analizar datos de cuotas y estadísticas para recomendar la mejor apuesta de valor.

REGLAS:
1. Responde SIEMPRE en español.
2. Sé directo y concreto — no rellenes con frases genéricas.
3. Tu análisis debe ser conciso (máximo 200 palabras).
4. Justifica tu recomendación con datos específicos.
5. Siempre menciona el riesgo y la varianza esperada.
6. Responde EXCLUSIVAMENTE en formato JSON válido.

FORMATO DE RESPUESTA (JSON estricto):
{
  "recommended_bet": {
    "market": "1X2 | Over/Under | BTTS",
    "selection": "nombre de la selección",
    "odds": 0.00,
    "edge": 0.00,
    "confidence": "alta | media | baja"
  },
  "analysis": "Texto del análisis en español...",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "risk_level": "bajo | medio | alto",
  "alternative_bet": {
    "market": "mercado alternativo",
    "selection": "selección",
    "reason": "razón breve"
  }
}"""


def _generate_mock_analysis(match_data: dict, value_data: dict, stats: dict = None) -> dict:
    """Genera un análisis mock para desarrollo sin API key.
    
    Produce un análisis realista basado en los datos disponibles.
    """
    home = match_data.get("home_team", "Local")
    away = match_data.get("away_team", "Visitante")
    
    best_bet = value_data.get("best_bet", {})
    if not best_bet:
        return {
            "recommended_bet": None,
            "analysis": f"No se encontraron apuestas de valor significativas para {home} vs {away}.",
            "key_factors": ["Sin edge suficiente en ningún mercado"],
            "risk_level": "N/A",
            "alternative_bet": None
        }
    
    market = best_bet.get("market", "h2h")
    outcome = best_bet.get("outcome", "")
    odds = best_bet.get("odds", 0)
    edge = best_bet.get("edge", 0)
    
    # Determinar nombre del mercado en español
    market_names = {
        "h2h": "Resultado Final (1X2)",
        "totals": "Over/Under Goles",
        "btts": "Ambos Marcan"
    }
    market_display = market_names.get(market, market)
    
    # Generar análisis basado en el edge
    if edge > 8:
        confidence = "alta"
        risk = "medio"
        analysis = (
            f"**{home} vs {away}** presenta una oportunidad de valor excepcional. "
            f"El mercado de {market_display} ({outcome}) ofrece un edge del {edge}%, "
            f"significativamente por encima de nuestro umbral. "
            f"Pinnacle valora esta probabilidad más alta que lo que bet365 sugiere con su cuota de {odds}. "
        )
    elif edge > 5:
        confidence = "media-alta"
        risk = "medio"
        analysis = (
            f"Oportunidad sólida de valor en {home} vs {away}. "
            f"El {market_display} ({outcome}) a cuota {odds} ofrece un edge del {edge}% "
            f"sobre la probabilidad justa de Pinnacle. "
        )
    else:
        confidence = "media"
        risk = "medio-alto"
        analysis = (
            f"Valor moderado detectado en {home} vs {away}. "
            f"El {market_display} ({outcome}) tiene un edge del {edge}%. "
            f"Aunque positivo, el margen es ajustado — apostar con stake reducido. "
        )
    
    # Añadir insights de stats si disponibles
    if stats and stats.get("insights"):
        analysis += " " + " ".join(stats["insights"][:2])
    
    key_factors = [
        f"Edge de {edge}% en {market_display}",
        f"Cuota bet365: {odds} vs probabilidad justa de Pinnacle",
    ]
    
    if stats:
        home_stats = stats.get("home", {})
        away_stats = stats.get("away", {})
        if home_stats.get("form"):
            key_factors.append(f"Forma {home}: {home_stats['form']}")
        if away_stats.get("form"):
            key_factors.append(f"Forma {away}: {away_stats['form']}")
    
    return {
        "recommended_bet": {
            "market": market_display,
            "selection": outcome,
            "odds": odds,
            "edge": edge,
            "confidence": confidence
        },
        "analysis": analysis,
        "key_factors": key_factors,
        "risk_level": risk,
        "alternative_bet": {
            "market": "Over/Under Goles" if market != "totals" else "Resultado Final",
            "selection": "Over 2.5" if market != "totals" else "Draw",
            "reason": "Mercado alternativo con menor riesgo"
        }
    }


class AIAnalyzer:
    """Wrapper para Gemini API que genera análisis de apuestas en español."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.use_mock = not bool(self.api_key) or genai is None
        
        if not self.use_mock and genai:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            self.model = None
    
    def analyze_match(
        self,
        match_data: dict,
        value_data: dict,
        stats: dict = None,
        force_refresh: bool = False
    ) -> dict:
        """Genera un análisis completo de un partido.
        
        Args:
            match_data: Datos del partido (equipos, hora, etc.)
            value_data: Resultado del ValueCalculator (edge, mercados, etc.)
            stats: Estadísticas enriquecidas del StatsEnricher (opcional)
            force_refresh: Si True, ignora cache y regenera el análisis
        
        Returns:
            Dict con el análisis completo en formato estructurado.
        """
        match_id = match_data.get("id", "unknown")
        cache_key = f"analysis_{match_id}"
        
        if not force_refresh:
            cached = _analysis_cache.get(cache_key)
            if cached:
                return cached
        
        if self.use_mock:
            result = _generate_mock_analysis(match_data, value_data, stats)
        else:
            result = self._call_gemini(match_data, value_data, stats)
        
        _analysis_cache[cache_key] = result
        return result
    
    def _call_gemini(self, match_data: dict, value_data: dict, stats: dict = None) -> dict:
        """Llama a la API de Gemini para generar el análisis.
        
        Args:
            match_data: Datos del partido
            value_data: Datos de value calculados
            stats: Estadísticas opcionales
        
        Returns:
            Dict con el análisis parseado de la respuesta de Gemini.
        """
        try:
            # Construir el prompt con los datos del partido
            prompt = self._build_prompt(match_data, value_data, stats)
            
            response = self.model.generate_content(
                [SYSTEM_PROMPT, prompt],
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1000,
                    response_mime_type="application/json"
                )
            )
            
            # Parsear la respuesta JSON
            text = response.text.strip()
            # Limpiar posible markdown
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            
            result = json.loads(text)
            return result
            
        except json.JSONDecodeError as e:
            print(f"[AIAnalyzer] JSON parse error: {e}")
            return _generate_mock_analysis(match_data, value_data, stats)
        except Exception as e:
            print(f"[AIAnalyzer] Gemini API error: {e}")
            return _generate_mock_analysis(match_data, value_data, stats)
    
    def _build_prompt(self, match_data: dict, value_data: dict, stats: dict = None) -> str:
        """Construye el prompt para Gemini con todos los datos disponibles."""
        home = match_data.get("home_team", "Local")
        away = match_data.get("away_team", "Visitante")
        
        prompt = f"""PARTIDO: {home} vs {away}
FECHA: {match_data.get('commence_time', 'N/A')}
COMPETICIÓN: {match_data.get('sport_title', 'N/A')}

CUOTAS Y EDGE POR MERCADO:
"""
        # Añadir mercados
        markets = value_data.get("markets", {})
        for market_key, market_data in markets.items():
            prompt += f"\n{market_key.upper()}:\n"
            for outcome in market_data.get("outcomes", []):
                prompt += (
                    f"  - {outcome['name']}: "
                    f"bet365={outcome['bet365_odds']} | "
                    f"pinnacle={outcome['pinnacle_odds']} | "
                    f"edge={outcome['edge']}%\n"
                )
        
        # Mejor apuesta detectada
        best_bet = value_data.get("best_bet")
        if best_bet:
            prompt += f"\nMEJOR APUESTA DETECTADA: {best_bet['outcome']} ({best_bet['market']}) — Edge: {best_bet['edge']}%\n"
        
        # Stats si disponibles
        if stats:
            prompt += f"\nESTADÍSTICAS:\n"
            home_stats = stats.get("home", {})
            away_stats = stats.get("away", {})
            
            prompt += f"  {home}: Forma={home_stats.get('form', 'N/A')}, "
            prompt += f"Goles={home_stats.get('goals_scored_avg', 'N/A')}/partido, "
            prompt += f"Posesión={home_stats.get('possession_avg', 'N/A')}%\n"
            
            prompt += f"  {away}: Forma={away_stats.get('form', 'N/A')}, "
            prompt += f"Goles={away_stats.get('goals_scored_avg', 'N/A')}/partido, "
            prompt += f"Posesión={away_stats.get('possession_avg', 'N/A')}%\n"
            
            # H2H
            h2h = stats.get("h2h", {})
            if h2h.get("matches_total", 0) > 0:
                prompt += f"\n  H2H: {h2h['matches_total']} partidos — "
                prompt += f"{h2h.get('home_wins', 0)}W {h2h.get('draws', 0)}D {h2h.get('away_wins', 0)}L\n"
            
            # Insights
            insights = stats.get("insights", [])
            if insights:
                prompt += "\n  INSIGHTS:\n"
                for insight in insights:
                    prompt += f"    {insight}\n"
        
        prompt += "\nAnaliza y recomienda la mejor apuesta de valor. Responde en JSON."
        
        return prompt
    
    @property
    def is_mock(self) -> bool:
        """Indica si está usando análisis mock."""
        return self.use_mock
