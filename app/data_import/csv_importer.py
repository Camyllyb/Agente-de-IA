"""Importador de dados de mercado a partir de CSV."""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

from app.data_import.base import MarketDataImporter
from app.data_import.models import MarketRecord, Provenance


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c for c in text.lower() if c.isalnum())


def _num(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


class CSVImporter(MarketDataImporter):
    """Importa OHLCV de um CSV com cabeçalho (ticker, date, open, high, low, close, volume)."""

    source_name = "csv"

    def __init__(self, path: str | Path, dataset_version: str = "csv-import", currency: str = "BRL"):
        self.path = Path(path)
        self.dataset_version = dataset_version
        self.currency = currency

    def import_market_data(self) -> list[MarketRecord]:
        records: list[MarketRecord] = []
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            colmap = {_norm(c): c for c in (reader.fieldnames or [])}

            def col(row, *keys):
                for key in keys:
                    actual = colmap.get(_norm(key))
                    if actual:
                        return row.get(actual)
                return None

            for row in reader:
                ticker = col(row, "ticker", "symbol")
                date_v = col(row, "date", "data")
                if not ticker or not date_v:
                    continue
                records.append(MarketRecord(
                    ticker=str(ticker).strip(),
                    date=str(date_v).strip(),
                    asset_type=col(row, "type", "tipo"),
                    open=_num(col(row, "open", "abertura")),
                    high=_num(col(row, "high", "maxima")),
                    low=_num(col(row, "low", "minima")),
                    close=_num(col(row, "close", "fechamento")),
                    volume=_num(col(row, "volume")),
                    dividends=_num(col(row, "dividends", "dividendos")),
                    currency=str(col(row, "currency", "moeda") or self.currency),
                    provenance=Provenance(
                        source_name=self.source_name,
                        source_url=str(self.path),
                        original_date=str(date_v).strip(),
                        dataset_version=self.dataset_version,
                    ),
                ))
        return records
