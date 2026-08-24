"""Exceções do agente financeiro."""

from __future__ import annotations


class AgentError(Exception):
    """Erro base do agente."""


class AgentExecutionError(AgentError):
    """Falha durante a execução do agente (invocação do grafo)."""
