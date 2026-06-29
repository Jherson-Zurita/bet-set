# 💎 Value Bet Finder

> Detecta apuestas de valor comparando cuotas de bet365 vs Pinnacle.
> Análisis AI en tiempo real para el Mundial 2026.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## ¿Qué es?

Value Bet Finder es una herramienta que detecta automáticamente **apuestas de valor** comparando las cuotas publicadas por bet365 con la probabilidad "real" del mercado, derivada de Pinnacle (la casa de apuestas sin margen de referencia) y complementada con estadísticas externas.

### Concepto

```
Edge = (probabilidad_real × cuota_bet365) - 1

Si Edge > 0 → bet365 paga más de lo que debería → VALUE BET 💎
```

## 🚀 Setup Rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/betset.git
cd betset
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus API keys
```

### 4. Probar localmente

El sistema funciona **sin API keys** usando datos mock:

```bash
# Servir el frontend localmente
cd web
python -m http.server 8000
# Abrir http://localhost:8000
```

### 5. Bot de Telegram

```bash
python bot/telegram_bot.py
```

## 📁 Estructura del Proyecto

```
betset/
├── api/                    # Vercel Serverless Functions
│   ├── matches.py          # GET /api/matches (WC + cuotas)
│   ├── value_bets.py       # GET /api/value-bets
│   ├── match.py            # GET /api/match?id=X
│   └── analyze.py          # POST /api/analyze
├── lib/                    # Módulos core
│   ├── world_cup_provider.py # Fixture oficial del Mundial (API-Football)
│   ├── odds_fetcher.py     # The Odds API wrapper + cuotas mock dinámicas
│   ├── value_calculator.py # Fórmula de edge + clasificación
│   ├── stats_enricher.py   # Stats de los 48 equipos del Mundial
│   └── ai_analyzer.py      # Gemini API wrapper
├── bot/
│   └── telegram_bot.py     # Bot con polling + alertas
├── web/                    # Frontend (HTML/CSS/JS vanilla)
│   ├── index.html          # Lista de partidos
│   ├── match.html          # Detalle de partido
│   ├── styles.css          # Design system premium
│   └── app.js              # Lógica frontend
├── test_modules.py         # Tests de los módulos core
├── test_hybrid.py          # Test del flujo híbrido (WC + cuotas)
├── requirements.txt
├── vercel.json
└── .env.example
```

### Arquitectura de datos

El sistema sigue un **flujo híbrido de datos** para garantizar precisión sobre el Mundial:

```
[WorldCupProvider]              [OddsFetcher]               [ValueCalculator]
  API-Football v3         +     The Odds API          →    Edge por mercado
  Fixture oficial WC 2026       Cuotas bet365/Pinnacle
  (con fallback estático)       (con fallback dinámico)
                 │                            │
                 └──────────► CRUCE ◄─────────┘
                              │
                              ▼
                      Partidos del Mundial
                      con edge calculado
```

## 🔑 APIs Requeridas

| API | Plan | Registro |
|---|---|---|
| [The Odds API](https://the-odds-api.com/) | Free (500 req/mes) | [Registrarse](https://the-odds-api.com/#get-access) |
| [API-Football](https://www.api-football.com/) | Free (100 req/día) | [Registrarse](https://dashboard.api-football.com/register) |
| [Gemini API](https://ai.google.dev/) | Pay-as-you-go | [Registrarse](https://makersuite.google.com/app/apikey) |
| Telegram Bot | Gratis | [BotFather](https://t.me/BotFather) |

## 📊 Clasificación de Edge

| Edge | Nivel | Acción |
|---|---|---|
| > +8% | 🟢 Excelente | Apuesta recomendada |
| +5% a +8% | 🟢 Buena | Apuesta recomendada |
| +3% a +5% | 🟡 Aceptable | Stake bajo |
| < +3% | ⚪ Insuficiente | No apostar |

## 🌐 Deploy en Vercel

1. Conectar tu repositorio GitHub con [Vercel](https://vercel.com)
2. Configurar las variables de entorno en el dashboard de Vercel
3. Deploy automático en cada push

## ⚠️ Disclaimer

Las apuestas deportivas conllevan riesgo financiero. Este sistema es una herramienta de análisis, **no una garantía de ganancias**. Apuesta solo lo que puedas permitirte perder. El edge pasado no garantiza resultados futuros.

---

*Value Bet Finder v1.0 · Mundial 2026*
