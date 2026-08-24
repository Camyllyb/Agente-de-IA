"""Componentes do chat: sugestões e renderização da resposta do agente."""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from components.metrics import execution_details

SUGGESTIONS = [
    "Qual é a cotação da PETR4.SA?",
    "Compare PETR4.SA e VALE3.SA.",
    "Qual foi o retorno da PETR4.SA entre 2024-01-02 e 2024-06-03?",
    "Qual ativo teve a maior cotação: PETR4.SA, VALE3.SA ou ITUB4.SA?",
    "Qual é a cotação da AAPL?",
    "Explique o comportamento da PETR4.SA no período.",
]


def render_suggestions() -> None:
    """Botões de sugestão; ao clicar, preenche a pergunta pendente."""
    st.caption("Comece com uma pergunta:")
    cols = st.columns(2)
    for i, suggestion in enumerate(SUGGESTIONS):
        if cols[i % 2].button(suggestion, key=f"sugg_{i}", use_container_width=True):
            st.session_state["pending_question"] = suggestion
            st.rerun()


def parse_sections(answer: str) -> dict:
    """Separa 'Resposta final', 'Justificativa' e 'Dados utilizados' do texto."""
    if not answer:
        return {"resposta": "", "analise": "", "dados": ""}
    labels = {
        "resposta": r"resposta final",
        "analise": r"justificativa",
        "dados": r"dados utilizados",
    }
    positions = []
    for key, pat in labels.items():
        m = re.search(pat, answer, re.IGNORECASE)
        if m:
            positions.append((m.start(), m.end(), key))
    positions.sort()
    if not positions:
        return {"resposta": answer.strip(), "analise": "", "dados": ""}
    result = {"resposta": "", "analise": "", "dados": ""}
    for idx, (_s, e, key) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(answer)
        result[key] = answer[e:end].lstrip(" :\n").strip()
    return result


def render_agent_response(response: dict) -> None:
    """Renderiza a resposta do agente em seções visuais."""
    sections = parse_sections(response.get("answer", ""))

    st.markdown(
        f'<div class="fpl-answer"><h4>Resposta</h4>{sections["resposta"] or "—"}</div>',
        unsafe_allow_html=True,
    )
    if sections["analise"]:
        st.markdown(
            f'<div class="fpl-answer"><h4>Análise</h4>{sections["analise"]}</div>',
            unsafe_allow_html=True,
        )

    data_used = response.get("data_used") or []
    if data_used:
        st.markdown('<div class="fpl-answer"><h4>Dados utilizados</h4></div>', unsafe_allow_html=True)
        df = pd.DataFrame(data_used).rename(columns={
            "ativo": "Ativo", "valor": "Valor", "data": "Data", "moeda": "Moeda", "fonte": "Fonte",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    elif sections["dados"]:
        st.markdown(
            f'<div class="fpl-answer"><h4>Dados utilizados</h4>{sections["dados"]}</div>',
            unsafe_allow_html=True,
        )

    execution_details(response)
