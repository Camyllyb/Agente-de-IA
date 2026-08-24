"""Auditoria de prontidão para o experimento final.

    python -m experiments.readiness

Responde: "Este projeto está metodologicamente pronto para o experimento final?"
Verifica dataset, snapshots, gabaritos, prompts, modelos, protocolo e pipeline.
Se qualquer componente crítico falhar, o experimento final (``--final``) é bloqueado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"

# Componentes críticos: se qualquer um falhar, NÃO está pronto.
_CRITICAL = {"DATASET", "SNAPSHOTS", "REFERENCES", "PROMPTS", "MODELS", "PROTOCOL"}


@dataclass
class Check:
    name: str
    status: str
    details: str = ""


@dataclass
class ReadinessReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, status: str, details: str = "") -> None:
        self.checks.append(Check(name, status, details))

    @property
    def ready(self) -> bool:
        return all(c.status == PASS for c in self.checks if c.name in _CRITICAL)

    def render(self) -> str:
        lines = []
        for c in self.checks:
            dots = "." * max(3, 22 - len(c.name))
            suffix = f"  ({c.details})" if c.details else ""
            lines.append(f"{c.name} {dots} {c.status}{suffix}")
        lines.append("")
        lines.append(f"FINAL EXPERIMENT READY: {'YES' if self.ready else 'NO'}")
        return "\n".join(lines)


def _check_dataset(report: ReadinessReport, dataset_path: Path) -> object | None:
    if not dataset_path.exists():
        report.add("DATASET", FAIL, "benchmark_v2.json ausente")
        return None
    from experiments.datasets.benchmark_loader import load_benchmark_dataset
    from app.models.benchmark import validate_dataset

    dataset = load_benchmark_dataset(dataset_path)
    result = validate_dataset(dataset, enforce_distribution=True)
    if result.ok:
        report.add("DATASET", PASS, f"{len(dataset.questions)} questões, 6/cat, 10/dif")
    else:
        report.add("DATASET", FAIL, f"{len(result.errors)} erro(s): {result.errors[0] if result.errors else ''}")
    return dataset


def _check_references(report: ReadinessReport, dataset) -> None:
    if dataset is None:
        report.add("REFERENCES", FAIL, "sem dataset")
        return
    from app.models.benchmark import QuestionCategory

    objective = [q for q in dataset.questions
                 if q.category in (QuestionCategory.factual, QuestionCategory.calculation, QuestionCategory.comparison)
                 and q.expected_answer.type not in ("rubric", "qualitative")]
    missing = [q.id for q in objective if q.expected_answer.value is None]
    interp = [q for q in dataset.questions if q.category == QuestionCategory.interpretation]
    interp_missing = [q.id for q in interp if not q.required_facts and not q.evaluation_metrics]
    tools_missing = [q.id for q in dataset.questions if q.category == QuestionCategory.tool_use and not q.expected_tool]

    if missing or interp_missing or tools_missing:
        report.add("REFERENCES", FAIL,
                   f"{len(missing)} sem gabarito; {len(interp_missing)} interpretativas sem rubrica; "
                   f"{len(tools_missing)} tool_use sem ferramenta")
    else:
        report.add("REFERENCES", PASS, "gabaritos/rubricas/ferramentas definidos")


def _check_snapshots(report: ReadinessReport) -> None:
    from app.snapshots import SnapshotManager, SnapshotStatus

    manager = SnapshotManager()
    frozen = [m for m in manager.list_snapshots() if m.status == SnapshotStatus.frozen]
    if not frozen:
        report.add("SNAPSHOTS", FAIL, "nenhum snapshot congelado")
        return
    bad = [m.snapshot_id for m in frozen if not manager.verify_integrity(m.snapshot_id)]
    if bad:
        report.add("SNAPSHOTS", FAIL, f"checksum inválido: {bad}")
    else:
        report.add("SNAPSHOTS", PASS, f"{len(frozen)} congelado(s), checksum ok")


def _check_prompts(report: ReadinessReport) -> None:
    from app.prompts import available_strategies, get_prompt_strategy

    strategies = available_strategies()
    versions = [get_prompt_strategy(s).prompt_version for s in strategies]
    if len(strategies) == 3 and all(versions):
        report.add("PROMPTS", PASS, ", ".join(versions))
    else:
        report.add("PROMPTS", FAIL, "estratégias/versões incompletas")


def _check_models(report: ReadinessReport) -> None:
    from app.config.models import load_models_config
    from app.config.settings import get_settings

    settings = get_settings()
    real = [c for c in load_models_config() if c.provider != "fake" and settings.api_key_for(c.provider)]
    if real:
        report.add("MODELS", PASS, f"{len(real)} modelo(s) real(is) com chave")
    else:
        report.add("MODELS", FAIL, "nenhum modelo real com API key configurada")


def _check_protocol(report: ReadinessReport) -> None:
    from experiments.protocol import ProtocolManager, ProtocolStatus

    manager = ProtocolManager()
    versions = manager.list_versions()
    frozen = []
    for v in versions:
        p = manager.load(v)
        if p.status == ProtocolStatus.frozen and p.verify_checksum():
            frozen.append(v)
    if frozen:
        report.add("PROTOCOL", PASS, f"congelado: {frozen[-1]}")
    else:
        report.add("PROTOCOL", FAIL, "nenhum protocolo congelado com checksum válido")


def _check_pipeline(report: ReadinessReport) -> None:
    try:
        import experiments.exporter  # noqa: F401
        import app.metrics  # noqa: F401
        from app.metrics import generate_blind_evaluation  # noqa: F401
        dashboard = Path("frontend/pages/1_Experimentos.py").exists()
        if dashboard:
            report.add("METRICS", PASS, "métricas, exportação, dashboard e avaliação cega disponíveis")
        else:
            report.add("METRICS", WARN, "dashboard não encontrado")
    except Exception as exc:  # pragma: no cover
        report.add("METRICS", FAIL, str(exc))


def run_readiness(dataset_path: str | Path = "experiments/datasets/benchmark_v2.json") -> ReadinessReport:
    report = ReadinessReport()
    dataset = _check_dataset(report, Path(dataset_path))
    _check_snapshots(report)
    _check_references(report, dataset)
    _check_prompts(report)
    _check_models(report)
    _check_protocol(report)
    _check_pipeline(report)
    return report


def assert_ready_for_final(dataset_path: str | Path = "experiments/datasets/benchmark_v2.json") -> None:
    """Levanta RuntimeError se o projeto não estiver pronto para o experimento final."""
    report = run_readiness(dataset_path)
    if not report.ready:
        failed = [c.name for c in report.checks if c.name in _CRITICAL and c.status != PASS]
        raise RuntimeError(
            "Experimento final BLOQUEADO: componentes críticos não prontos: "
            + ", ".join(failed)
        )


def main(argv=None) -> int:
    report = run_readiness()
    print(report.render())
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
