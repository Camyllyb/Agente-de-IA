"""Gera o conjunto de snapshots 'default' com dados SINTÉTICOS.

⚠️  Os valores produzidos aqui são **fictícios e determinísticos**, destinados
exclusivamente a testar o *pipeline* (testes automatizados e experimento offline).
Eles **não representam** cotações reais de mercado.

Para experimentos científicos com dados reais, gere snapshots a partir da fonte
ao vivo (ver ``LiveMarketDataProvider``) e versione o conjunto correspondente.

Uso:
    python data/snapshots/build_default_snapshots.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "default"

DATES = [
    "2024-01-02",
    "2024-02-01",
    "2024-03-01",
    "2024-04-01",
    "2024-05-02",
    "2024-06-03",
    "2024-07-01",
]

# Fechamentos SINTÉTICOS por ativo (não são valores reais de mercado).
CLOSES: dict[str, dict[str, object]] = {
    "PETR4.SA": {"currency": "BRL", "closes": [36.00, 40.50, 38.00, 42.00, 39.60, 37.80, 41.00]},
    "VALE3.SA": {"currency": "BRL", "closes": [78.00, 72.00, 68.00, 62.00, 66.00, 64.00, 70.00]},
    "ITUB4.SA": {"currency": "BRL", "closes": [33.00, 34.50, 33.75, 35.00, 36.00, 34.20, 35.50]},
    "AAPL": {"currency": "USD", "closes": [185.00, 186.00, 179.00, 170.00, 173.00, 194.00, 210.00]},
}

NOTE = (
    "Dados SINTÉTICOS para teste de pipeline — não representam valores reais de "
    "mercado."
)


def _bar(prev_close: float, close: float, date: str, index: int) -> dict:
    open_price = round(prev_close, 2)
    high = round(max(open_price, close) * 1.01, 2)
    low = round(min(open_price, close) * 0.99, 2)
    volume = 1_000_000 + index * 50_000
    return {
        "date": date,
        "open": open_price,
        "high": high,
        "low": low,
        "close": round(close, 2),
        "volume": volume,
    }


def build() -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for symbol, spec in CLOSES.items():
        closes = spec["closes"]  # type: ignore[index]
        currency = spec["currency"]  # type: ignore[index]
        history = []
        prev = closes[0]
        for i, (date, close) in enumerate(zip(DATES, closes)):
            history.append(_bar(prev, close, date, i))
            prev = close
        last_date = DATES[-1]
        payload = {
            "symbol": symbol,
            "currency": currency,
            "as_of": last_date,
            "note": NOTE,
            "quote": {
                "price": round(closes[-1], 2),
                "date": last_date,
                "timestamp": f"{last_date}T21:00:00Z",
            },
            "history": history,
        }
        path = OUT_DIR / f"{symbol}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    paths = build()
    print(f"Gerados {len(paths)} snapshots sintéticos em {OUT_DIR}:")
    for p in paths:
        print(f"  - {p.name}")
