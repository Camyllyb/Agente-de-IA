"""Testes do pacote de reprodutibilidade (offline)."""

from __future__ import annotations

from pathlib import Path

from experiments.reproducibility import build_reproducibility_package


def test_package_generated_with_expected_files(tmp_path) -> None:
    out = tmp_path / "repro"
    manifest = build_reproducibility_package(out, now="2026-08-24T00:00:00Z")

    for name in (
        "protocol.json", "snapshot_metadata.json", "model_config.json",
        "metric_definitions.json", "environment.txt", "requirements_lock.txt",
        "README.md", "manifest.json",
    ):
        assert (out / name).exists(), name
    assert (out / "prompt_versions" / "versions.json").exists()
    assert (out / "prompt_versions" / "zero_shot.txt").exists()

    assert manifest["contains_secrets"] is False
    assert manifest["python_version"]


def test_package_contains_no_secrets(tmp_path) -> None:
    out = tmp_path / "repro"
    build_reproducibility_package(out, now="2026-08-24T00:00:00Z")
    # Nenhuma chave de API real deve aparecer em nenhum arquivo gerado.
    for path in out.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "sk-" not in text
            assert "OPENAI_API_KEY=" not in text


def test_requirements_lock_not_empty(tmp_path) -> None:
    out = tmp_path / "repro"
    build_reproducibility_package(out, now="2026-08-24T00:00:00Z")
    lock = (out / "requirements_lock.txt").read_text(encoding="utf-8")
    assert "pydantic==" in lock
    assert "langchain==" in lock
