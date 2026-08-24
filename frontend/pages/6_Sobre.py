"""Página Sobre."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from components.ui import footer, inject_styles, page_header, section  # noqa: E402

inject_styles()
page_header("Sobre o Financial Prompt Lab", "Análise financeira assistida por Inteligência Artificial.")

st.markdown(
    "O Financial Prompt Lab é uma aplicação desenvolvida para apoiar uma pesquisa "
    "experimental sobre Engenharia de Prompt em modelos de linguagem e agentes de "
    "Inteligência Artificial."
)

section("Objetivo")
st.markdown(
    "Investigar como diferentes estratégias de prompt influenciam qualidade, "
    "robustez e eficiência de sistemas baseados em LLMs."
)

section("Técnicas avaliadas")
st.markdown("- Zero-shot\n- Few-shot\n- Raciocínio estruturado")

section("Domínio experimental")
st.markdown("Mercado financeiro brasileiro (ações, FIIs e índices de referência).")

section("Aviso")
st.info(
    "As informações apresentadas têm finalidade acadêmica e informativa e não "
    "constituem recomendação de investimento."
)

footer()
