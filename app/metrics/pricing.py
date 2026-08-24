"""Estimativa de custo a partir de uma tabela de preços configurável e versionada.

Nunca fixa preços silenciosamente: se um modelo não estiver na tabela, o custo
estimado é ``None``. A versão e o timestamp da tabela são preservados para
rastreabilidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config.settings import get_settings


@dataclass
class PriceTable:
    version: str
    generated_at: str
    unit: str  # "per_1k_tokens" | "per_1m_tokens"
    currency: str
    prices: dict[str, dict] = field(default_factory=dict)

    def _divisor(self) -> int:
        return 1_000 if self.unit == "per_1k_tokens" else 1_000_000

    def is_configured(self) -> bool:
        return bool(self.prices)

    def estimate(self, model: str, input_tokens: int, output_tokens: int) -> float | None:
        """Custo estimado ou ``None`` se o modelo não tiver preço configurado."""
        entry = self.prices.get(model)
        if not entry:
            return None
        divisor = self._divisor()
        cost = (
            (input_tokens / divisor) * float(entry.get("input", 0.0))
            + (output_tokens / divisor) * float(entry.get("output", 0.0))
        )
        return round(cost, 6)

    def metadata(self) -> dict:
        return {
            "price_table_version": self.version,
            "price_table_generated_at": self.generated_at,
            "unit": self.unit,
            "currency": self.currency,
            "configured": self.is_configured(),
        }


def load_price_table(path: Path | None = None) -> PriceTable:
    """Carrega a tabela de preços (retorna uma tabela vazia se não configurada)."""
    path = path or get_settings().pricing_config_path
    if not path.exists():
        return PriceTable(version="unset", generated_at="unset", unit="per_1m_tokens", currency="USD")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PriceTable(
        version=str(data.get("version", "unset")),
        generated_at=str(data.get("generated_at", "unset")),
        unit=str(data.get("unit", "per_1m_tokens")),
        currency=str(data.get("currency", "USD")),
        prices=data.get("prices") or {},
    )
