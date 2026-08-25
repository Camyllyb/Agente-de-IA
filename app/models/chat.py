"""Schemas de entrada/saída da API de chat."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Requisição do endpoint ``POST /api/chat``."""

    message: str = Field(..., description="Pergunta do usuário.")
    strategy: str = Field("zero_shot", description="Técnica de prompting.")
    provider: str | None = Field(None, description="Provedor de LLM (usa o padrão se omitido).")
    model: str | None = Field(None, description="Modelo (usa o padrão se omitido).")
    data_source: str | None = Field(
        None, description="Fonte de dados: 'snapshot' ou 'live' (usa o padrão se omitido)."
    )
    snapshot_set: str | None = Field(None, description="Conjunto de snapshots (fonte snapshot).")
    temperature: float | None = Field(None, description="Temperatura (usa o padrão se omitido).")
    max_tokens: int | None = Field(None, description="Limite de tokens de saída (opcional).")


class Metrics(BaseModel):
    """Métricas de execução."""

    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float | None = None


class ChatResponse(BaseModel):
    """Resposta do endpoint ``POST /api/chat``."""

    answer: str
    strategy: str
    prompt_version: str
    provider: str
    model: str
    data_source: str
    tools_used: list[str] = Field(default_factory=list)
    data_used: list[dict] = Field(
        default_factory=list,
        description="Dados estruturados obtidos das ferramentas (ativo, valor, data, moeda, fonte).",
    )
    metrics: Metrics


class ModelInfo(BaseModel):
    """Informação de um modelo configurado (sem expor credenciais)."""

    provider: str
    model: str
    requires_key: bool
    available: bool


class ModelsResponse(BaseModel):
    default_provider: str
    default_model: str
    models: list[ModelInfo]


class StrategyInfo(BaseModel):
    name: str
    prompt_version: str
    description: str


class StrategiesResponse(BaseModel):
    strategies: list[StrategyInfo]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
