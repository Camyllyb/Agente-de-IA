"""Bootstrap comum das páginas Streamlit.

Garante que a raiz do projeto esteja no ``sys.path`` para importar ``app`` e
``experiments`` ao executar ``streamlit run frontend/streamlit_app.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def api_base_url() -> str:
    """URL base do backend FastAPI."""
    return os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
