"""Pacote de reprodutibilidade científica.

    python -m experiments.reproducibility

Gera um diretório com tudo o que outro pesquisador precisa para reproduzir o
experimento — SEM incluir chaves de API, segredos ou credenciais.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

METRIC_DEFINITIONS = {
    "factual_precision": "Acerto numérico/categórico da resposta vs. referência (com tolerância).",
    "latency_ms": "Tempo de resposta em milissegundos.",
    "tokens": "Tokens de entrada, saída e total.",
    "estimated_cost": "Custo estimado via tabela de preços versionada (null se não configurada).",
    "success_rate": "Fração de execuções sem erro.",
    "tool_selection_accuracy": "(Agente) ferramenta esperada foi utilizada.",
    "tool_execution_success": "(Agente) chamadas de ferramenta retornaram dados válidos.",
    "data_grounding": "(Agente) resposta fundamentada nos dados obtidos.",
    "task_success": "Tarefa concluída com sucesso.",
    "human_criteria": "Avaliação humana 1-5: relevância, clareza, completude, precisão percebida.",
    "agreement": "Concordância entre avaliadores: Cohen/weighted Kappa, Krippendorff's Alpha.",
}


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else "unavailable"
    except Exception:  # pragma: no cover
        return "unavailable"


def _requirements_lock() -> str:
    from importlib.metadata import distributions

    entries = []
    for dist in distributions():
        name = dist.metadata["Name"] if dist.metadata else None
        if name:
            entries.append(f"{name}=={dist.version}")
    return "\n".join(sorted(set(entries), key=str.lower))


def build_reproducibility_package(
    out_dir: str | Path = "reproducibility",
    dataset_path: str | Path = "experiments/datasets/benchmark_v2.json",
    now: str | None = None,
) -> dict:
    out = Path(out_dir)
    (out / "prompt_versions").mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc).isoformat()
    checksums: dict[str, str | None] = {}

    # --- dataset ------------------------------------------------------------
    dataset_path = Path(dataset_path)
    if dataset_path.exists():
        content = dataset_path.read_text(encoding="utf-8")
        (out / "dataset.json").write_text(content, encoding="utf-8")
        checksums["dataset.json"] = _sha256_file(out / "dataset.json")

    # --- protocolo ----------------------------------------------------------
    from experiments.protocol import ProtocolManager, ProtocolStatus

    manager = ProtocolManager()
    frozen = [v for v in manager.list_versions()
              if manager.load(v).status == ProtocolStatus.frozen]
    if frozen:
        protocol = manager.load(frozen[-1])
        (out / "protocol.json").write_text(protocol.model_dump_json(indent=2), encoding="utf-8")
    else:
        (out / "protocol.json").write_text(
            json.dumps({"status": "none",
                        "note": "Nenhum protocolo congelado. Congele um protocolo antes do experimento final."},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    checksums["protocol.json"] = _sha256_file(out / "protocol.json")

    # --- snapshots (apenas metadados) --------------------------------------
    from app.snapshots import SnapshotManager

    metas = [m.model_dump(mode="json") for m in SnapshotManager().list_snapshots()]
    (out / "snapshot_metadata.json").write_text(
        json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")
    checksums["snapshot_metadata.json"] = _sha256_file(out / "snapshot_metadata.json")

    # --- prompts ------------------------------------------------------------
    from app.prompts import available_strategies, get_prompt_strategy

    versions = {}
    for name in available_strategies():
        strategy = get_prompt_strategy(name)
        versions[name] = strategy.prompt_version
        (out / "prompt_versions" / f"{name}.txt").write_text(
            strategy.build_system_prompt(), encoding="utf-8")
    (out / "prompt_versions" / "versions.json").write_text(
        json.dumps(versions, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- model_config (SEM chaves) -----------------------------------------
    models_yaml = Path("app/config/models.yaml")
    model_config = models_yaml.read_text(encoding="utf-8") if models_yaml.exists() else ""
    (out / "model_config.json").write_text(
        json.dumps({"models_yaml": model_config,
                    "note": "Sem chaves de API. Configure-as por variáveis de ambiente."},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # --- definições de métricas --------------------------------------------
    (out / "metric_definitions.json").write_text(
        json.dumps(METRIC_DEFINITIONS, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- ambiente -----------------------------------------------------------
    git_commit = _git_commit()
    environment = (
        f"generated_at: {now}\n"
        f"python_version: {sys.version.splitlines()[0]}\n"
        f"platform: {platform.platform()}\n"
        f"machine: {platform.machine()}\n"
        f"git_commit: {git_commit}\n"
    )
    (out / "environment.txt").write_text(environment, encoding="utf-8")
    (out / "requirements_lock.txt").write_text(_requirements_lock(), encoding="utf-8")

    # --- README + manifest --------------------------------------------------
    manifest = {
        "generated_at": now,
        "git_commit": git_commit,
        "python_version": sys.version.splitlines()[0],
        "platform": platform.platform(),
        "prompt_versions": versions,
        "checksums": checksums,
        "contains_secrets": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "README.md").write_text(_readme(now, git_commit), encoding="utf-8")

    return manifest


def _readme(now: str, git_commit: str) -> str:
    return (
        "# Pacote de reprodutibilidade — financial-prompt-agent\n\n"
        f"Gerado em: {now}\n\n"
        f"Commit Git: `{git_commit}`\n\n"
        "## Conteúdo\n\n"
        "- `protocol.json` — protocolo experimental congelado (decisões metodológicas).\n"
        "- `dataset.json` — dataset de benchmark (30 questões).\n"
        "- `snapshot_metadata.json` — metadados dos snapshots (checksums, período, fontes).\n"
        "- `prompt_versions/` — prompts de sistema versionados de cada estratégia.\n"
        "- `model_config.json` — configuração dos modelos (SEM chaves de API).\n"
        "- `metric_definitions.json` — definição das métricas.\n"
        "- `environment.txt` — versão do Python, SO, data, commit.\n"
        "- `requirements_lock.txt` — versões exatas das bibliotecas.\n"
        "- `manifest.json` — checksums e resumo.\n\n"
        "## Como reproduzir\n\n"
        "1. Recrie o ambiente: `pip install -r requirements_lock.txt`.\n"
        "2. Configure as chaves de API por variáveis de ambiente (ver `.env.example`).\n"
        "3. Restaure os snapshots congelados referenciados em `snapshot_metadata.json`.\n"
        "4. Verifique a prontidão: `python -m experiments.readiness`.\n"
        "5. Execute: `python -m experiments.runner --models-config --final --yes`.\n\n"
        "**Este pacote NÃO contém chaves, segredos ou credenciais.**\n"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gera o pacote de reprodutibilidade.")
    parser.add_argument("--out", default="reproducibility")
    args = parser.parse_args(argv)
    manifest = build_reproducibility_package(args.out)
    print(f"Pacote de reprodutibilidade gerado em '{args.out}':")
    print(f"  python: {manifest['python_version']}")
    print(f"  git: {manifest['git_commit']}")
    print(f"  checksums: {list(manifest['checksums'])}")
    print("  contém segredos: NÃO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
