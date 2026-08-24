"""Carregamento da configuração de modelos a partir de YAML.

Permite descrever, em ``app/config/models.yaml``, o conjunto de modelos usado nos
experimentos, no formato conceitual::

    models:
      - provider: openai
        model: MODELO
      - provider: anthropic
        model: MODELO

Nenhuma versão de modelo é fixada no código — os identificadores vêm do YAML.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.config.settings import get_settings
from app.models.llm import LLMConfig


def load_models_config(path: Path | None = None) -> list[LLMConfig]:
    """Lê o YAML de modelos e retorna uma lista de :class:`LLMConfig`.

    Retorna lista vazia se o arquivo não existir. Um bloco ``defaults`` (opcional)
    fornece temperatura/max_tokens/timeout padrão para as entradas.
    """
    settings = get_settings()
    path = path or settings.models_config_path
    if not path.exists():
        return []

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = data.get("defaults", {}) or {}
    entries = data.get("models", []) or []

    configs: list[LLMConfig] = []
    for entry in entries:
        configs.append(
            LLMConfig(
                provider=entry["provider"],
                model=entry["model"],
                temperature=entry.get("temperature", defaults.get("temperature", 0.0)),
                max_tokens=entry.get("max_tokens", defaults.get("max_tokens", 1024)),
                timeout=entry.get("timeout", defaults.get("timeout", 60)),
                extra=entry.get("extra", {}) or {},
            )
        )
    return configs
