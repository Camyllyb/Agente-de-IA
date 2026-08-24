"""Modelo de linguagem falso (fake) para testes e desenvolvimento offline.

O :class:`FakeChatModel` é um ``BaseChatModel`` determinístico que:

* funciona para gerações simples (retorna uma resposta padrão ou roteirizada);
* é compatível com o agente LangChain — implementa ``bind_tools`` e pode emitir
  ``tool_calls`` roteirizados, permitindo exercitar o laço do agente sem rede.

Nenhuma chamada externa, chave de API ou crédito pago é necessária.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr

from app.models.llm import LLMConfig
from app.services.llm.base import LLMProvider

# Um item roteirizado pode ser: uma string, uma AIMessage (com ou sem tool_calls),
# ou um callable que recebe as mensagens e devolve uma AIMessage.
ScriptedResponse = str | AIMessage | Callable[[list[BaseMessage]], AIMessage]


def _approx_tokens(text: str) -> int:
    """Aproximação determinística de tokens (contagem de "palavras")."""
    return len(text.split())


def _messages_to_text(messages: Sequence[BaseMessage]) -> str:
    parts: list[str] = []
    for message in messages:
        content = message.content
        parts.append(content if isinstance(content, str) else str(content))
    return " ".join(parts)


class FakeChatModel(BaseChatModel):
    """Chat model determinístico e roteirizável (sem rede)."""

    responses: list[Any] = Field(default_factory=list)
    default_response: str = "[FAKE] Resposta simulada determinística."

    _cursor: int = PrivateAttr(default=0)
    _bound_tools: list[Any] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FakeChatModel":
        """Registra as ferramentas e permanece utilizável pelo agente.

        O modelo falso não interpreta os schemas; a decisão de chamar ferramentas
        vem das respostas roteirizadas (``responses``).
        """
        self._bound_tools = list(tools)
        return self

    def _next_response(self, messages: list[BaseMessage]) -> AIMessage:
        if self._cursor < len(self.responses):
            raw = self.responses[self._cursor]
            self._cursor += 1
        else:
            raw = self.default_response

        if callable(raw) and not isinstance(raw, BaseMessage):
            message = raw(messages)
        elif isinstance(raw, AIMessage):
            message = raw
        elif isinstance(raw, BaseMessage):
            message = AIMessage(content=raw.content)
        else:
            message = AIMessage(content=str(raw))

        # Garante usage_metadata determinístico quando ausente.
        if not getattr(message, "usage_metadata", None):
            input_tokens = _approx_tokens(_messages_to_text(messages))
            text = message.content if isinstance(message.content, str) else str(message.content)
            output_tokens = _approx_tokens(text)
            message = message.model_copy(
                update={
                    "usage_metadata": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    }
                }
            )
        return message

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        message = self._next_response(messages)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def reset(self) -> None:
        """Reinicia o cursor de respostas roteirizadas."""
        self._cursor = 0


class FakeLLMProvider(LLMProvider):
    """Provedor de LLM falso, para testes e execução offline.

    Aceita, via ``config.extra``:
        * ``responses``: lista de respostas roteirizadas;
        * ``default_response``: resposta padrão quando o roteiro se esgota.
    """

    provider_name = "fake"
    required_package = None

    def build_chat_model(self) -> FakeChatModel:
        extra = self.config.extra or {}
        return FakeChatModel(
            responses=list(extra.get("responses", [])),
            default_response=extra.get(
                "default_response", "[FAKE] Resposta simulada determinística."
            ),
        )


def make_fake_config(
    model: str = "fake-model",
    responses: list[Any] | None = None,
    default_response: str | None = None,
    **kwargs: Any,
) -> LLMConfig:
    """Atalho para criar uma :class:`LLMConfig` do provedor fake."""
    extra: dict[str, Any] = {}
    if responses is not None:
        extra["responses"] = responses
    if default_response is not None:
        extra["default_response"] = default_response
    return LLMConfig(provider="fake", model=model, extra=extra, **kwargs)
