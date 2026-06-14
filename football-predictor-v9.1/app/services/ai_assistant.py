"""
Football Predictor V9.0 - AI Assistant
Optional: uses OpenAI or Anthropic for textual analysis of predictions.
Falls back gracefully if no AI key is configured.
"""

from typing import Optional
from loguru import logger
from app.config import settings


AI_UNAVAILABLE_MSG = (
    "Asistente IA no disponible. Para habilitarlo, agrega una clave de OpenAI "
    "(OPENAI_API_KEY) o Anthropic (ANTHROPIC_API_KEY) en tu archivo .env."
)


class AIAssistant:
    """
    Provides human-readable analysis of predictions using LLM.
    Completely optional — the predictor works 100% without AI.
    """

    def __init__(self):
        self._openai_client = None
        self._anthropic_client = None

    def _get_openai(self):
        if self._openai_client is None and settings.has_openai:
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            except ImportError:
                logger.warning("openai package not installed")
        return self._openai_client

    def _get_anthropic(self):
        if self._anthropic_client is None and settings.has_anthropic:
            try:
                import anthropic
                self._anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
        return self._anthropic_client

    def is_available(self) -> bool:
        return settings.has_ai

    async def analyze_prediction(
        self,
        home_team: str,
        away_team: str,
        competition: str,
        prediction: dict,
        team_stats: Optional[dict] = None,
    ) -> dict:
        """
        Generate AI analysis for a match prediction.
        Returns structured analysis with 9 sections.
        """
        if not self.is_available():
            return {"error": AI_UNAVAILABLE_MSG, "available": False}

        prompt = self._build_prompt(home_team, away_team, competition, prediction, team_stats)

        try:
            if settings.has_openai:
                return await self._query_openai(prompt)
            elif settings.has_anthropic:
                return await self._query_anthropic(prompt)
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {"error": f"Error en análisis IA: {str(e)}", "available": True}

        return {"error": "No AI provider configured", "available": False}

    def _build_prompt(
        self,
        home_team: str,
        away_team: str,
        competition: str,
        prediction: dict,
        team_stats: Optional[dict] = None,
    ) -> str:
        stats_info = ""
        if team_stats:
            stats_info = f"\nEstadísticas adicionales: {team_stats}"

        return f"""Eres un analista experto de fútbol. Analiza la siguiente predicción de partido:

PARTIDO: {home_team} vs {away_team}
COMPETICIÓN: {competition}

PREDICCIÓN DEL MODELO:
- Probabilidad victoria local: {prediction.get('home_win_prob', 0)*100:.1f}%
- Probabilidad empate: {prediction.get('draw_prob', 0)*100:.1f}%
- Probabilidad victoria visitante: {prediction.get('away_win_prob', 0)*100:.1f}%
- Goles esperados local: {prediction.get('home_goals_expected', 1.2):.2f}
- Goles esperados visitante: {prediction.get('away_goals_expected', 1.1):.2f}
- Marcador más probable: {prediction.get('most_likely_score', '1-1')}
- Probabilidad BTTS: {prediction.get('btts_prob', 0)*100:.1f}%
- Probabilidad Over 2.5: {prediction.get('over_25_prob', 0)*100:.1f}%
- Confianza del modelo: {prediction.get('confidence_score', 0)*100:.1f}%
{stats_info}

Responde en español con un análisis estructurado que incluya:
1. **Fiabilidad de la predicción** — ¿Cuán confiable es esta predicción?
2. **Coincidencia con mercado** — ¿Coincide con las cuotas habituales?
3. **Jugadores más probables para marcar** — Nombra perfiles ideales para este partido.
4. **Jugadores más probables para asistir** — Perfiles de asistidores.
5. **Posibles alineaciones** — Sistemas tácticos más probables para cada equipo.
6. **Lesiones importantes** — Menciona posibles bajas significativas basándote en el contexto.
7. **Ausencias clave** — Otros factores de disponibilidad.
8. **Factores ocultos** — Variables que el modelo estadístico no capta fácilmente.
9. **Explicación humana** — Resume la predicción en 2-3 frases para un lector no técnico.

Sé conciso, profesional y directo. Máximo 300 palabras."""

    async def _query_openai(self, prompt: str) -> dict:
        client = self._get_openai()
        if not client:
            return {"error": "OpenAI client not initialized", "available": False}

        response = await client.chat.completions.create(
            model=settings.ai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.7,
        )
        text = response.choices[0].message.content
        return {"analysis": text, "available": True, "provider": "openai", "model": settings.ai_model}

    async def _query_anthropic(self, prompt: str) -> dict:
        client = self._get_anthropic()
        if not client:
            return {"error": "Anthropic client not initialized", "available": False}

        import anthropic
        response = await client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return {"analysis": text, "available": True, "provider": "anthropic", "model": "claude-3-5-haiku"}

    async def analyze_worldcup(self, simulation_result: dict) -> dict:
        """Analyze World Cup simulation results."""
        if not self.is_available():
            return {"error": AI_UNAVAILABLE_MSG, "available": False}

        top_5 = list(simulation_result.get("champion_probs", {}).items())[:5]
        top_final = list(simulation_result.get("finalist_probs", {}).items())[:4]

        prompt = f"""Analiza en español los resultados de esta simulación del Mundial 2026 (20.000 simulaciones):

CAMPEONES MÁS PROBABLES:
{chr(10).join([f"- {team}: {prob}%" for team, prob in top_5])}

FINALISTAS MÁS PROBABLES:
{chr(10).join([f"- {team}: {prob}%" for team, prob in top_final])}

FINAL MÁS PROBABLE: {simulation_result.get('most_likely_final', 'TBD')}

Proporciona un análisis experto en 150-200 palabras explicando:
1. Por qué el favorito lo es
2. Sorpresas o equipos infravalorados
3. Bloques de equipos con más opciones
4. Factores que podrían cambiar el resultado real"""

        try:
            if settings.has_openai:
                return await self._query_openai(prompt)
            elif settings.has_anthropic:
                return await self._query_anthropic(prompt)
        except Exception as e:
            return {"error": str(e), "available": True}

        return {"error": "No AI provider", "available": False}


ai_assistant = AIAssistant()
