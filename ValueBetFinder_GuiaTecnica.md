# VALUE BET FINDER

> **Guía Técnica del Proyecto**
> v1.0 · Junio 2026

Este documento es la guía de referencia técnica del sistema **Value Bet Finder**: una aplicación que detecta apuestas de valor comparando cuotas de bet365 contra la probabilidad "real" estimada con datos de Pinnacle y estadísticas externas. Cubre arquitectura, módulos, flujos de datos, APIs utilizadas y plan de implementación.

---

## 1. VISIÓN GENERAL DEL SISTEMA

Value Bet Finder es una herramienta **web + bot de Telegram** que detecta automáticamente apuestas de valor comparando las cuotas publicadas por bet365 con la probabilidad "real" del mercado, derivada de Pinnacle (la casa de apuestas sin margen de referencia) y complementada con estadísticas externas. El sistema corre **completamente gratis** en su primera versión: APIs gratuitas, hosting en Vercel y bot de Telegram.

### Objetivo del sistema

- Obtener las cuotas de bet365 para los partidos del Mundial 2026 (y futuras ligas).
- Calcular la probabilidad implícita de Pinnacle como benchmark "honesto" del mercado.
- Enriquecer el análisis con estadísticas: H2H, forma, corners, presión (CornerPro).
- Detectar apuestas donde bet365 paga más de lo que sugiere la probabilidad real → **VALUE BET**.
- Presentar la recomendación al usuario via interfaz web o alerta Telegram.

### Qué NO hace (alcance v1.0)

- No apuesta automáticamente — el humano siempre confirma.
- No cubre mercados de jugadores individuales (solo partidos).
- No tiene gestión de bankroll automática (solo recomendación de stake sugerido).

---

## 2. ARQUITECTURA DEL SISTEMA

El sistema se divide en **tres capas independientes**:

1. **Capa de Datos** (fuentes externas)
2. **Capa de Lógica / Backend** (cálculo de value y análisis)
3. **Capa de Presentación** (frontend web y bot Telegram)

Las capas se comunican vía llamadas HTTP; no hay base de datos en la versión MVP (los datos se calculan on-demand).

### Diagrama de flujo simplificado

```text
[Fuentes externas]                  [Backend /api/]                  [Presentación]
  - The Odds API     ──┐
  - Pinnacle (Odds)   ─┼─►  odds_fetcher.py  ──┐
  - API-Football WC   ─┼─►  world_cup_provider.py ─┐
  - CornerPro         ──┘                         │
                                                   ▼
                                          _merge_world_cup_with_odds()
                                                   │
                                                   ▼
                                          value_calculator.py
                                          stats_enricher.py
                                          ai_analyzer.py
                                                   │
                ┌──────────────────────────────────┼──────────────────────────────┐
                ▼                                  ▼                              ▼
        Frontend Web (HTML/JS)              Bot Telegram                  Logs / Métricas
```

### Stack tecnológico

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.11 |
| Backend / API | Vercel Serverless Functions (`/api/`) |
| Frontend | HTML + CSS + JS vanilla (mobile-first) |
| Bot | Telegram Bot API (polling) |
| Datos de cuotas | The Odds API (plan free) |
| Datos de stats | API-Football (plan free) + scraping CornerPro |
| AI | Gemini API (`gemini-sonnet-4-6`) |
| Hosting | Vercel (plan hobby/free) |
| Scraping | `requests` + `BeautifulSoup4` |

---

## 3. MÓDULOS DEL SISTEMA

### Módulo 0 — World Cup Provider (NUEVO)

**Responsabilidad:** ser la fuente oficial de partidos del Mundial 2026.

- **Inputs:** ninguno (consulta directa).
- **Outputs:** lista de partidos del Mundial con IDs oficiales, equipos, fechas, grupos, fases.
- **API utilizada:** API-Football v3 (`league=1`, `season=2026`).
- **Fallback:** fixture estático con los 72 partidos del Mundial 2026 (calendario oficial 11 jun – 19 jul).
- **Importante:** este módulo es la **autoridad** sobre qué partidos existen. OddsFetcher solo aporta cuotas para esos IDs.

### Módulo 1 — Odds Fetcher

**Responsabilidad:** obtener cuotas en tiempo real de The Odds API y normalizar los datos.

- **Inputs:** `sport_key`, mercados deseados, opcionalmente `match_ids` para filtrar.
- **Outputs:** lista de partidos con cuotas normalizadas por bookmaker y mercado.
- **Cache:** 5 minutos (las cuotas no cambian segundo a segundo antes del partido).
- **Fallback:** si Pinnacle no tiene cuota, usar Betfair Exchange como benchmark.
- **Fallback demo:** genera cuotas dinámicas realistas basadas en el rating relativo de los equipos (solo ~30% de partidos tienen value bet).

