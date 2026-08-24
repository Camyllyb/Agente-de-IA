"""Navegação lateral da aplicação (st.navigation)."""

from __future__ import annotations

import streamlit as st


def build_navigation():
    """Constrói a navegação com as 6 áreas (Assistente é a padrão)."""
    pages = [
        st.Page("pages/1_Assistente.py", title="Assistente", icon=":material/forum:", default=True),
        st.Page("pages/2_Mercado.py", title="Mercado", icon=":material/trending_up:"),
        st.Page("pages/3_Comparar_Ativos.py", title="Comparar Ativos", icon=":material/compare_arrows:"),
        st.Page("pages/4_Historico.py", title="Histórico", icon=":material/history:"),
        st.Page("pages/5_Laboratorio.py", title="Laboratório Experimental", icon=":material/science:"),
        st.Page("pages/6_Sobre.py", title="Sobre", icon=":material/info:"),
    ]
    return st.navigation(pages, position="sidebar")
