"""Financial Prompt Lab — aplicação web (ponto de entrada).

Execute com:
    streamlit run frontend/streamlit_app.py

Requer o backend em execução (python main.py) para o Assistente responder.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from components.navigation import build_navigation  # noqa: E402
from components.ui import inject_styles, sidebar_brand  # noqa: E402

st.set_page_config(
    page_title="Financial Prompt Lab",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_styles()

with st.sidebar:
    sidebar_brand()

navigation = build_navigation()
navigation.run()
