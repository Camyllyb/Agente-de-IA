"""Testes da auditoria de prontidão (offline)."""

from __future__ import annotations

import pytest

from experiments.readiness import PASS, assert_ready_for_final, run_readiness


def test_readiness_report_structure() -> None:
    report = run_readiness()
    names = {c.name for c in report.checks}
    assert {"DATASET", "SNAPSHOTS", "REFERENCES", "PROMPTS", "MODELS", "PROTOCOL"} <= names


def test_prompts_component_passes() -> None:
    report = run_readiness()
    prompts = next(c for c in report.checks if c.name == "PROMPTS")
    assert prompts.status == PASS  # 3 estratégias versionadas sempre disponíveis


def test_not_ready_without_references_and_data() -> None:
    """Com o dataset em rascunho (sem gabaritos), NÃO está pronto."""
    report = run_readiness()
    refs = next(c for c in report.checks if c.name == "REFERENCES")
    assert refs.status != PASS  # rascunhos sem gabarito
    assert report.ready is False
    assert "FINAL EXPERIMENT READY: NO" in report.render()


def test_assert_ready_raises_when_not_ready() -> None:
    with pytest.raises(RuntimeError):
        assert_ready_for_final()
