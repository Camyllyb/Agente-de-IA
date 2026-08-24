"""Testar o agente financeiro pela linha de comando.

Exemplos:

    # 1) Demonstração OFFLINE, determinística (sem chave, sem internet):
    #    usa o oráculo + snapshots reais do repositório e mostra o agente
    #    escolhendo a ferramenta, obtendo os dados e respondendo.
    python try_agent.py --demo

    # 2) Uma pergunta com o provedor FAKE (offline; resposta canônica, sem tools):
    python try_agent.py --question "Explique o que é retorno percentual." --provider fake --model fake-model

    # 3) EXPERIMENTO A (LLM isolado, sem ferramentas):
    python try_agent.py --question "..." --provider fake --model fake-model --llm-only

    # 4) Com um LLM REAL (requer a chave no ambiente e a lib do provedor):
    #    export/set OPENAI_API_KEY=...   e   pip install langchain-openai
    python try_agent.py --question "Qual a variação da PETR4.SA entre 2024-01-02 e 2024-06-03?" \
        --provider openai --model <modelo-atual> --source snapshot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.agents import FinancialAgent, LLMOnlyAgent  # noqa: E402
from app.services.llm import create_llm_provider_from_params  # noqa: E402
from app.tools.market_data import SnapshotMarketDataProvider, get_market_data_provider  # noqa: E402


def _print(result) -> None:
    print(f"  Resposta      : {result.answer!r}")
    print(f"  Ferramentas   : {result.tools_used or 'nenhuma'}")
    print(f"  Tokens (t)    : {result.usage.total_tokens}  | latência: {result.latency_ms} ms")
    for call in result.tool_calls:
        print(f"    -> {call.name}({call.args}) => {call.output}")
    if result.error:
        print(f"  ERRO          : {result.error}")


def demo() -> None:
    """Prova o laço do agente com dados reais dos snapshots (determinístico)."""
    from experiments.datasets import load_questions
    from experiments.runner.oracle import build_oracle_provider

    market = SnapshotMarketDataProvider("default")
    questions = {q["id"]: q for q in load_questions()}
    for qid in ("Q001", "Q009", "Q013"):
        q = questions[qid]
        # O oráculo apenas ROTEIRIZA quais ferramentas chamar; os DADOS vêm do
        # snapshot real. O cálculo/decisão é feito pelas ferramentas, não inventado.
        agent = FinancialAgent(
            model=build_oracle_provider(q),
            prompt_strategy="chain_of_thought",
            market_data_provider=market,
        )
        print("=" * 70)
        print(f"{qid} [{q['category']}] — {q['question']}")
        _print(agent.run(q["question"]))


def run_one(args) -> None:
    if args.source == "live":
        market = get_market_data_provider("live")
    else:
        market = SnapshotMarketDataProvider(args.snapshot_set)

    provider = create_llm_provider_from_params(args.provider, args.model, temperature=args.temperature)

    if args.llm_only:
        print(f"[Experimento A · LLM isolado · {args.provider}/{args.model} · {args.strategy}]")
        agent = LLMOnlyAgent(model=provider, prompt_strategy=args.strategy)
    else:
        print(f"[Experimento B · Agente · {args.provider}/{args.model} · {args.strategy} · fonte={args.source}]")
        agent = FinancialAgent(model=provider, prompt_strategy=args.strategy, market_data_provider=market)

    _print(agent.run(args.question))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Testar o agente financeiro.")
    parser.add_argument("--demo", action="store_true", help="Demonstração offline determinística.")
    parser.add_argument("--question", default=None, help="Pergunta a enviar ao agente.")
    parser.add_argument("--provider", default="fake")
    parser.add_argument("--model", default="fake-model")
    parser.add_argument("--strategy", default="chain_of_thought",
                        choices=["zero_shot", "few_shot", "chain_of_thought"])
    parser.add_argument("--source", default="snapshot", choices=["snapshot", "live"])
    parser.add_argument("--snapshot-set", default="default")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--llm-only", action="store_true", help="Experimento A (sem ferramentas).")
    args = parser.parse_args(argv)

    if args.demo:
        demo()
        return 0
    if not args.question:
        parser.error("informe --question ou use --demo")
    run_one(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
