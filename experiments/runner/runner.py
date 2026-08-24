"""Executor de experimentos: MODELOS × TÉCNICAS × QUESTÕES × REPETIÇÕES.

Registra tudo em SQLite e permite exportação CSV. Nunca substitui falhas por
resultados inventados: falhas são registradas e a execução continua.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from random import Random
from typing import Callable, Iterable

from app.agents import FinancialAgent
from app.config.logging import get_logger
from app.tools.market_data import SnapshotMarketDataProvider
from experiments.runner.model_spec import ModelSpec
from experiments.runner.storage import ResultStore

logger = get_logger(__name__)

# Estimador de custo opcional: (model, input_tokens, output_tokens) -> custo|None.
PriceEstimator = Callable[[str, int, int], float | None]


@dataclass
class RunnerConfig:
    experiment_id: str
    strategies: list[str]
    repetitions: int = 1
    snapshot_set: str = "default"
    max_runs: int | None = None
    dry_run: bool = False
    randomize: bool = False
    seed: int = 42
    recursion_limit: int = 25
    experiment_type: str = "agent"          # "agent" | "llm_only" (nunca misturados)
    protocol_checksum: str | None = None    # checksum do protocolo congelado


@dataclass
class ExperimentPlan:
    total: int
    effective: int
    models: int
    strategies: int
    questions: int
    repetitions: int

    def describe(self) -> str:
        lines = [
            f"Plano do experimento:",
            f"  modelos     : {self.models}",
            f"  técnicas    : {self.strategies}",
            f"  questões    : {self.questions}",
            f"  repetições  : {self.repetitions}",
            f"  combinações : {self.total}",
        ]
        if self.effective != self.total:
            lines.append(f"  LIMITE (--max-runs) : {self.effective} de {self.total}")
        lines.append(f"  >>> Serão realizadas {self.effective} chamada(s).")
        return "\n".join(lines)


@dataclass
class ExperimentSummary:
    experiment_id: str
    planned: int
    executed: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class _Unit:
    model: ModelSpec
    strategy: str
    question: dict
    repetition: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperimentRunner:
    def __init__(
        self,
        models: list[ModelSpec],
        questions: list[dict],
        config: RunnerConfig,
        store: ResultStore,
        price_estimator: PriceEstimator | None = None,
    ) -> None:
        self.models = models
        self.questions = questions
        self.config = config
        self.store = store
        self.price_estimator = price_estimator
        self.market = SnapshotMarketDataProvider(snapshot_set=config.snapshot_set)

    # --- planejamento -------------------------------------------------------
    def plan(self) -> ExperimentPlan:
        total = (
            len(self.models)
            * len(self.config.strategies)
            * len(self.questions)
            * self.config.repetitions
        )
        effective = min(total, self.config.max_runs) if self.config.max_runs else total
        return ExperimentPlan(
            total=total,
            effective=effective,
            models=len(self.models),
            strategies=len(self.config.strategies),
            questions=len(self.questions),
            repetitions=self.config.repetitions,
        )

    def _units(self) -> list[_Unit]:
        units: list[_Unit] = []
        for model in self.models:
            for strategy in self.config.strategies:
                for question in self.questions:
                    for rep in range(1, self.config.repetitions + 1):
                        units.append(_Unit(model, strategy, question, rep))
        if self.config.randomize:
            Random(self.config.seed).shuffle(units)
        if self.config.max_runs:
            units = units[: self.config.max_runs]
        return units

    # --- execução -----------------------------------------------------------
    def run(self, progress: Callable[[int, int, ExperimentSummary], None] | None = None) -> ExperimentSummary:
        plan = self.plan()
        print(plan.describe())

        summary = ExperimentSummary(experiment_id=self.config.experiment_id, planned=plan.effective)
        if self.config.dry_run:
            print("[dry-run] Nenhuma chamada foi realizada.")
            return summary

        units = self._units()
        for index, unit in enumerate(units, start=1):
            record = self._execute(unit)
            self.store.insert(record)
            summary.executed += 1
            if record["error"]:
                summary.failed += 1
                summary.errors.append(f"{unit.question['id']}/{unit.strategy}: {record['error']}")
            else:
                summary.succeeded += 1
            if progress:
                progress(index, len(units), summary)
        return summary

    def _execute(self, unit: _Unit) -> dict:
        question = unit.question
        base_record = {
            "experiment_id": self.config.experiment_id,
            "experiment_type": self.config.experiment_type,
            "protocol_checksum": self.config.protocol_checksum,
            "timestamp": _now(),
            "question_id": question.get("id"),
            "category": question.get("category"),
            "difficulty": question.get("difficulty"),
            "provider": unit.model.provider,
            "model": unit.model.model,
            "strategy": unit.strategy,
            "prompt_version": None,
            "repetition": unit.repetition,
            "question": question.get("question"),
            "answer": "",
            "expected_answer": question.get("expected_answer"),
            "financial_data": [],
            "tools_called": [],
            "latency_ms": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": None,
            "attempts": 1,
            "retry_reason": None,
            "error": None,
        }

        try:
            provider = unit.model.build(question)
            if self.config.experiment_type == "llm_only":
                from app.agents import LLMOnlyAgent

                agent = LLMOnlyAgent(model=provider, prompt_strategy=unit.strategy)
            else:
                agent = FinancialAgent(
                    model=provider,
                    prompt_strategy=unit.strategy,
                    market_data_provider=self.market,
                    recursion_limit=self.config.recursion_limit,
                )
            result = agent.run(question.get("question", ""))
        except Exception as exc:  # falha registrada; execução continua
            logger.warning("Falha em %s/%s: %s", question.get("id"), unit.strategy, exc)
            base_record["error"] = f"{type(exc).__name__}: {exc}"
            return base_record

        base_record.update(
            {
                "prompt_version": result.prompt_version,
                "answer": result.answer,
                "financial_data": [
                    {"name": c.name, "args": c.args, "output": _maybe_json(c.output)}
                    for c in result.tool_calls
                ],
                "tools_called": result.tools_used,
                "latency_ms": result.latency_ms,
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "total_tokens": result.usage.total_tokens,
                "error": result.error,
            }
        )
        if self.price_estimator and not result.error:
            base_record["estimated_cost"] = self.price_estimator(
                result.model, result.usage.input_tokens, result.usage.output_tokens
            )
        return base_record


def _maybe_json(value: str | None):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value
