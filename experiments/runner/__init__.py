"""Runner de experimentos científicos."""

from experiments.runner.model_spec import ModelSpec, from_llm_config
from experiments.runner.oracle import build_oracle_provider, oracle_model_spec
from experiments.runner.runner import (
    ExperimentPlan,
    ExperimentRunner,
    ExperimentSummary,
    RunnerConfig,
)
from experiments.runner.storage import ResultStore

__all__ = [
    "ModelSpec",
    "from_llm_config",
    "oracle_model_spec",
    "build_oracle_provider",
    "ExperimentRunner",
    "RunnerConfig",
    "ExperimentPlan",
    "ExperimentSummary",
    "ResultStore",
]
