"""Verificação de pré-voo antes de um experimento real.

Executa os passos exigidos ANTES de qualquer chamada externa:
  1. verifica quais provedores têm API key configurada;
  2. (se houver) testa uma única chamada por modelo real;
  3. valida o dataset;
  4. valida os snapshots financeiros;
  5. valida as respostas de referência (recomputa a partir dos snapshots);
  6. calcula o total previsto de chamadas;
  7. estima o custo, se a tabela de preços estiver configurada.

Se não for possível realizar chamadas externas (nenhum provedor real
configurado), o experimento real deve ser interrompido — este módulo informa o
motivo. Nada é inventado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config.models import load_models_config
from app.config.settings import get_settings
from app.metrics import load_price_table, score_answer
from app.models.llm import LLMConfig
from app.tools.financial_tools import FinancialToolset
from app.tools.market_data import SnapshotMarketDataProvider
from experiments.datasets import load_questions


@dataclass
class PreflightReport:
    configured_real_providers: list[str]
    real_models: list[str]
    n_questions: int
    categories: dict[str, int]
    dataset_ok: bool
    missing_symbols: list[str]
    reference_mismatches: list[str]
    strategies: list[str]
    repetitions: int
    planned_calls_real: int
    price_table_configured: bool
    model_call_tests: dict[str, str] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    @property
    def can_run_real(self) -> bool:
        return bool(self.real_models)

    @property
    def snapshots_ok(self) -> bool:
        return not self.missing_symbols

    @property
    def references_ok(self) -> bool:
        return not self.reference_mismatches


def _validate_references(questions, toolset: FinancialToolset) -> tuple[list[str], list[str]]:
    """Recomputa referências a partir dos snapshots e confere consistência."""
    missing_symbols: list[str] = []
    mismatches: list[str] = []
    available = set(toolset.provider.available_symbols())

    for q in questions:
        params = q.get("params", {})
        symbols = params.get("symbols") or ([params["symbol"]] if params.get("symbol") else [])
        for sym in symbols:
            if sym not in available:
                missing_symbols.append(f"{q['id']}:{sym}")

        expected = q.get("expected_answer", {})
        etype = expected.get("type")
        if etype == "numeric" and q["category"] == "return_calculation":
            r = toolset.calculate_return(params["symbol"], params["start_date"], params["end_date"])
            if r.get("found"):
                score = score_answer(expected, f"Resposta final: {r['return_pct']}%")
                if not score.correct:
                    mismatches.append(f"{q['id']} (retorno {r['return_pct']} vs {expected['value']})")
        elif etype == "numeric" and q["category"] == "factual_quote":
            r = toolset.get_stock_quote(params["symbol"])
            if r.get("found"):
                score = score_answer(expected, f"Resposta final: {r['price']}")
                if not score.correct:
                    mismatches.append(f"{q['id']} (preço {r['price']} vs {expected['value']})")

    return missing_symbols, mismatches


def _test_model_call(config: LLMConfig) -> str:
    """Tenta uma única chamada mínima; retorna 'ok' ou a mensagem de erro."""
    from app.services.llm import create_llm_provider

    try:
        provider = create_llm_provider(config)
        response = provider.generate("Responda apenas: ok")
        return "ok" if response.content else "resposta vazia"
    except Exception as exc:  # não vaza stack trace
        return f"{type(exc).__name__}: {exc}"


def run_preflight(
    strategies: list[str] | None = None,
    repetitions: int = 5,
    snapshot_set: str = "default",
    test_calls: bool = True,
) -> PreflightReport:
    settings = get_settings()
    strategies = strategies or ["zero_shot", "few_shot", "chain_of_thought"]

    configured_real = [p for p in settings.configured_providers() if p != "fake"]

    configs = load_models_config()
    real_models = [c for c in configs if c.provider != "fake" and settings.api_key_for(c.provider)]

    questions = load_questions()
    categories: dict[str, int] = {}
    for q in questions:
        categories[q["category"]] = categories.get(q["category"], 0) + 1
    dataset_ok = bool(questions) and all("expected_answer" in q for q in questions)

    toolset = FinancialToolset(SnapshotMarketDataProvider(snapshot_set=snapshot_set))
    missing_symbols, mismatches = _validate_references(questions, toolset)

    planned = len(real_models) * len(strategies) * len(questions) * repetitions

    price_table = load_price_table()

    model_tests: dict[str, str] = {}
    if test_calls and real_models:
        for c in real_models:
            model_tests[f"{c.provider}/{c.model}"] = _test_model_call(c)

    messages: list[str] = []
    if not configured_real:
        messages.append(
            "Nenhum provedor real possui API key configurada (apenas 'fake'). "
            "O experimento REAL não pode ser executado. Configure as variáveis de "
            "ambiente (ver .env.example) e adicione os modelos em app/config/models.yaml."
        )
    elif not real_models:
        messages.append(
            "Há provedor com chave, mas nenhum modelo real listado em "
            "app/config/models.yaml. Adicione os modelos desejados para executar."
        )
    if not price_table.is_configured():
        messages.append(
            "Tabela de preços não configurada: 'estimated_cost' será null (não "
            "inventamos custos). Configure app/config/pricing.yaml para estimar custo."
        )
    if missing_symbols:
        messages.append(f"Snapshots ausentes para: {', '.join(missing_symbols)}")
    if mismatches:
        messages.append(f"Referências inconsistentes: {', '.join(mismatches)}")

    return PreflightReport(
        configured_real_providers=configured_real,
        real_models=[f"{c.provider}/{c.model}" for c in real_models],
        n_questions=len(questions),
        categories=categories,
        dataset_ok=dataset_ok,
        missing_symbols=missing_symbols,
        reference_mismatches=mismatches,
        strategies=strategies,
        repetitions=repetitions,
        planned_calls_real=planned,
        price_table_configured=price_table.is_configured(),
        model_call_tests=model_tests,
        messages=messages,
    )


def _print_report(report: PreflightReport) -> None:
    print("=" * 68)
    print("PRÉ-VOO DO EXPERIMENTO")
    print("=" * 68)
    print(f"Provedores reais com chave : {report.configured_real_providers or 'nenhum'}")
    print(f"Modelos reais disponíveis  : {report.real_models or 'nenhum'}")
    print(f"Dataset                    : {report.n_questions} questões  {report.categories}")
    print(f"  dataset íntegro          : {'sim' if report.dataset_ok else 'NÃO'}")
    print(f"  snapshots íntegros       : {'sim' if report.snapshots_ok else 'NÃO'}")
    print(f"  referências consistentes : {'sim' if report.references_ok else 'NÃO'}")
    print(f"Técnicas × repetições      : {report.strategies} × {report.repetitions}")
    print(f"Chamadas reais previstas   : {report.planned_calls_real}")
    print(f"Tabela de preços           : {'configurada' if report.price_table_configured else 'não configurada (custo=null)'}")
    if report.model_call_tests:
        print("Teste de 1 chamada por modelo:")
        for model, status in report.model_call_tests.items():
            print(f"  - {model}: {status}")
    if report.messages:
        print("-" * 68)
        for msg in report.messages:
            print(f"! {msg}")
    print("=" * 68)
    if report.can_run_real:
        print("PRONTO: é possível executar o experimento real (use o runner com --yes).")
    else:
        print("INTERROMPER: não é possível executar chamadas externas (ver acima).")


def main() -> None:
    report = run_preflight()
    _print_report(report)


if __name__ == "__main__":
    main()
