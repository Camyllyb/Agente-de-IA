"""Gera ``questions.json`` computando as respostas de referência a partir dos
snapshots sintéticos.

Isso garante que ``expected_answer`` seja **consistente** com os dados
fornecidos ao agente (mesma fonte snapshot). Regenerar:

    python experiments/datasets/build_questions.py

⚠️  Como o conjunto 'default' de snapshots é sintético, este dataset é adequado
apenas para testar o pipeline. Para uso científico, gere snapshots reais e
recompute as respostas de referência.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.tools.financial_tools import FinancialToolset
from app.tools.market_data import SnapshotMarketDataProvider

OUT = Path(__file__).resolve().parent / "questions.json"

toolset = FinancialToolset(SnapshotMarketDataProvider(snapshot_set="default"))


def _ret(symbol: str, start: str, end: str) -> float:
    r = toolset.calculate_return(symbol, start, end)
    return round(r["return_pct"], 2)


def _price(symbol: str) -> float:
    return round(toolset.get_stock_quote(symbol)["price"], 2)


def _max_symbol(symbols: list[str]) -> str:
    quotes = toolset.compare_stocks(symbols)["quotes"]
    return max(quotes, key=lambda q: q["price"])["symbol"]


def _direction(symbol: str, start: str, end: str) -> tuple[str, list[str]]:
    hist = toolset.get_stock_history(symbol, start, end)["bars"]
    first, last = hist[0]["close"], hist[-1]["close"]
    if last > first:
        return "alta", ["alta", "subiu", "aumentou", "valorizou"]
    if last < first:
        return "baixa", ["baixa", "caiu", "queda", "recuou", "desvalorizou"]
    return "estável", ["estável", "estabilidade"]


def build() -> list[dict]:
    questions: list[dict] = []

    def add_return(qid, symbol, start, end):
        questions.append({
            "id": qid,
            "category": "return_calculation",
            "question": f"Qual foi o retorno percentual da {symbol} entre {start} e {end}?",
            "params": {"symbol": symbol, "start_date": start, "end_date": end},
            "expected_tools": ["calculate_return", "get_stock_history"],
            "expected_answer": {
                "type": "numeric",
                "unit": "percent",
                "value": _ret(symbol, start, end),
                "tolerance": 0.1,
            },
        })

    def add_quote(qid, symbol):
        questions.append({
            "id": qid,
            "category": "factual_quote",
            "question": f"Qual é a cotação mais recente disponível da {symbol}?",
            "params": {"symbol": symbol},
            "expected_tools": ["get_stock_quote"],
            "expected_answer": {
                "type": "numeric",
                "unit": "currency",
                "value": _price(symbol),
                "tolerance": 0.01,
            },
        })

    def add_compare(qid, symbols):
        questions.append({
            "id": qid,
            "category": "comparison",
            "question": (
                "Considerando a cotação mais recente, qual dos ativos a seguir tem "
                f"o maior preço: {', '.join(symbols)}?"
            ),
            "params": {"symbols": symbols},
            "expected_tools": ["compare_stocks"],
            "expected_answer": {
                "type": "categorical",
                "value": _max_symbol(symbols),
                "accept": [_max_symbol(symbols), _max_symbol(symbols).split(".")[0]],
            },
        })

    def add_trend(qid, symbol, start, end):
        value, accept = _direction(symbol, start, end)
        questions.append({
            "id": qid,
            "category": "trend_analysis",
            "question": (
                f"Com base nos fechamentos entre {start} e {end}, a tendência de "
                f"preço da {symbol} foi de alta ou de baixa?"
            ),
            "params": {"symbol": symbol, "start_date": start, "end_date": end},
            "expected_tools": ["get_stock_history"],
            "expected_answer": {"type": "categorical", "value": value, "accept": accept},
        })

    def add_interpretation(qid, symbol, start, end):
        questions.append({
            "id": qid,
            "category": "interpretation",
            "question": (
                f"Com base nos dados de {symbol} entre {start} e {end}, descreva "
                "de forma concisa o comportamento do preço no período."
            ),
            "params": {"symbol": symbol, "start_date": start, "end_date": end},
            "expected_tools": ["get_stock_history"],
            "expected_answer": {"type": "qualitative"},
        })

    # return_calculation (8)
    add_return("Q001", "PETR4.SA", "2024-01-02", "2024-06-03")
    add_return("Q002", "VALE3.SA", "2024-01-02", "2024-06-03")
    add_return("Q003", "ITUB4.SA", "2024-01-02", "2024-06-03")
    add_return("Q004", "AAPL", "2024-01-02", "2024-07-01")
    add_return("Q005", "PETR4.SA", "2024-01-02", "2024-04-01")
    add_return("Q006", "VALE3.SA", "2024-03-01", "2024-07-01")
    add_return("Q007", "AAPL", "2024-04-01", "2024-07-01")
    add_return("Q008", "ITUB4.SA", "2024-02-01", "2024-06-03")
    # factual_quote (4)
    add_quote("Q009", "PETR4.SA")
    add_quote("Q010", "VALE3.SA")
    add_quote("Q011", "AAPL")
    add_quote("Q012", "ITUB4.SA")
    # comparison (3)
    add_compare("Q013", ["PETR4.SA", "VALE3.SA"])
    add_compare("Q014", ["ITUB4.SA", "PETR4.SA"])
    add_compare("Q015", ["PETR4.SA", "VALE3.SA", "ITUB4.SA"])
    # trend_analysis (3)
    add_trend("Q016", "AAPL", "2024-04-01", "2024-07-01")
    add_trend("Q017", "VALE3.SA", "2024-01-02", "2024-04-01")
    add_trend("Q018", "PETR4.SA", "2024-01-02", "2024-07-01")
    # interpretation (2)
    add_interpretation("Q019", "PETR4.SA", "2024-01-02", "2024-06-03")
    add_interpretation("Q020", "AAPL", "2024-01-02", "2024-07-01")

    return questions


if __name__ == "__main__":
    data = {
        "dataset_version": "v1",
        "snapshot_set": "default",
        "note": (
            "Respostas de referência computadas a partir do snapshot SINTÉTICO "
            "'default'. Uso apenas para teste de pipeline."
        ),
        "questions": build(),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Gerado {OUT} com {len(data['questions'])} questões.")
    cats: dict[str, int] = {}
    for q in data["questions"]:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    for c, n in sorted(cats.items()):
        print(f"  {c}: {n}")
