"""
Telegram Bot — Alertas automáticas de Value Bets del Mundial 2026.

Envía notificaciones al usuario cuando aparece una apuesta de valor.
Polling cada 15 minutos a la API de value bets.

Comandos disponibles:
  /hoy       — Resumen de value bets del Mundial del día
  /partidos  — Lista de partidos del Mundial con cuotas
  /config_edge <n>  — Ajustar umbral mínimo de edge (default 3%)
  /help      — Mostrar ayuda

Uso:
  python bot/telegram_bot.py
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone

# Añadir directorio raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import requests as http_requests
except ImportError:
    http_requests = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from lib.odds_fetcher import OddsFetcher
from lib.value_calculator import ValueCalculator
from lib.world_cup_provider import WorldCupProvider

# Configuración
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Control de alertas enviadas (deduplicación)
_alerted_matches = set()

# Configuración runtime
_config = {
    "min_edge": float(os.environ.get("MIN_EDGE_THRESHOLD", 3)),
    "poll_interval": 900,  # 15 minutos en segundos
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("ValueBetBot")


# ============================================================
# TELEGRAM API HELPERS
# ============================================================

def send_message(chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
    """Envía un mensaje por Telegram.
    
    Args:
        chat_id: ID del chat destino
        text: Texto del mensaje (soporta Markdown)
        parse_mode: Formato del texto (Markdown o HTML)
    
    Returns:
        True si el mensaje se envió correctamente
    """
    if not TELEGRAM_BOT_TOKEN or http_requests is None:
        log.warning("Telegram not configured or requests not available")
        log.info(f"[DRY RUN] Message to {chat_id}:\n{text}")
        return False
    
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        response = http_requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            log.info(f"Message sent to {chat_id}")
            return True
        else:
            log.error(f"Telegram API error: {response.status_code} — {response.text}")
            return False
    except Exception as e:
        log.error(f"Failed to send message: {e}")
        return False


def get_updates(offset: int = 0) -> list:
    """Obtiene las actualizaciones (mensajes) pendientes del bot.
    
    Args:
        offset: ID del último update procesado + 1
    
    Returns:
        Lista de updates
    """
    if not TELEGRAM_BOT_TOKEN or http_requests is None:
        return []
    
    url = f"{TELEGRAM_API}/getUpdates"
    params = {"offset": offset, "timeout": 30}
    
    try:
        response = http_requests.get(url, params=params, timeout=35)
        if response.status_code == 200:
            data = response.json()
            return data.get("result", [])
        return []
    except Exception as e:
        log.error(f"Failed to get updates: {e}")
        return []


# ============================================================
# MESSAGE FORMATTING
# ============================================================

def format_value_bet_alert(match: dict) -> str:
    """Formatea un value bet como alerta de Telegram.
    
    Args:
        match: Dict con datos del partido analizado
    
    Returns:
        Texto formateado con Markdown para Telegram
    """
    best = match.get("best_bet", {})
    if not best:
        return ""
    
    market_names = {
        "h2h": "Resultado Final (1X2)",
        "totals": "Over/Under Goles",
        "btts": "Ambos Marcan"
    }
    
    edge = best.get("edge", 0)
    classification = best.get("classification", {})
    emoji = classification.get("emoji", "🟢")
    label = classification.get("label", "Value")
    
    lines = [
        f"🚨 *VALUE BET DETECTADA* {emoji}",
        "",
        f"⚽ *{match['home_team']} vs {match['away_team']}*",
        f"🏆 FIFA World Cup 2026",
        f"🕐 {_format_time_simple(match.get('commence_time', ''))}",
        "",
        f"📊 *Mercado:* {market_names.get(best.get('market', ''), best.get('market', ''))}",
        f"✅ *Selección:* {best.get('outcome', '')}",
        f"💰 *Cuota bet365:* {best.get('odds', 0):.2f}",
        f"📈 *Edge:* +{edge:.1f}% ({label})",
        f"💵 *Stake sugerido:* ${best.get('stake_suggested', 0):.2f}",
        "",
        f"_{_get_motivation(edge)}_",
    ]
    
    return "\n".join(lines)


def format_daily_summary(matches: list) -> str:
    """Formatea el resumen diario de value bets.
    
    Args:
        matches: Lista de partidos con value bets
    
    Returns:
        Texto formateado para Telegram
    """
    if not matches:
        return (
            "📋 *Resumen del Día*\n\n"
            "No se encontraron value bets por ahora.\n"
            "Las cuotas se actualizan cada 5 minutos — mantente atento! 👀"
        )
    
    lines = [
        f"📋 *Resumen de Value Bets — {datetime.now().strftime('%d/%m/%Y')}*",
        f"Se encontraron *{len(matches)}* apuestas de valor:\n"
    ]
    
    for i, match in enumerate(matches, 1):
        best = match.get("best_bet", {})
        if not best:
            continue
        
        edge = best.get("edge", 0)
        emoji = best.get("classification", {}).get("emoji", "🟢")
        
        lines.append(
            f"{i}. {emoji} *{match['home_team']} vs {match['away_team']}*\n"
            f"   {best.get('outcome', '')} @ {best.get('odds', 0):.2f} — "
            f"Edge: +{edge:.1f}%"
        )
    
    lines.append("\nUsa /hoy para ver el detalle actualizado.")
    
    return "\n".join(lines)


def format_all_matches(matches: list) -> str:
    """Formatea la lista completa de partidos.
    
    Args:
        matches: Lista de todos los partidos analizados
    
    Returns:
        Texto formateado para Telegram
    """
    if not matches:
        return "⚽ No hay partidos disponibles en este momento."
    
    lines = [
        f"⚽ *Partidos del Día* ({len(matches)} partidos)\n"
    ]
    
    for match in matches:
        best = match.get("best_bet", {})
        has_value = match.get("has_value", False)
        
        if has_value and best:
            emoji = best.get("classification", {}).get("emoji", "⚪")
            edge_str = f"+{best['edge']:.1f}%"
        else:
            emoji = "⚪"
            edge_str = "Sin valor"
        
        time_str = _format_time_simple(match.get("commence_time", ""))
        lines.append(
            f"{emoji} *{match['home_team']}* vs *{match['away_team']}*\n"
            f"   🕐 {time_str} — {edge_str}"
        )
    
    return "\n".join(lines)


def _format_time_simple(iso_string: str) -> str:
    """Formatea una fecha ISO a hora legible."""
    if not iso_string:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return "—"


def _get_motivation(edge: float) -> str:
    """Genera un texto motivacional según el edge."""
    if edge > 8:
        return "🔥 Oportunidad excepcional — no dejes pasar esta!"
    elif edge > 5:
        return "💪 Buena oportunidad de valor — apuesta con confianza."
    else:
        return "👍 Valor moderado — considera un stake conservador."


# ============================================================
# COMMAND HANDLERS
# ============================================================

def handle_command(chat_id: str, command: str, args: str = ""):
    """Procesa un comando recibido del usuario.
    
    Args:
        chat_id: ID del chat
        command: Comando (sin /)
        args: Argumentos adicionales
    """
    command = command.lower().strip()
    
    if command == "start" or command == "help":
        send_message(chat_id, (
            "💎 *Value Bet Finder Bot*\n\n"
            "Detecto apuestas de valor comparando cuotas de bet365 "
            "contra Pinnacle.\n\n"
            "*Comandos disponibles:*\n"
            "/hoy — Value bets del día\n"
            "/partidos — Todos los partidos con cuotas\n"
            "/config\\_edge N — Cambiar umbral de edge (actual: "
            f"{_config['min_edge']}%)\n"
            "/help — Esta ayuda\n\n"
            "⚠️ Las apuestas conllevan riesgo. Apuesta responsablemente."
        ))
    
    elif command == "hoy":
        log.info(f"Command /hoy from {chat_id}")
        wc_provider = WorldCupProvider()
        fetcher = OddsFetcher()
        calculator = ValueCalculator(min_edge=_config["min_edge"])

        # Solo partidos oficiales del Mundial (no inventados)
        wc_matches = wc_provider.get_fixture(only_upcoming=True, window_days=7)
        odds_matches = fetcher.get_matches()
        wc_with_odds = _merge_with_odds(wc_matches, odds_matches)

        value_bets = calculator.get_value_bets_only(wc_with_odds)
        send_message(chat_id, format_daily_summary(value_bets))

    elif command == "partidos":
        log.info(f"Command /partidos from {chat_id}")
        wc_provider = WorldCupProvider()
        fetcher = OddsFetcher()
        calculator = ValueCalculator()

        wc_matches = wc_provider.get_fixture(only_upcoming=True, window_days=7)
        odds_matches = fetcher.get_matches()
        wc_with_odds = _merge_with_odds(wc_matches, odds_matches)
        analyzed = calculator.analyze_matches(wc_with_odds)
        send_message(chat_id, format_all_matches(analyzed))
    
    elif command == "config_edge":
        try:
            new_edge = float(args.strip())
            if 0 < new_edge <= 20:
                _config["min_edge"] = new_edge
                send_message(chat_id, (
                    f"✅ Umbral de edge actualizado a *{new_edge}%*\n"
                    "Solo recibirás alertas con edge mayor a este valor."
                ))
                log.info(f"Edge threshold updated to {new_edge}% by {chat_id}")
            else:
                send_message(chat_id, "⚠️ El valor debe estar entre 0 y 20.")
        except ValueError:
            send_message(chat_id, (
                f"📊 Umbral actual: *{_config['min_edge']}%*\n\n"
                "Uso: `/config_edge 5` para cambiar a 5%"
            ))
    
    else:
        send_message(chat_id, (
            "❓ Comando no reconocido.\n"
            "Escribe /help para ver los comandos disponibles."
        ))


# ============================================================
# POLLING LOOP
# ============================================================

def _merge_with_odds(wc_matches: list[dict], odds_matches: list[dict]) -> list[dict]:
    """Cruza partidos del Mundial con cuotas (mismo algoritmo que api/matches.py)."""
    odds_by_teams = {}
    for om in odds_matches:
        key = (om["home_team"].lower().strip(), om["away_team"].lower().strip())
        odds_by_teams[key] = om

    merged = []
    for wc in wc_matches:
        home = wc["home_team"]
        away = wc["away_team"]
        key = (home.lower().strip(), away.lower().strip())

        odds_match = odds_by_teams.get(key)
        if not odds_match:
            for (h, a), om in odds_by_teams.items():
                if (h in home.lower() or home.lower() in h) and (a in away.lower() or away.lower() in a):
                    odds_match = om
                    break

        if odds_match:
            merged.append({
                **wc,
                "sport_title": "FIFA World Cup 2026",
                "bookmakers": odds_match.get("bookmakers", {}),
            })
        else:
            merged.append({
                **wc,
                "sport_title": "FIFA World Cup 2026",
                "bookmakers": {},
                "odds_pending": True,
            })

    return merged


def check_for_new_value_bets():
    """Verifica si hay nuevos value bets del Mundial 2026 y envía alertas.

    Compara con los partidos ya alertados para evitar duplicados.
    """
    if not TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID not set, skipping alert check")
        return

    log.info("Checking for new value bets (World Cup 2026)...")

    try:
        wc_provider = WorldCupProvider()
        fetcher = OddsFetcher()
        calculator = ValueCalculator(min_edge=_config["min_edge"])

        wc_matches = wc_provider.get_fixture(only_upcoming=True, window_days=7)
        odds_matches = fetcher.get_matches()
        wc_with_odds = _merge_with_odds(wc_matches, odds_matches)
        value_bets = calculator.get_value_bets_only(wc_with_odds)

        new_alerts = 0
        for match in value_bets:
            match_id = match.get("match_id", "")

            if match_id not in _alerted_matches:
                alert_text = format_value_bet_alert(match)
                if alert_text:
                    success = send_message(TELEGRAM_CHAT_ID, alert_text)
                    if success:
                        _alerted_matches.add(match_id)
                        new_alerts += 1
                        # Pausa entre mensajes para evitar rate limit
                        time.sleep(1)

        if new_alerts > 0:
            log.info(f"Sent {new_alerts} new value bet alerts")
        else:
            log.info(f"No new value bets (total tracked: {len(_alerted_matches)})")

    except Exception as e:
        log.error(f"Error checking for value bets: {e}")


def process_updates(offset: int = 0) -> int:
    """Procesa mensajes pendientes del bot.
    
    Args:
        offset: ID del último update procesado
    
    Returns:
        Nuevo offset para la siguiente llamada
    """
    updates = get_updates(offset)
    
    for update in updates:
        offset = update.get("update_id", 0) + 1
        
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()
        
        if not chat_id or not text:
            continue
        
        if text.startswith("/"):
            parts = text[1:].split(maxsplit=1)
            command = parts[0].split("@")[0]  # Remove @botname
            args = parts[1] if len(parts) > 1 else ""
            handle_command(chat_id, command, args)
    
    return offset


def run_bot():
    """Loop principal del bot.
    
    Combina:
    1. Polling de mensajes del usuario (comandos)
    2. Verificación periódica de nuevos value bets
    """
    log.info("=" * 50)
    log.info("Value Bet Finder — Telegram Bot")
    log.info("=" * 50)
    
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN not set!")
        log.info("Set the environment variable and restart.")
        log.info("Running in DRY RUN mode (logs only)...")
    
    offset = 0
    last_check = 0
    poll_interval = _config["poll_interval"]
    
    log.info(f"Poll interval: {poll_interval}s | Min edge: {_config['min_edge']}%")
    log.info("Bot started. Waiting for commands...")
    
    while True:
        try:
            # 1. Procesar comandos del usuario
            offset = process_updates(offset)
            
            # 2. Verificar value bets periódicamente
            now = time.time()
            if now - last_check >= poll_interval:
                check_for_new_value_bets()
                last_check = now
            
            # Pausa entre iteraciones
            time.sleep(2)
            
        except KeyboardInterrupt:
            log.info("Bot stopped by user")
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            time.sleep(10)  # Esperar antes de reintentar


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_bot()
