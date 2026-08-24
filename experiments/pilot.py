"""Piloto experimental (PILOT_ONLY).

Serve APENAS para identificar problemas metodológicos e técnicos antes do
experimento final. Seus resultados NÃO podem ser misturados ao experimento
científico final e NÃO produzem conclusão sobre qual técnica é melhor.

Configuração padrão: 10 questões × 1 modelo × 3 estratégias × 3 repetições = 90.
Todos os artefatos são rotulados com ``PILOT_ONLY``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config.settings import get_settings
from app.metrics import build_scored_records, load_price_table
from app.metrics.answer_parsing import final_answer_line
from experiments.datasets import load_questions
from experiments.runner import (
    ExperimentRunner,
    ResultStore,
    RunnerConfig,
    from_llm_config,
    oracle_model_spec,
)
from experiments.runner.model_spec import ModelSpec

PILOT_LABEL = "PILOT_ONLY"


@dataclass
class PilotConfig:
    num_questions: int = 10
    strategies: list[str] = field(default_factory=lambda: ["zero_shot", "few_shot", "chain_of_thought"])
    repetitions: int = 3
    experiment_type: str = "agent"
    snapshot_set: str = "default"


def pilot_prechecks(model_spec: ModelSpec, questions: list[dict]) -> dict:
    """Verificações antes do piloto (não fabricam nada)."""
    settings = get_settings()
    price_table = load_price_table()
    checks = {
        "dataset_valid": bool(questions),
        "model_configured": bool(model_spec),
        "api_key_available": model_spec.provider == "fake" or bool(settings.api_key_for(model_spec.provider)),
        "price_table_configured": price_table.is_configured(),
    }
    checks["ready"] = checks["dataset_valid"] and checks["model_configured"] and checks["api_key_available"]
    return checks


class PilotAuditor:
    """Gera o relatório de auditoria do piloto a partir dos registros pontuados."""

    def audit(self, scored: list[dict], questions_by_id: dict[str, dict]) -> dict:
        n = len(scored)
        errors = [r for r in scored if r.get("error")]
        empty = [r for r in scored if not (r.get("answer") or "").strip()]
        parsing = [
            r for r in scored
            if r.get("factual_applicable") and r.get("predicted_value") is None and not r.get("error")
        ]
        tool_failures = [r for r in scored if r.get("tool_execution_ok") is False]
        format_dev = [
            r for r in scored
            if (r.get("answer") or "").strip() and "resposta final" not in (r.get("answer") or "").lower()
        ]

        # Gabaritos ausentes para questões objetivas.
        gabarito_issues = []
        for qid, q in questions_by_id.items():
            ea = q.get("expected_answer", {})
            if q.get("category") in ("factual", "calculation", "comparison", "return_calculation", "factual_quote") \
                    and ea.get("type") not in ("rubric", "qualitative") and ea.get("value") is None:
                gabarito_issues.append(qid)

        # Inconsistência entre repetições (possível ambiguidade).
        by_group: dict[tuple, list] = {}
        for r in scored:
            key = (r.get("question_id"), r.get("strategy"))
            by_group.setdefault(key, []).append(r.get("is_correct"))
        inconsistent = [
            f"{qid}/{strat}" for (qid, strat), vals in by_group.items()
            if len([v for v in vals if v is not None]) > 1 and len(set(v for v in vals if v is not None)) > 1
        ]

        tokens = [r.get("total_tokens", 0) for r in scored]
        costs = [r.get("estimated_cost") for r in scored if r.get("estimated_cost") is not None]

        return {
            "label": PILOT_LABEL,
            "n_runs": n,
            "errors": len(errors),
            "empty_responses": len(empty),
            "parsing_failures": len(parsing),
            "tool_failures": len(tool_failures),
            "format_deviations": len(format_dev),
            "gabarito_issues": gabarito_issues,
            "inconsistent_repetitions": inconsistent,
            "tokens_total": sum(tokens),
            "tokens_mean": (sum(tokens) / n) if n else 0,
            "estimated_cost_total": sum(costs) if costs else None,
            "note": "PILOT_ONLY — não use para conclusões científicas sobre técnicas.",
        }


def run_pilot(
    store: ResultStore,
    model_spec: ModelSpec,
    config: PilotConfig | None = None,
    questions: list[dict] | None = None,
    experiment_id: str | None = None,
) -> tuple[object, dict, dict]:
    """Executa o piloto e retorna (summary, prechecks, audit)."""
    config = config or PilotConfig()
    questions = (questions or load_questions())[: config.num_questions]
    prechecks = pilot_prechecks(model_spec, questions)

    experiment_id = experiment_id or f"{PILOT_LABEL}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    if not prechecks["ready"]:
        return None, prechecks, {"label": PILOT_LABEL, "halted": True, "reason": "pré-checagens falharam"}

    runner_config = RunnerConfig(
        experiment_id=experiment_id,
        strategies=config.strategies,
        repetitions=config.repetitions,
        snapshot_set=config.snapshot_set,
        experiment_type=config.experiment_type,
    )
    runner = ExperimentRunner([model_spec], questions, runner_config, store)
    summary = runner.run()

    qmap = {q["id"]: q for q in questions}
    scored = build_scored_records(store.fetch_all(experiment_id), qmap)
    audit = PilotAuditor().audit(scored, qmap)
    return summary, prechecks, audit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Piloto experimental (PILOT_ONLY).")
    parser.add_argument("--oracle", action="store_true", help="Usa o oráculo determinístico (offline).")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--experiment-type", default="agent", choices=["agent", "llm_only"])
    parser.add_argument("--db", default="data/pilot.db")
    args = parser.parse_args(argv)

    if args.oracle or not args.provider:
        model_spec = oracle_model_spec()
    else:
        from app.models.llm import LLMConfig

        model_spec = from_llm_config(LLMConfig(provider=args.provider, model=args.model or "modelo"))

    store = ResultStore(args.db)
    summary, prechecks, audit = run_pilot(
        store, model_spec, PilotConfig(experiment_type=args.experiment_type)
    )
    store.close()

    print("PILOT_ONLY — pré-checagens:")
    for k, v in prechecks.items():
        print(f"  {k}: {v}")
    if summary is None:
        print("Piloto interrompido (pré-checagens falharam).")
        return 1
    print("\nRelatório de auditoria do piloto:")
    for k, v in audit.items():
        print(f"  {k}: {v}")
    print("\n(NÃO produz conclusão científica sobre qual técnica é melhor.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