### Módulo 2 — Value Calculator

**Responsabilidad:** calcular el edge (ventaja) de cada apuesta comparando la probabilidad implícita de bet365 contra la de Pinnacle.

- **Umbral mínimo de value:** +3% (configurable). Por debajo, no se muestra como value bet.
- **Mercados calculados:** 1X2 (local/empate/visitante), Over/Under 2.5 goles, BTTS, Corners.
- El edge negativo indica que bet365 tiene margen a su favor → **no apostar**.

### Módulo 3 — Stats Enricher (CornerPro Scraper)

**Responsabilidad:** enriquecer el análisis con estadísticas del partido desde CornerPro. Como CornerPro no tiene API pública documentada, se usa scraping del HTML.

### Módulo 4 — AI Analyzer (gemini API)

**Responsabilidad:** recibir los datos crudos (cuotas + edge + stats) y producir un análisis en lenguaje natural con la recomendación final.

- **Modelo:** `gemini-sonnet-4-6` (rápido y económico para respuestas estructuradas).
- **Output:** JSON estricto con la mejor apuesta + justificación en español.
- **Costo estimado:** ~$0.001–0.003 por análisis de partido (muy bajo).

### Módulo 5 — API Backend (`/api/`)

**Responsabilidad:** orquestar los módulos anteriores y exponer endpoints HTTP.

### Módulo 6 — Frontend Web

**Responsabilidad:** mostrar los value bets del día en una interfaz limpia y usable desde móvil. Stack: HTML + CSS + JS vanilla (sin frameworks en v1.0) para máxima velocidad de desarrollo.

- **Página principal:** lista de partidos del día con badge de edge (verde si > 5%, amarillo 3–5%).
- **Card de partido:** cuotas bet365 vs Pinnacle, edge por mercado, mejor apuesta recomendada.
- **Análisis AI:** sección colapsable con el texto generado por gemini.
- **Botón "copiar apuesta":** copia el texto listo para pegar en bet365.
- **Responsive mobile-first:** la mayoría de uso será desde el celular antes/durante el partido.

### Módulo 7 — Bot Telegram

**Responsabilidad:** enviar alertas automáticas cuando aparece una value bet.

- **Frecuencia:** polling cada 15 minutos a `/api/value-bets` para detectar nuevas alertas.
- **Sin spam:** una alerta por partido máximo, aunque mejore el edge.
- **Comandos disponibles:** `/hoy`, `/partidos`, `/config_edge` (para ajustar el umbral).

---

## 4. FUENTES DE DATOS Y APIS

| Fuente | Tipo | Plan | Uso | Límite |
|---|---|---|---|---|
| The Odds API | Cuotas en vivo | Free | Cuotas de bet365, Pinnacle, Betfair | 500 req/mes |
| API-Football | Estadísticas | Free | H2H, forma, lesiones, lineups | 100 req/día |
| CornerPro | Stats avanzadas | Scraping | Presión, corners, tiros | Sin API oficial |
| gemini API | AI | Pay-as-you-go | Análisis en lenguaje natural | ~$0.001/análisis |

### Estrategia de rate limiting y caché

- **The Odds API:** cachear respuesta 5 min. Con 500 req/mes ≈ 16 req/día → 1 refresh cada 90 min si hay 3 partidos.
- **API-Football:** cachear 24h para stats pre-partido (no cambian). Solo refrescar para lineups (1h antes del partido).
- **CornerPro:** scraping solo al cargar el detalle de un partido. No polling automático.
- **gemini API:** cachear el análisis generado 30 min. No regenerar si los datos no cambiaron.

---

## 5. LÓGICA DE DETECCIÓN DE VALUE BETS

### Fórmula principal

```text
probabilidad_implícita = 1 / cuota
probabilidad_real = 1 / cuota_pinnacle        (Pinnacle como benchmark "justo")
edge = (probabilidad_real × cuota_bet365) - 1
```

- **Edge > 0** → bet365 paga más de lo que debería según Pinnacle → VALUE BET.
- **Edge ≤ 0** → bet365 paga igual o menos → no hay valor.

### Clasificación de confianza

| Edge | Clasificación | Acción |
|---|---|---|
| `> +8%` | 🟢 Excelente | Apuesta recomendada |
| `+5% a +8%` | 🟢 Buena | Apuesta recomendada |
| `+3% a +5%` | 🟡 Aceptable | Apuesta con stake bajo |
| `< +3%` | ⚪ Insuficiente | No mostrar |

---

## 6. ESTRUCTURA DE ARCHIVOS DEL PROYECTO

