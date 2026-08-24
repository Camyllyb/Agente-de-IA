"""Página Assistente — chat com o agente financeiro (tela principal)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from components import chat as chat_ui  # noqa: E402
from components.metrics import STRATEGY_LABELS  # noqa: E402
from components.ui import footer, inject_styles, page_header, status_badge  # noqa: E402
from services import api_client  # noqa: E402

inject_styles()

# --- Cabeçalho + status ------------------------------------------------------
page_header("Financial Prompt Lab", "Seu assistente para análise de dados do mercado financeiro.")
health = api_client.health()
status_badge(health.ok)

# --- Sidebar: configurações --------------------------------------------------
STRATEGY_BY_LABEL = {v: k for k, v in STRATEGY_LABELS.items()}


def _sidebar() -> dict:
    with st.sidebar:
        st.markdown("### Configurações")

        models_res = api_client.get_models()
        options = []
        if models_res.ok:
            for m in models_res.data.get("models", []):
                options.append((m["provider"], m["model"], m.get("available", True)))
        if not options:
            options = [("fake", "fake-model", True)]

        providers = sorted({p for p, _, _ in options})
        provider = st.selectbox("Provider", providers, format_func=str.capitalize)
        models_for_provider = [(m, av) for p, m, av in options if p == provider]
        model = st.selectbox("Modelo", [m for m, _ in models_for_provider])
        available = dict(models_for_provider).get(model, True)
        if not available:
            st.info("Este modelo requer uma chave de API configurada no servidor.")

        source_label = st.radio("Fonte dos dados", ["Base histórica", "Mercado atual"],
                                help="Base histórica: snapshots reproduzíveis. Mercado atual: dados ao vivo.")
        data_source = "snapshot" if source_label == "Base histórica" else "live"

        st.divider()
        researcher = st.toggle("Modo pesquisador", value=False,
                               help="Exibe a escolha da estratégia de prompting.")
        strategy = "chain_of_thought"
        if researcher:
            label = st.radio("Estratégia de prompting",
                             ["Zero-shot", "Few-shot", "Raciocínio estruturado"], index=2)
            strategy = STRATEGY_BY_LABEL.get(label, "chain_of_thought")

    return {"provider": provider, "model": model, "data_source": data_source, "strategy": strategy}


config = _sidebar()

# --- Estado do chat ----------------------------------------------------------
st.session_state.setdefault("messages", [])
st.session_state.setdefault("history", [])

for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and message.get("response"):
            chat_ui.render_agent_response(message["response"])
        else:
            st.markdown(message["content"])

# Sugestões quando não há conversa.
if not st.session_state["messages"]:
    chat_ui.render_suggestions()

# Pergunta: preferir a sugestão clicada; senão, o campo de entrada.
typed = st.chat_input("Pergunte sobre um ativo, cotação, retorno ou comparação…")
prompt = st.session_state.pop("pending_question", None) or typed

if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando o agente…"):
            payload = {"message": prompt, **config}
            result = api_client.post_chat(payload)
        if result.ok:
            chat_ui.render_agent_response(result.data)
            st.session_state["messages"].append(
                {"role": "assistant", "content": result.data.get("answer", ""), "response": result.data}
            )
            sections = chat_ui.parse_sections(result.data.get("answer", ""))
            st.session_state["history"].insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "question": prompt,
                "asset": ", ".join(d.get("ativo", "") for d in result.data.get("data_used", []) if d.get("ativo")) or "—",
                "summary": sections["resposta"][:160] or "—",
                "response": result.data,
            })
        else:
            st.error("Não foi possível concluir a consulta.")
            st.caption(result.error or "")
            st.session_state["messages"].append(
                {"role": "assistant", "content": f"⚠️ {result.error}"}
            )

footer()
