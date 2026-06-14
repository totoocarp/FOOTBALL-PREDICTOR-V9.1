"""
Football Predictor V9.0 - Entry Point
"""

import uvicorn
import os
from pathlib import Path


def main():
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    for directory in [
        "database/cache",
        "database/predictions/full_model",
        "database/predictions/learning/xg",
        "database/predictions/learning/elo",
        "database/predictions/learning/form",
        "database/predictions/learning/market",
        "database/predictions/learning/ranking",
        "database/results",
        "database/statistics",
        "database/worldcup",
    ]:
        Path(directory).mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print("  FOOTBALL PREDICTOR V9.0")
    print(f"{'='*50}")
    print(f"\nServidor iniciado en:")
    print(f"  http://localhost:{port}")
    print(f"\nModo: {'DEBUG' if debug else 'PRODUCCIÓN'}")
    print(f"{'='*50}\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
