"""Ferramentas financeiras utilizadas pelo agente.

Todas as ferramentas obtêm valores **exclusivamente** de uma
:class:`~app.tools.market_data.base.MarketDataProvider`. Quando um dado não
existe, retornam explicitamente ``{"found": false, ...}`` — nunca inventam preços
ou valores de mercado.

Cada resposta identifica: ativo, data(s), valor(es), moeda e fonte.

``FinancialToolset`` oferece a API programática (retornando dicionários
estruturados). ``build_market_tools`` embrulha o toolset como ferramentas do
LangChain, para uso pelo agente.
"""

from __future__ import annotations

import json
from typing import Any

from app.config.logging import get_logger
from app.tools.market_data.base import MarketDataError, MarketDataProvider

logger = get_logger(__name__)


class FinancialToolset:
    """Ferramentas financeiras ligadas a uma fonte de dados injetada."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    @property
    def source(self) -> str:
        return self.provider.source_name

    # --- get_stock_quote ----------------------------------------------------
    def get_stock_quote(self, symbol: str) -> dict[str, Any]:
        """Cotação mais recente disponível para ``symbol``."""
        try:
            quote = self.provider.get_quote(symbol)
        except MarketDataError as exc:
            logger.info("Cotação não encontrada para %s: %s", symbol, exc)
            return {"found": False, "symbol": symbol, "error": str(exc), "source": self.source}
        return {
            "found": True,
            "symbol": quote.symbol,
            "price": quote.price,
            "currency": quote.currency,
            "date": quote.date,
            "timestamp": quote.timestamp,
            "source": quote.source,
        }

    # --- get_stock_history --------------------------------------------------
    def get_stock_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Histórico de preços de ``symbol`` entre ``start_date`` e ``end_date`` (ISO)."""
        try:
            history = self.provider.get_history(symbol, start_date, end_date)
        except MarketDataError as exc:
            logger.info("Histórico não encontrado para %s: %s", symbol, exc)
            return {
                "found": False,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "error": str(exc),
                "source": self.source,
            }
        return {
            "found": True,
            "symbol": history.symbol,
            "currency": history.currency,
            "source": history.source,
            "start_date": history.start_date,
            "end_date": history.end_date,
            "count": len(history.bars),
            "bars": [bar.model_dump() for bar in history.bars],
        }

    # --- calculate_return ---------------------------------------------------
    def calculate_return(
        self, symbol: str, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Retorno percentual de ``symbol`` no período.

        Convenção: usa o fechamento da primeira barra disponível em/ após
        ``start_date`` e o da última barra em/ antes de ``end_date``.
        """
        try:
            history = self.provider.get_history(symbol, start_date, end_date)
        except MarketDataError as exc:
            logger.info("Retorno indisponível para %s: %s", symbol, exc)
            return {
                "found": False,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "error": str(exc),
                "source": self.source,
            }

        first, last = history.bars[0], history.bars[-1]
        start_price, end_price = first.close, last.close
        return_abs = end_price - start_price
        return_pct = (end_price / start_price - 1.0) * 100.0 if start_price else None
        return {
            "found": True,
            "symbol": history.symbol,
            "start_date": start_date,
            "end_date": end_date,
            "start_observed_date": first.date,
            "end_observed_date": last.date,
            "start_price": start_price,
            "end_price": end_price,
            "return_abs": round(return_abs, 6),
            "return_pct": round(return_pct, 6) if return_pct is not None else None,
            "currency": history.currency,
            "source": history.source,
        }

    # --- compare_stocks -----------------------------------------------------
    def compare_stocks(self, symbols: list[str] | str) -> dict[str, Any]:
        """Compara as cotações atuais de vários ativos.

        Observação: preços em moedas diferentes não são diretamente comparáveis;
        a comparação apenas reúne as cotações obtidas, sem ranquear.
        """
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(",") if s.strip()]

        quotes: list[dict[str, Any]] = []
        not_found: list[dict[str, Any]] = []
        for symbol in symbols:
            result = self.get_stock_quote(symbol)
            if result.get("found"):
                quotes.append(result)
            else:
                not_found.append({"symbol": symbol, "error": result.get("error")})

        return {
            "symbols": list(symbols),
            "quotes": quotes,
            "not_found": not_found,
            "source": self.source,
        }


# --- Integração com o LangChain ---------------------------------------------

_TOOL_DESCRIPTIONS = {
    "get_stock_quote": (
        "Obtém a cotação mais recente de um ativo (ex.: 'PETR4.SA'). "
        "Retorna preço, moeda, data e fonte. Use SEMPRE que a pergunta depender "
        "do preço atual de um ativo. Nunca invente o valor."
    ),
    "get_stock_history": (
        "Obtém o histórico de preços de um ativo entre duas datas (formato "
        "ISO YYYY-MM-DD). Retorna barras com data e fechamento."
    ),
    "calculate_return": (
        "Calcula o retorno percentual de um ativo entre duas datas (ISO). "
        "Retorna preço inicial, final, retorno absoluto e percentual."
    ),
    "compare_stocks": (
        "Compara as cotações atuais de vários ativos. Recebe uma lista de "
        "símbolos e retorna as cotações encontradas."
    ),
}


def build_market_tools(provider: MarketDataProvider) -> list:
    """Constrói a lista de ferramentas do LangChain ligadas a ``provider``.

    As ferramentas retornam JSON (string) com dados estruturados, para que o
    modelo trabalhe com fatos verificáveis e não invente valores.
    """
    from langchain_core.tools import StructuredTool

    toolset = FinancialToolset(provider)

    def _dumps(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False)

    def get_stock_quote(symbol: str) -> str:
        return _dumps(toolset.get_stock_quote(symbol))

    def get_stock_history(symbol: str, start_date: str, end_date: str) -> str:
        return _dumps(toolset.get_stock_history(symbol, start_date, end_date))

    def calculate_return(symbol: str, start_date: str, end_date: str) -> str:
        return _dumps(toolset.calculate_return(symbol, start_date, end_date))

    def compare_stocks(symbols: list[str]) -> str:
        return _dumps(toolset.compare_stocks(symbols))

    return [
        StructuredTool.from_function(
            func=get_stock_quote,
            name="get_stock_quote",
            description=_TOOL_DESCRIPTIONS["get_stock_quote"],
        ),
        StructuredTool.from_function(
            func=get_stock_history,
            name="get_stock_history",
            description=_TOOL_DESCRIPTIONS["get_stock_history"],
        ),
        StructuredTool.from_function(
            func=calculate_return,
            name="calculate_return",
            description=_TOOL_DESCRIPTIONS["calculate_return"],
        ),
        StructuredTool.from_function(
            func=compare_stocks,
            name="compare_stocks",
            description=_TOOL_DESCRIPTIONS["compare_stocks"],
        ),
    ]
