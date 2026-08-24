"""Importadores remotos (Brapi, CVM). Fazem chamadas de rede — NÃO usados nos
testes automatizados. As dependências e a rede são acessadas de forma lazy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.data_import.base import MarketDataImporter
from app.data_import.models import FIIRecord, MarketRecord, Provenance


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrapiImporter(MarketDataImporter):
    """Importa cotações históricas via API pública da Brapi (brapi.dev).

    Requer rede e, possivelmente, token. Não é chamado nos testes.
    """

    source_name = "brapi"
    BASE_URL = "https://brapi.dev/api/quote"

    def __init__(self, tickers: list[str], range_: str = "3mo", interval: str = "1d",
                 token: str | None = None, dataset_version: str = "brapi-import"):
        self.tickers = tickers
        self.range = range_
        self.interval = interval
        self.token = token
        self.dataset_version = dataset_version

    def import_market_data(self) -> list[MarketRecord]:  # pragma: no cover - requer rede
        import httpx

        records: list[MarketRecord] = []
        collected = _now_iso()
        for ticker in self.tickers:
            params = {"range": self.range, "interval": self.interval, "fundamental": "false"}
            if self.token:
                params["token"] = self.token
            url = f"{self.BASE_URL}/{ticker}"
            response = httpx.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            payload = response.json()
            for result in payload.get("results", []):
                for bar in result.get("historicalDataPrice", []) or []:
                    ts = bar.get("date")
                    day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat() if ts else None
                    if not day:
                        continue
                    records.append(MarketRecord(
                        ticker=ticker,
                        date=day,
                        open=bar.get("open"),
                        high=bar.get("high"),
                        low=bar.get("low"),
                        close=bar.get("close"),
                        volume=bar.get("volume"),
                        currency=result.get("currency", "BRL"),
                        provenance=Provenance(
                            source_name=self.source_name,
                            source_url=url,
                            collection_datetime=collected,
                            original_date=day,
                            dataset_version=self.dataset_version,
                        ),
                    ))
        return records


class CVMFIIImporter(MarketDataImporter):
    """Importa dados periódicos de FIIs a partir de arquivos da CVM.

    Requer download/rede. Não é chamado nos testes. Aceita, alternativamente, um
    caminho local já baixado (para reprodutibilidade).
    """

    source_name = "cvm"

    def __init__(self, local_path: str | None = None, dataset_version: str = "cvm-import"):
        self.local_path = local_path
        self.dataset_version = dataset_version

    def import_market_data(self) -> list[MarketRecord]:
        return []  # a CVM fornece dados periódicos de FII, não OHLCV

    def import_fii_data(self) -> list[FIIRecord]:  # pragma: no cover - requer arquivo/rede
        if not self.local_path:
            raise NotImplementedError(
                "Forneça um arquivo local da CVM (informe mensal) para importar FIIs "
                "de forma reprodutível, ou implemente o download explicitamente."
            )
        import pandas as pd

        df = pd.read_csv(self.local_path, sep=";", encoding="latin-1")
        records: list[FIIRecord] = []
        collected = _now_iso()
        for _, row in df.iterrows():
            records.append(FIIRecord(
                ticker=str(row.get("Ticker", "")),
                reference_date=str(row.get("Data_Referencia", "")),
                net_worth=row.get("Patrimonio_Liquido"),
                num_shareholders=row.get("Num_Cotistas"),
                num_shares=row.get("Qtd_Cotas"),
                provenance=Provenance(
                    source_name=self.source_name,
                    source_url=self.local_path,
                    collection_datetime=collected,
                    dataset_version=self.dataset_version,
                ),
            ))
        return records
