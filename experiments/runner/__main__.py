"""CLI do runner de experimentos.

Exemplos:
    # Pré-visualização (não executa nada)
    python -m experiments.runner --dry-run

    # Pipeline offline com o oráculo determinístico (não é um LLM real)
    python -m experiments.runner --oracle --export experiments/results/pipeline_raw.csv

    # Execução real (exige confirmação --yes e chaves de API configuradas)
    python -m experiments.runner --provider openai --model <modelo> --repetitions 5 --yes
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from app.config.settings import get_settings
from app.models.llm import LLMConfig
from app.prompts import available_strategies
from experiments.datasets import load_questions
from experiments.runner.model_spec import ModelSpec, from_llm_config
from experiments.runner.oracle import oracle_model_spec
from experiments.runner.runner import ExperimentRunner, RunnerConfig
from experiments.runner.storage import ResultStore


def _default_experiment_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"exp-{stamp}"


def _build_models(args) -> list[ModelSpec]:
    if args.oracle:
        return [oracle_model_spec()]
    if args.models_config:
        from app.config.models import load_models_config

        configs = load_models_config()
        if not configs:
            raise SystemExit("Nenhum modelo em app/config/models.yaml.")
        return [from_llm_config(c) for c in configs]
    settings = get_settings()
    config = LLMConfig(
        provider=args.provider or settings.default_provider,
        model=args.model or settings.default_model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )
    return [from_llm_config(config)]


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Runner de experimentos científicos.")
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--questions", default=None, help="Caminho do dataset.")
    parser.add_argument("--limit-questions", type=int, default=None)
    parser.add_argument(
        "--strategies",
        default=",".join(available_strategies()),
        help="Lista separada por vírgula.",
    )
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--snapshot-set", default="default")
    parser.add_argument("--max-runs", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--randomize", action="store_true")
    parser.add_argument("--seed", type=int, default=42)

    # Seleção de modelo
    parser.add_argument("--oracle", action="store_true", help="Usa o oráculo determinístico (pipeline).")
    parser.add_argument("--models-config", action="store_true", help="Usa app/config/models.yaml.")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=int, default=60)

    parser.add_argument("--db", default=None, help="Caminho do SQLite.")
    parser.add_argument("--export", default=None, help="Exporta CSV ao final.")
    parser.add_argument("--yes", action="store_true", help="Confirma chamadas a provedores reais (pagas).")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)
    settings = get_settings()

    experiment_id = args.experiment_id or _default_experiment_id()
    questions = load_questions(args.questions)
    if args.limit_questions:
        questions = questions[: args.limit_questions]
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    models = _build_models(args)

    config = RunnerConfig(
        experiment_id=experiment_id,
        strategies=strategies,
        repetitions=args.repetitions,
        snapshot_set=args.snapshot_set,
        max_runs=args.max_runs,
        dry_run=args.dry_run,
        randomize=args.randomize,
        seed=args.seed,
    )

    store = ResultStore(args.db or settings.database_path)
    runner = ExperimentRunner(models, questions, config, store)

    plan = runner.plan()
    # Guarda contra chamadas pagas acidentais.
    uses_real_provider = any(m.provider != "fake" for m in models)
    if uses_real_provider and not args.dry_run and not args.yes:
        print(plan.describe())
        print(
            "\nATENÇÃO: esta execução usaria provedores reais (possivelmente pagos).\n"
            "Reveja o plano acima e adicione --yes para confirmar."
        )
        store.close()
        return

    def _progress(i: int, total: int, summary) -> None:
        if i == 1 or i % 10 == 0 or i == total:
            print(f"  [{i}/{total}] ok={summary.succeeded} falhas={summary.failed}")

    summary = runner.run(progress=_progress)

    print(
        f"\nExperimento '{experiment_id}' concluído: "
        f"executadas={summary.executed}, sucesso={summary.succeeded}, falhas={summary.failed}."
    )
    if summary.failed:
        print("Falhas registradas (execução continuou):")
        for err in summary.errors[:20]:
            print(f"  - {err}")

    if args.export and not args.dry_run:
        n = store.export_csv(args.export, experiment_id)
        print(f"Exportadas {n} linha(s) para {args.export}")

    store.close()


if __name__ == "__main__":
    main()
