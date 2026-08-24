"""Página Histórico — consultas realizadas na sessão."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from components import chat as chat_ui  # noqa: E402
from components.ui import empty_state, footer, inject_styles, page_header  # noqa: E402

inject_styles()
page_header("Histórico", "Consultas realizadas nesta sessão.")

history = st.session_state.get("history", [])

if not history:
    empty_state("Nenhuma consulta ainda",
                "Use o Assistente para fazer perguntas — elas aparecerão aqui.")
    footer()
    st.stop()

col1, col2 = st.columns([3, 1])
col1.caption(f"{len(history)} consulta(s) nesta sessão.")
if col2.button("Limpar histórico", use_container_width=True):
    st.session_state["history"] = []
    st.rerun()

for i, item in enumerate(history):
    with st.container(border=True):
        st.markdown(f"**{item['time']}** · {item['asset']}")
        st.markdown(item["question"])
        st.caption(item["summary"])
        if item.get("response"):
            with st.expander("Abrir consulta"):
                chat_ui.render_agent_response(item["response"])

footer()
