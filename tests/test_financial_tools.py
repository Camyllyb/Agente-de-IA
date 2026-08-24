"""Testes das ferramentas financeiras (offline, via snapshots).

Não dependem da bolsa estar aberta nem de internet — usam o conjunto de snapshots
sintético `default`.
"""

from __future__ import annotations

import pytest

from app.tools.financial_tools import FinancialToolset, build_market_tools
from app.tools.market_data import SnapshotMarketDataProvider
from app.tools.market_data.base import DataNotFoundError, SymbolNotFoundError


@pytest.fixture()
def provider() -> SnapshotMarketDataProvider:
    return SnapshotMarketDataProvider(snapshot_set="default")


@pytest.fixture()
def toolset(provider: SnapshotMarketDataProvider) -> FinancialToolset:
    return FinancialToolset(provider)


# --- Provider de snapshot ----------------------------------------------------

def test_available_symbols(provider: SnapshotMarketDataProvider) -> None:
    symbols = provider.available_symbols()
    assert "PETR4.SA" in symbols
    assert "AAPL" in symbols


def test_get_quote(provider: SnapshotMarketDataProvider) -> None:
    quote = provider.get_quote("PETR4.SA")
    assert quote.symbol == "PETR4.SA"
    assert quote.currency == "BRL"
    assert quote.source == "snapshot:default"
    assert quote.price == 41.0


def test_get_history_filters_by_range(provider: SnapshotMarketDataProvider) -> None:
    history = provider.get_history("PETR4.SA", "2024-01-01", "2024-03-31")
    dates = [bar.date for bar in history.bars]
    assert dates == ["2024-01-02", "2024-02-01", "2024-03-01"]


def test_get_history_symbol_not_found(provider: SnapshotMarketDataProvider) -> None:
    with pytest.raises(SymbolNotFoundError):
        provider.get_history("ZZZZ.SA", "2024-01-01", "2024-12-31")


def test_get_history_no_data_in_range(provider: SnapshotMarketDataProvider) -> None:
    with pytest.raises(DataNotFoundError):
        provider.get_history("PETR4.SA", "2020-01-01", "2020-12-31")


# --- FinancialToolset --------------------------------------------------------

def test_toolset_quote_identifies_all_fields(toolset: FinancialToolset) -> None:
    result = toolset.get_stock_quote("PETR4.SA")
    assert result["found"] is True
    # Toda resposta identifica: ativo, valor, moeda, data, fonte.
    for field in ("symbol", "price", "currency", "date", "source"):
        assert field in result
    assert result["source"] == "snapshot:default"


def test_toolset_quote_not_found_does_not_invent(toolset: FinancialToolset) -> None:
    result = toolset.get_stock_quote("INVALIDO.SA")
    assert result["found"] is False
    assert "error" in result
    assert "price" not in result  # nunca inventa valor


def test_toolset_calculate_return(toolset: FinancialToolset) -> None:
    # PETR4.SA: 36.00 -> 37.80 => +5.0%
    result = toolset.calculate_return("PETR4.SA", "2024-01-02", "2024-06-03")
    assert result["found"] is True
    assert result["start_price"] == 36.0
    assert result["end_price"] == 37.8
    assert result["return_pct"] == pytest.approx(5.0, abs=1e-6)
    assert result["currency"] == "BRL"


def test_toolset_calculate_return_not_found(toolset: FinancialToolset) -> None:
    result = toolset.calculate_return("PETR4.SA", "2020-01-01", "2020-02-01")
    assert result["found"] is False
    assert "return_pct" not in result


def test_toolset_compare_stocks(toolset: FinancialToolset) -> None:
    result = toolset.compare_stocks(["PETR4.SA", "VALE3.SA", "INVALIDO.SA"])
    found_symbols = {q["symbol"] for q in result["quotes"]}
    assert found_symbols == {"PETR4.SA", "VALE3.SA"}
    assert result["not_found"][0]["symbol"] == "INVALIDO.SA"


def test_toolset_history_structure(toolset: FinancialToolset) -> None:
    result = toolset.get_stock_history("AAPL", "2024-01-01", "2024-07-31")
    assert result["found"] is True
    assert result["currency"] == "USD"
    assert result["count"] == len(result["bars"])
    assert result["bars"][0]["close"] == 185.0


# --- Ferramentas LangChain ---------------------------------------------------

def test_build_market_tools_names(provider: SnapshotMarketDataProvider) -> None:
    tools = build_market_tools(provider)
    names = {t.name for t in tools}
    assert names == {
        "get_stock_quote",
        "get_stock_history",
        "calculate_return",
        "compare_stocks",
    }


def test_langchain_tool_invoke_returns_json(provider: SnapshotMarketDataProvider) -> None:
    import json

    tools = {t.name: t for t in build_market_tools(provider)}
    raw = tools["get_stock_quote"].invoke({"symbol": "PETR4.SA"})
    payload = json.loads(raw)
    assert payload["found"] is True
    assert payload["symbol"] == "PETR4.SA"
