"""Modelos de dados do agente financeiro."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.llm import TokenUsage


class ToolCallRecord(BaseModel):
    """Registro de uma chamada de ferramenta feita pelo agente."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None


class AgentResult(BaseModel):
    """Resultado de uma execução do agente.

    Distingue os fatos obtidos por ferramentas (``tool_calls``) da resposta
    elaborada pelo modelo (``answer``).
    """

    answer: str
    provider: str
    model: str
    strategy: str
    prompt_version: str
    tools_used: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage.zero)
    latency_ms: int = 0
    error: str | None = None
