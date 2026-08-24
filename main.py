"""Ponto de entrada da aplicação.

Uso:
    python main.py            # inicia a API (FastAPI/uvicorn) em 0.0.0.0:8000
    python main.py --help     # opções

A interface Streamlit é iniciada separadamente:
    streamlit run frontend/streamlit_app.py
"""

from __future__ import annotations

import argparse

from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="financial-prompt-agent API")
    parser.add_argument("--host", default="0.0.0.0", help="Host do servidor")
    parser.add_argument("--port", type=int, default=8000, help="Porta do servidor")
    parser.add_argument("--reload", action="store_true", help="Recarregar em alterações")
    args = parser.parse_args()

    # Import local: só carrega o uvicorn quando o servidor é realmente iniciado.
    import uvicorn

    print(f"Iniciando {settings.app_name} em http://{args.host}:{args.port}")
    uvicorn.run(
        "app.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
