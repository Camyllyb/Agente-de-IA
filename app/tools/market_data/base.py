"""Interface de fonte de dados financeiros.

:class:`MarketDataProvider` desacopla o agente e as ferramentas da origem dos
dados. Trocar de fonte (ao vivo ↔ snapshot) não exige alterar o agente.

Quando um dado não existe, os provedores **levantam exceções explícitas** — nunca
inventam valores. As ferramentas de alto nível (``app.tools.financial_tools``)
convertem essas exceções em respostas estruturadas de "não encontrado".
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.market import Quote, StockHistory


class MarketDataError(Exception):
    """Erro base de dados de mercado."""


class SymbolNotFoundError(MarketDataError):
    """O ativo solicitado não existe na fonte."""

    def __init__(self, symbol: str, source: str):
        self.symbol = symbol
        self.source = source
        super().__init__(f"Ativo '{symbol}' não encontrado na fonte '{source}'.")


class DataNotFoundError(MarketDataError):
    """O ativo existe, mas não há dados para o período/instante solicitado."""

    def __init__(self, symbol: str, detail: str, source: str):
        self.symbol = symbol
        self.detail = detail
        self.source = source
        super().__init__(
            f"Sem dados para '{symbol}' ({detail}) na fonte '{source}'."
        )


class MarketDataProvider(ABC):
    """Interface comum para fontes de dados financeiros."""

    #: Identificador da fonte (ex.: 'snapshot:default', 'live:yfinance').
    source_name: str = "base"

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Retorna a cotação mais recente disponível para ``symbol``.

        Raises:
            SymbolNotFoundError: se o ativo não existir na fonte.
            DataNotFoundError: se não houver cotação disponível.
        """
        raise NotImplementedError

    @abstractmethod
    def get_history(self, symbol: str, start_date: str, end_date: str) -> StockHistory:
        """Retorna o histórico de ``symbol`` no intervalo [start_date, end_date].

        Datas no formato ISO (YYYY-MM-DD), inclusivas.

        Raises:
            SymbolNotFoundError: se o ativo não existir na fonte.
            DataNotFoundError: se não houver dados no período.
        """
        raise NotImplementedError