```text
betset/
├── api/
│   ├── matches.py           # GET /api/matches → partidos del día con cuotas
│   ├── value_bets.py        # GET /api/value-bets → solo los value bets
│   ├── match.py             # GET /api/match/{id} → detalle + análisis AI
│   └── analyze.py           # POST /api/analyze → fuerza un análisis nuevo
├── lib/
│   ├── odds_fetcher.py      # The Odds API wrapper
│   ├── value_calculator.py  # Fórmula de edge
│   ├── stats_enricher.py    # API-Football + CornerPro scraper
│   └── ai_analyzer.py       # gemini API wrapper
├── bot/
│   └── telegram_bot.py      # Bot con polling
├── web/
│   ├── index.html           # Lista de partidos
│   ├── match.html           # Detalle de partido
│   ├── styles.css
│   └── app.js
├── requirements.txt
├── vercel.json
└── README.md
```

### Variables de entorno requeridas

```bash
ODDS_API_KEY=            # The Odds API
FOOTBALL_API_KEY=        # API-Football
ANTHROPIC_API_KEY=       # gemini API
TELEGRAM_BOT_TOKEN=      # Bot de Telegram
TELEGRAM_CHAT_ID=        # Chat destino de las alertas
MIN_EDGE_THRESHOLD=3     # % mínimo de edge (default 3)
```

---

## 7. PLAN DE IMPLEMENTACIÓN

### Fase 1 — Esqueleto básico (Día 1–2)

- Registrarse en The Odds API y obtener key.
- Escribir `odds_fetcher.py` y testear con `curl` que devuelve cuotas del Mundial.
- Escribir `value_calculator.py` con la fórmula de edge.
- Endpoint `/api/matches` funcionando localmente.

### Fase 2 — Frontend mínimo (Día 3)

- HTML/CSS básico que llama `/api/matches` y muestra la lista de partidos.
- Badges de color según nivel de edge.
- Deploy en Vercel desde GitHub.

### Fase 3 — Análisis AI (Día 4)

- Integrar gemini API en `ai_analyzer.py`.
- Endpoint `/api/match/{id}` que devuelve el análisis completo.
- Sección de análisis colapsable en el frontend.

### Fase 4 — Stats enricher (Día 5–6)

- Scraper de CornerPro (`requests` + `BeautifulSoup`).
- Integrar stats en el payload que se envía a gemini.
- Fallback a API-Football si el scraper falla.

### Fase 5 — Bot Telegram (Día 7)

- Crear bot con `@BotFather`.
- Polling cada 15 min a `/api/value-bets`.
- Envío de alertas formateadas con emojis.
- Comando `/hoy` para pedir el resumen manual.

### Fase 6 — Pulido y prueba real (Día 8+)

- Probar con partidos reales del Mundial (los $5 de bet365).
- Ajustar umbrales de edge según resultados.
- Documentar qué apuestas ganaron/perdieron para calibrar el modelo.

---

## 8. RIESGOS Y LIMITACIONES

- **Pinnacle puede no tener cuota** para todos los partidos (especialmente ligas menores) → fallback a Betfair.
- **Scraping de CornerPro es frágil** ante cambios de HTML → requiere monitoreo y alertas si falla.
- **Cuotas cambian en milisegundos** en partido en vivo → la versión v1.0 es solo pre-partido.
- **El edge pasado no garantiza resultados futuros** → el sistema es una ayuda, no una garantía.
- **Límite de APIs gratuitas** puede agotarse si hay Mundial con muchos partidos simultáneos → considerar upgrade a plan pago.
- **No hay gestión de bankroll** → el usuario puede apostar de más; se recomienda stake fijo del 1–2% del bankroll.

---

## 9. GLOSARIO

| Término | Definición |
|---|---|
| **Value Bet** | Apuesta donde la cuota ofrecida es mayor que la probabilidad real del evento. |
| **Edge** | Ventaja porcentual del apostador sobre la casa de apuestas. `edge > 0` = value. |
| **Probabilidad implícita** | `1 / cuota` — la probabilidad que la casa "sugiere" con su cuota. |
| **Pinnacle** | Casa de apuestas de referencia por tener el margen más bajo del mercado (~2%). |
| **Bet365** | Casa destino: la que recibe las apuestas del usuario. |
| **BTTS** | Both Teams To Score — ambos equipos marcan. |
| **1X2** | Mercado de resultado final: local (1), empate (X), visitante (2). |
| **Over/Under 2.5** | Apuesta a si habrá más o menos de 2.5 goles en el partido. |
| **H2H** | Head-to-head: enfrentamientos directos históricos entre los dos equipos. |
| **CornerPro** | Sitio con estadísticas avanzadas de presión, tiros y corners. |
| **Stake** | Cantidad de dinero apostada. |

---

> *Value Bet Finder · Guía Técnica v1.0 · Junio 2026 · Documento generado con gemini*