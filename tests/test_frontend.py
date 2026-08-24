"""Verificação de runtime da interface Streamlit via AppTest.

Executa de fato os scripts das páginas (sem navegador) e verifica que rodam sem
exceções. Não dependem de backend nem de banco populado (degradam graciosamente).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_chat_page_runs_without_exception() -> None:
    app = AppTest.from_file(str(ROOT / "frontend" / "streamlit_app.py"), default_timeout=60)
    app.run()
    assert not app.exception


def test_experiments_page_runs_without_exception() -> None:
    app = AppTest.from_file(str(ROOT / "frontend" / "pages" / "1_Experimentos.py"), default_timeout=60)
    app.run()
    assert not app.exception
