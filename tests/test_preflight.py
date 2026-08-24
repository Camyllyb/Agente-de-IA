"""Testes do pré-voo do experimento (offline)."""

from __future__ import annotations

from experiments.preflight import run_preflight


def test_preflight_dataset_and_references_ok() -> None:
    report = run_preflight(test_calls=False)
    assert report.dataset_ok is True
    assert report.snapshots_ok is True
    assert report.references_ok is True  # referências recomputadas batem com o dataset
    assert report.n_questions == 20


def test_preflight_without_keys_cannot_run_real() -> None:
    report = run_preflight(test_calls=False)
    # No ambiente de teste não há chaves reais -> não é possível rodar experimento real.
    if not report.configured_real_providers:
        assert report.can_run_real is False
        assert report.planned_calls_real == 0
        assert any("não pode ser executado" in m for m in report.messages)
