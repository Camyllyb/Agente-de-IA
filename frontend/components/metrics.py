"""Detalhes de execução (métricas) — exibidos de forma discreta."""

from __future__ import annotations

import streamlit as st

STRATEGY_LABELS = {
    "zero_shot": "Zero-shot",
    "few_shot": "Few-shot",
    "chain_of_thought": "Raciocínio estruturado",
}


def execution_details(response: dict) -> None:
    """Mostra as métricas dentro de um expander (não como informação principal).

    Nunca exibe API keys, prompts internos ou raciocínio privado do modelo.
    """
    metrics = response.get("metrics", {})
    tools = response.get("tools_used") or []
    with st.expander("Detalhes da execução"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Latência", f"{metrics.get('latency_ms', 0)} ms")
        c2.metric("Tokens (total)", metrics.get("total_tokens", 0))
        cost = metrics.get("estimated_cost")
        c3.metric("Custo estimado", "—" if cost in (None, "") else f"{cost}")

        st.caption(
            f"Modelo: **{response.get('provider','?')}/{response.get('model','?')}**  ·  "
            f"Estratégia: **{STRATEGY_LABELS.get(response.get('strategy',''), response.get('strategy',''))}**  ·  "
            f"Versão do prompt: **{response.get('prompt_version','?')}**"
        )
        st.caption(
            f"Tokens entrada/saída: **{metrics.get('input_tokens', 0)}** / "
            f"**{metrics.get('output_tokens', 0)}**  ·  "
            f"Ferramentas acionadas: **{', '.join(tools) if tools else 'nenhuma'}**  ·  "
            f"Fonte dos dados: **{response.get('data_source','?')}**"
        )
