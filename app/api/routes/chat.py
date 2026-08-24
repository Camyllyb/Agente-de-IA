"""Rotas do agente: chat, modelos e estratégias."""

from __future__ import annotations

from fastapi import APIRouter

from app.config.models import load_models_config
from app.config.settings import get_settings
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ModelsResponse,
    StrategiesResponse,
    StrategyInfo,
)
from app.prompts import available_strategies, get_prompt_strategy
from app.services.agent_service import run_chat

router = APIRouter(prefix="/api", tags=["agent"])

STRATEGY_DESCRIPTIONS = {
    "zero_shot": "Apresenta a tarefa diretamente, sem exemplos.",
    "few_shot": "Acrescenta exemplos representativos de entrada/saída.",
    "chain_of_thought": "Solicita raciocínio estruturado antes da conclusão.",
}


@router.post("/chat", response_model=ChatResponse, summary="Conversa com o agente")
def chat(request: ChatRequest) -> ChatResponse:
    """Executa o agente financeiro para a mensagem informada.

    Erros (provedor não suportado, estratégia inexistente, credencial ausente,
    timeout etc.) são retornados como respostas de erro estruturadas, sem stack
    traces (ver ``app.api.errors``).
    """
    return run_chat(request)


@router.get("/models", response_model=ModelsResponse, summary="Modelos configurados")
def list_models() -> ModelsResponse:
    """Lista os modelos configurados, sem expor credenciais."""
    settings = get_settings()
    configs = load_models_config()
    models: list[ModelInfo] = []
    for config in configs:
        requires_key = config.provider != "fake"
        available = (not requires_key) or bool(settings.api_key_for(config.provider))
        models.append(
            ModelInfo(
                provider=config.provider,
                model=config.model,
                requires_key=requires_key,
                available=available,
            )
        )
    return ModelsResponse(
        default_provider=settings.default_provider,
        default_model=settings.default_model,
        models=models,
    )


@router.get("/strategies", response_model=StrategiesResponse, summary="Estratégias de prompting")
def list_strategies() -> StrategiesResponse:
    """Lista as estratégias de prompting disponíveis e suas versões."""
    strategies = [
        StrategyInfo(
            name=name,
            prompt_version=get_prompt_strategy(name).prompt_version,
            description=STRATEGY_DESCRIPTIONS.get(name, ""),
        )
        for name in available_strategies()
    ]
    return StrategiesResponse(strategies=strategies)
