"""Fonte de dados financeiros ao vivo (yfinance).

Consulta dados reais de mercado. Import lazy de ``yfinance`` — a biblioteca só é
necessária quando esta fonte é efetivamente utilizada (os testes usam snapshots).
"""

from __future__ import annotations

from datetime import date, timedelta

from app.config.logging import get_logger
from app.models.market import HistoryBar, Quote, StockHistory
from app.tools.market_data.base import (
    DataNotFoundError,
    MarketDataError,
    MarketDataProvider,
    SymbolNotFoundError,
)

logger = get_logger(__name__)


def _infer_currency(symbol: str) -> str:
    """Heurística simples de moeda a partir do sufixo do ticker."""
    suffix_map = {".SA": "BRL", ".L": "GBP", ".TO": "CAD", ".DE": "EUR", ".PA": "EUR"}
    for suffix, currency in suffix_map.items():
        if symbol.upper().endswith(suffix):
            return currency
    return "USD"


class LiveMarketDataProvider(MarketDataProvider):
    """Provedor de dados reais via yfinance."""

    source_name = "live:yfinance"

    def _yfinance(self):
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - depende de instalação
            raise MarketDataError(
                "A fonte 'live' requer o pacote 'yfinance'. Instale com: "
                "pip install yfinance"
            ) from exc
        return yf

    def _currency_for(self, ticker, symbol: str) -> str:
        try:
            fast = getattr(ticker, "fast_info", None)
            if fast:
                currency = fast.get("currency") if hasattr(fast, "get") else getattr(fast, "currency", None)
                if currency:
                    return str(currency)
        except Exception:  # pragma: no cover - fast_info pode falhar
            logger.debug("fast_info indisponível para %s; usando heurística.", symbol)
        return _infer_currency(symbol)

    def get_quote(self, symbol: str) -> Quote:  # pragma: no cover - requer rede
        yf = self._yfinance()
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="5d")
        if history is None or history.empty:
            raise SymbolNotFoundError(symbol, self.source_name)

        last = history.iloc[-1]
        last_index = history.index[-1]
        quote_date = last_index.date().isoformat()
        return Quote(
            symbol=symbol,
            price=round(float(last["Close"]), 4),
            currency=self._currency_for(ticker, symbol),
            date=quote_date,
            timestamp=last_index.isoformat(),
            source=self.source_name,
        )

    def get_history(  # pragma: no cover - requer rede
        self, symbol: str, start_date: str, end_date: str
    ) -> StockHistory:
        yf = self._yfinance()
        ticker = yf.Ticker(symbol)
        # yfinance trata 'end' como exclusivo; somamos 1 dia para incluí-lo.
        inclusive_end = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
        history = ticker.history(start=start_date, end=inclusive_end)
        if history is None or history.empty:
            raise DataNotFoundError(
                symbol, f"nenhum dado entre {start_date} e {end_date}", self.source_name
            )

        bars = [
            HistoryBar(
                date=idx.date().isoformat(),
                open=round(float(row["Open"]), 4),
                high=round(float(row["High"]), 4),
                low=round(float(row["Low"]), 4),
                close=round(float(row["Close"]), 4),
                volume=int(row["Volume"]) if not _is_nan(row["Volume"]) else None,
            )
            for idx, row in history.iterrows()
        ]
        return StockHistory(
            symbol=symbol,
            currency=self._currency_for(ticker, symbol),
            source=self.source_name,
            start_date=start_date,
            end_date=end_date,
            bars=bars,
        )


def _is_nan(value) -> bool:  # pragma: no cover - utilitário trivial
    try:
        return value != value
    except Exception:
        return False
