"""Financial Prompt Lab — interface conversacional (página principal).

Execute com:
    streamlit run frontend/streamlit_app.py

Requer o backend em execução (python main.py) para responder às perguntas.
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- path setup (robusto a partir do marcador pyproject.toml) ---------------
_HERE = Path(__file__).resolve()
_ROOT = next(p for p in _HERE.parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from app.config.models import load_models_config  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.services.llm import supported_providers  # noqa: E402
from lib import api_client  # noqa: E402
from lib.theme import (  # noqa: E402
    inject_theme,
    render_chips,
    render_footer,
    render_header,
)

STRATEGY_LABELS = {
    "zero_shot": "Zero-shot",
    "few_shot": "Few-shot",
    "chain_of_thought": "Chain-of-thought",
}


st.set_page_config(
    page_title="Financial Prompt Lab",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()


def _sidebar() -> dict:
    settings = get_settings()
    configs = load_models_config()

    with st.sidebar:
        st.markdown("### ⚙️ Configuração da execução")

        providers = list(supported_providers())
        default_idx = providers.index(settings.default_provider) if settings.default_provider in providers else 0
        provider = st.selectbox("Provider", providers, index=default_idx)

        suggestions = [c.model for c in configs if c.provider == provider]
        default_model = suggestions[0] if suggestions else ("fake-model" if provider == "fake" else "")
        model = st.text_input(
            "Modelo",
            value=default_model,
            help="Identificador do modelo no provedor (não há modelo obrigatório).",
        )

        strategy_key = st.selectbox(
            "Técnica de prompting",
            options=list(STRATEGY_LABELS.keys()),
            format_func=lambda k: STRATEGY_LABELS[k],
        )

        source_label = st.radio(
            "Fonte de dados",
            options=["Snapshot experimental", "Live"],
            help="Snapshot: dados congelados (reprodutível). Live: dados reais (yfinance).",
        )
        data_source = "snapshot" if source_label.startswith("Snapshot") else "live"

        snapshot_set = "default"
        if data_source == "snapshot":
            snapshot_set = st.text_input("Conjunto de snapshot", value=settings.snapshot_set)

        temperature = st.slider("Temperatura", 0.0, 2.0, float(settings.default_temperature), 0.1)

        st.divider()
        _render_backend_status()

    return {
        "provider": provider,
        "model": model,
        "strategy": strategy_key,
        "data_source": data_source,
        "snapshot_set": snapshot_set,
        "temperature": temperature,
    }


def _render_backend_status() -> None:
    result = api_client.health()
    if result.ok:
        st.caption("🟢 Backend conectado.")
    else:
        st.caption("🔴 Backend indisponível — inicie com `python main.py`.")


def _render_execution_meta(body: dict) -> None:
    metrics = body.get("metrics", {})
    tools = body.get("tools_used") or []
    render_chips(
        {
            "Modelo": f"{body.get('provider','?')}/{body.get('model','?')}",
            "Estratégia": STRATEGY_LABELS.get(body.get("strategy", ""), body.get("strategy", "")),
            "Tempo": f"{metrics.get('latency_ms', 0)} ms",
            "Tokens (in/out)": f"{metrics.get('input_tokens', 0)}/{metrics.get('output_tokens', 0)}",
            "Tokens total": str(metrics.get("total_tokens", 0)),
            "Ferramentas": ", ".join(tools) if tools else "nenhuma",
        }
    )


def main() -> None:
    render_header(
        title="Converse com o agente financeiro",
        subtitle="Laboratório experimental de Engenharia de Prompt aplicada a agentes financeiros.",
    )

    config = _sidebar()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Histórico
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("meta"):
                _render_execution_meta(message["meta"])

    prompt = st.chat_input("Faça uma pergunta financeira (ex.: variação da PETR4.SA entre duas datas)…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consultando o agente…"):
                payload = {"message": prompt, **config}
                result = api_client.post_chat(payload)
            if result.ok:
                answer = result.data.get("answer", "")
                st.markdown(answer)
                _render_execution_meta(result.data)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "meta": result.data}
                )
            else:
                st.error(result.error)
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"⚠️ {result.error}"}
                )

    render_footer()


main()
