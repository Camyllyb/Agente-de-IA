"""Estilo visual (CSS) e componentes de layout da interface."""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
:root {
  --fpl-primary: #4F46E5;
  --fpl-primary-dark: #3730A3;
  --fpl-ink: #1E2230;
  --fpl-muted: #6B7280;
  --fpl-surface: #F4F5FA;
  --fpl-border: #E6E8F0;
}

/* Container principal um pouco mais estreito e arejado */
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1200px; }

/* Cabeçalho (hero) */
.fpl-hero {
  background: linear-gradient(120deg, var(--fpl-primary-dark) 0%, var(--fpl-primary) 55%, #6366F1 100%);
  border-radius: 18px;
  padding: 26px 30px;
  color: #FFFFFF;
  box-shadow: 0 10px 30px rgba(79,70,229,0.18);
  margin-bottom: 1.4rem;
}
.fpl-hero-eyebrow {
  text-transform: uppercase;
  letter-spacing: .16em;
  font-size: .72rem;
  font-weight: 600;
  opacity: .85;
  margin-bottom: .35rem;
}
.fpl-hero-title { font-size: 2.05rem; font-weight: 750; line-height: 1.1; margin: 0; }
.fpl-hero-sub { font-size: 1.02rem; opacity: .92; margin-top: .5rem; max-width: 720px; }

/* Chips de metadados de execução */
.fpl-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: .3rem 0 .2rem; }
.fpl-chip {
  background: var(--fpl-surface);
  border: 1px solid var(--fpl-border);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: .8rem;
  color: var(--fpl-ink);
}
.fpl-chip b { color: var(--fpl-primary-dark); font-weight: 650; }

/* Cartão genérico */
.fpl-card {
  background: #FFFFFF;
  border: 1px solid var(--fpl-border);
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 2px 10px rgba(30,34,48,0.04);
}

/* Rodapé sutil */
.fpl-footer { color: var(--fpl-muted); font-size: .8rem; margin-top: 2rem; text-align: center; }

/* Badge de fatos vs. interpretação */
.fpl-note { color: var(--fpl-muted); font-size: .82rem; }

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
"""


def inject_theme() -> None:
    """Injeta o CSS global (chame uma vez por página, após set_page_config)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def render_header(title: str, subtitle: str, eyebrow: str = "Financial Prompt Lab") -> None:
    """Renderiza o cabeçalho (hero) da página."""
    st.markdown(
        f"""
        <div class="fpl-hero">
          <div class="fpl-hero-eyebrow">{eyebrow}</div>
          <div class="fpl-hero-title">{title}</div>
          <div class="fpl-hero-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chips(items: dict[str, str]) -> None:
    """Renderiza chips discretos de metadados (rótulo → valor)."""
    chips = "".join(
        f'<span class="fpl-chip">{label} <b>{value}</b></span>'
        for label, value in items.items()
    )
    st.markdown(f'<div class="fpl-chips">{chips}</div>', unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown(
        '<div class="fpl-footer">Financial Prompt Lab · pesquisa em Engenharia de '
        "Prompt · as respostas não constituem recomendação de investimento.</div>",
        unsafe_allow_html=True,
    )
