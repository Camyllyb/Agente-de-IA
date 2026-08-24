"""Registro leve dos nomes canônicos das ferramentas financeiras.

Módulo sem dependências pesadas, para ser importado por validadores (ex.: schema
do benchmark) sem acoplar às implementações das ferramentas.
"""

from __future__ import annotations

# Nomes canônicos das ferramentas expostas ao agente.
TOOL_NAMES: tuple[str, ...] = (
    "get_stock_quote",
    "get_stock_history",
    "compare_stocks",
    "calculate_return",
)

# Valor aceito quando a questão explicitamente não requer ferramenta.
NO_TOOL = "none"


def is_valid_tool(name: str | None) -> bool:
    """True se ``name`` é uma ferramenta conhecida, vazio, ``None`` ou 'none'."""
    if name is None or name == "" or name == NO_TOOL:
        return True
    return name in TOOL_NAMES
