# Football Predictor V9.1

Predictor avanzado de fútbol profesional con simulación Monte Carlo, aprendizaje automático y predicción del Mundial 2026.

## Características

- **20.000 simulaciones Monte Carlo** por partido (distribución de Poisson)
- **Normalización global** (Z-score, percentiles) — sin explosiones de ratings
- **Motor de aprendizaje automático** — ajusta pesos por variable
- **Predictor Mundial 2026** — 48 equipos, 12 grupos, fase eliminatoria completa
- **Múltiples APIs gratuitas** con fallback automático
- **Asistente IA opcional** (OpenAI / Anthropic)
- **Actualizaciones automáticas** cada 10 minutos (APScheduler)

## Instalación

### 1. Clonar / descomprimir el proyecto

```bash
cd football-predictor-v9
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tu editor favorito y agrega tus claves API
```

### 5. Ejecutar

```bash
python run.py
```

Abre el navegador en: **http://localhost:8000**

---

## Variables de Entorno (`.env`)

| Variable | Descripción | Obligatorio |
|---|---|---|
| `FOOTBALL_DATA_API_KEY` | API Key de [football-data.org](https://www.football-data.org/) | Recomendado |
| `API_FOOTBALL_KEY` | API Key de [api-football.com](https://www.api-football.com/) | Recomendado |
| `ODDS_API_KEY` | API Key de [the-odds-api.com](https://the-odds-api.com/) | Opcional |
| `OPENAI_API_KEY` | API Key de OpenAI (análisis IA) | Opcional |
| `ANTHROPIC_API_KEY` | API Key de Anthropic (análisis IA) | Opcional |
| `DATABASE_URL` | URL de PostgreSQL para producción | Solo producción |
| `MONTE_CARLO_SIMULATIONS` | Número de simulaciones (default: 20000) | Opcional |
| `SCHEDULER_INTERVAL_MINUTES` | Intervalo actualización (default: 10) | Opcional |

> **Importante:** El archivo `.env` NUNCA se sube a GitHub. Está en `.gitignore`.
> El predictor funciona sin ninguna API key, usando solo estimaciones internas.

---

## Estructura del Proyecto

```
football-predictor-v9/
├── run.py                      # Punto de entrada
├── requirements.txt            # Dependencias Python
├── .env.example                # Plantilla de variables de entorno
├── .gitignore
├── README.md
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Configuración
│   ├── database.py             # SQLAlchemy setup
│   ├── models/                 # Modelos ORM
│   │   ├── team.py             # Equipos y estadísticas
│   │   ├── match.py            # Partidos y predicciones
│   │   ├── player.py           # Jugadores
│   │   ├── competition.py      # Competiciones
│   │   ├── learning.py         # Motor de aprendizaje
│   │   ├── worldcup.py         # Mundial 2026
│   │   └── logs.py             # Logs del sistema
│   ├── routers/
│   │   ├── main_routes.py      # Páginas HTML
│   │   └── api_routes.py       # API REST (JSON)
│   ├── services/
│   │   ├── monte_carlo.py      # Simulación Monte Carlo (core)
│   │   ├── elo.py              # Sistema ELO
│   │   ├── predictor.py        # Pipeline de predicción
│   │   ├── learning_engine.py  # Aprendizaje y ajuste de pesos
│   │   ├── worldcup_predictor.py  # Predictor Mundial 2026
│   │   ├── data_collector.py   # APIs y scraping
│   │   ├── ai_assistant.py     # Asistente IA (opcional)
│   │   ├── cache.py            # Cache en disco (24h)
│   │   └── scheduler.py        # APScheduler (cada 10 min)
│   ├── templates/              # Jinja2 HTML
│   └── static/                 # CSS + JS
└── database/
    ├── cache/                  # Cache API (auto-generado)
    ├── predictions/            # Predicciones guardadas
    ├── results/                # Resultados reales
    ├── statistics/             # Estadísticas del modelo
    └── worldcup/               # Simulaciones del Mundial
```

---

## APIs Gratuitas Soportadas

| API | Requiere Clave | Límite Gratis |
|---|---|---|
| [football-data.org](https://www.football-data.org/) | Sí (gratis) | 10 req/min |
| [api-football.com](https://www.api-football.com/) | Sí (gratis) | 100 req/día |
| [TheSportsDB](https://www.thesportsdb.com/) | No | Sin límite |
| [OpenLigaDB](https://www.openligadb.de/) | No | Sin límite |
| [The Odds API](https://the-odds-api.com/) | Sí (gratis) | 500 req/mes |

---

## Motor de Predicción

### Variables (20 por tipo de equipo)

**Clubs:** ELO global, ELO 12 meses, xG prom, xGA prom, diferencia xG, goles/partido, goles recibidos, puntos/partido, rendimiento local/visitante, forma 5, forma 10, valor plantilla, valor XI, lesiones, suspensiones, cuotas, posesión, tiros al arco, portería a cero, fatiga.

**Selecciones:** Ranking FIFA, ELO internacional, forma 5/10, goles, value convocados, jugadores Top5 ligas, jugadores UCL, experiencia internacional, Mundiales, eliminatorias, torneos continentales, lesiones, suspensiones, mercado, historial directo, localía.

### Normalización (Anti-explosión)
- Z-score global (μ=1500, σ=200 para ELO)
- Percentiles históricos
- Min-Max global
- Clamping lambda [0.1, 5.0]

---

## Producción (PostgreSQL)

```env
DATABASE_URL=postgresql+asyncpg://usuario:contraseña@host:5432/football_predictor
```

```bash
# Aplicar migraciones
alembic upgrade head
```

---

## Versión

**V9.0.0** — Junio 2026
