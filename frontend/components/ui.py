"""Elementos visuais compartilhados (estilo, cabeçalho, estados)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).resolve().parents[1] / "styles" / "app.css"


def inject_styles() -> None:
    """Injeta a folha de estilo global (chame uma vez por página)."""
    try:
        css = _CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        css = ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def sidebar_brand() -> None:
    # translate="no" evita que o tradutor do navegador altere o nome do produto.
    st.markdown(
        '<div class="fpl-brand" translate="no">Financial Prompt Lab</div>'
        '<div class="fpl-brand-sub">Análise financeira assistida por IA</div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="fpl-hero"><div class="fpl-hero-title" translate="no">{title}</div>'
        f'<div class="fpl-hero-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<div class="fpl-section">{title}</div>', unsafe_allow_html=True)


def status_badge(ok: bool, ok_text: str = "Sistema disponível",
                 down_text: str = "Serviço indisponível") -> None:
    if ok:
        st.markdown(f'<span class="fpl-badge ok">🟢 {ok_text}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="fpl-badge down">🔴 {down_text}</span>', unsafe_allow_html=True)


def chips(items: dict[str, str]) -> None:
    html = "".join(f'<span class="fpl-chip">{k} <b>{v}</b></span>' for k, v in items.items())
    st.markdown(f'<div class="fpl-chips">{html}</div>', unsafe_allow_html=True)


def empty_state(title: str, text: str = "") -> None:
    st.markdown(
        f'<div class="fpl-empty"><div class="fpl-empty-title">{title}</div>{text}</div>',
        unsafe_allow_html=True,
    )


def error_box(detail: str | None = None) -> None:
    st.error("Não foi possível concluir a consulta.")
    if detail:
        st.caption(detail)


def footer() -> None:
    st.markdown(
        '<div class="fpl-footer">Financial Prompt Lab · pesquisa em Engenharia de Prompt · '
        "as informações têm finalidade acadêmica e não constituem recomendação de investimento.</div>",
        unsafe_allow_html=True,
    )
