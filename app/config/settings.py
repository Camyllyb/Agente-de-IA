"""Configuração central da aplicação.

Toda a configuração é carregada a partir de variáveis de ambiente (com suporte a
um arquivo ``.env``). As credenciais dos provedores de LLM ficam **exclusivamente**
em variáveis de ambiente — nunca no código.

Use :func:`get_settings` para obter uma instância única (cacheada) de
:class:`Settings`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do projeto: .../financial-agent (dois níveis acima deste arquivo).
BASE_DIR: Path = Path(__file__).resolve().parents[2]

# Provedores de LLM suportados oficialmente pela camada de modelos.
SUPPORTED_PROVIDERS: tuple[str, ...] = ("openai", "anthropic", "google", "openrouter", "fake")


class Settings(BaseSettings):
    """Configuração da aplicação carregada do ambiente.

    Os nomes dos campos correspondem (case-insensitive) às variáveis de ambiente.
    Ex.: o campo ``openai_api_key`` lê ``OPENAI_API_KEY``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicação ----------------------------------------------------------
    app_name: str = "financial-prompt-agent"
    environment: str = "development"
    log_level: str = "INFO"

    # --- LLM padrão ---------------------------------------------------------
    default_provider: str = "fake"
    default_model: str = "fake-model"
    default_temperature: float = 0.0
    default_max_tokens: int = 1024
    default_timeout: int = 60

    # --- Credenciais dos provedores (via ambiente) --------------------------
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- Fonte de dados financeiros -----------------------------------------
    market_data_source: str = "snapshot"  # "snapshot" | "live"
    snapshot_set: str = "default"

    # --- Interface ----------------------------------------------------------
    api_base_url: str = "http://localhost:8000"

    # --- Caminhos (derivados de BASE_DIR) -----------------------------------
    base_dir: Path = Field(default=BASE_DIR)

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def snapshots_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def results_dir(self) -> Path:
        return self.base_dir / "experiments" / "results"

    @property
    def datasets_dir(self) -> Path:
        return self.base_dir / "experiments" / "datasets"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "experiments.db"

    @property
    def models_config_path(self) -> Path:
        return self.base_dir / "app" / "config" / "models.yaml"

    @property
    def pricing_config_path(self) -> Path:
        return self.base_dir / "app" / "config" / "pricing.yaml"

    # --- Utilidades ---------------------------------------------------------
    def api_key_for(self, provider: str) -> Optional[str]:
        """Retorna a chave de API configurada para ``provider`` (ou ``None``)."""
        return {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.google_api_key,
            "openrouter": self.openrouter_api_key,
        }.get(provider.lower())

    def configured_providers(self) -> list[str]:
        """Lista provedores com credencial configurada (``fake`` sempre incluso)."""
        providers = ["fake"]
        for name in ("openai", "anthropic", "google", "openrouter"):
            if self.api_key_for(name):
                providers.append(name)
        return providers


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a instância única de :class:`Settings` (cacheada)."""
    return Settings()
