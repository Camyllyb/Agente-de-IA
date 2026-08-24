"""Geração e validação de gabaritos (respostas de referência).

Os gabaritos objetivos são calculados de forma determinística usando SOMENTE
snapshots congelados. Nada é digitado à mão nem fabricado: se faltarem dados no
snapshot, a referência fica ``missing_data`` (valor nulo).

Cada referência registra auditoria: snapshot_id, fórmula, registros de origem,
timestamp de geração e versão do gerador.

CLI:
    python -m experiments.references validate   # audita gabaritos vs snapshot
    python -m experiments.references generate    # gera gabaritos para o dataset
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.models.benchmark import BenchmarkQuestion, QuestionCategory
from app.snapshots import SnapshotManager, SnapshotStatus
from app.snapshots.errors import SnapshotError
from app.tools.financial_tools import FinancialToolset
from app.tools.market_data.base import MarketDataError

GENERATOR_VERSION = "refgen_v1"


@dataclass
class ReferenceResult:
    question_id: str
    category: str
    status: str  # generated | missing_data | not_applicable
    expected_answer: dict | None = None
    reference_audit: dict | None = None
    required_facts: list[str] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    notes: str = ""


class ReferenceAnswerGenerator:
    """Gera respostas de referência a partir de um snapshot CONGELADO."""

    def __init__(self, snapshot_manager: SnapshotManager, snapshot_id: str, now: str | None = None):
        self.snapshot_id = snapshot_id
        meta = snapshot_manager.read_metadata(snapshot_id)
        if meta.status != SnapshotStatus.frozen:
            raise SnapshotError(
                f"Gabaritos só podem ser gerados de snapshot CONGELADO; "
                f"'{snapshot_id}' está '{meta.status.value}'."
            )
        self.provider = snapshot_manager.build_provider(snapshot_id)
        self.toolset = FinancialToolset(self.provider)
        self._now = now or datetime.now(timezone.utc).isoformat()

    def _audit(self, formula: str, source_records: list[dict]) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "formula": formula,
            "source_records": source_records,
            "generated_at": self._now,
            "generator_version": GENERATOR_VERSION,
        }

    def _close_on(self, ticker: str, day: str) -> tuple[float, dict]:
        hist = self.toolset.get_stock_history(ticker, day, day)
        if not hist.get("found") or not hist.get("bars"):
            raise MarketDataError(f"sem fechamento de {ticker} em {day}")
        bar = hist["bars"][0]
        return float(bar["close"]), bar

    # --- por categoria ------------------------------------------------------
    def generate_for(self, q: BenchmarkQuestion) -> ReferenceResult:
        category = q.category
        try:
            if category == QuestionCategory.factual:
                return self._factual(q)
            if category == QuestionCategory.calculation:
                return self._calculation(q)
            if category == QuestionCategory.comparison:
                return self._comparison(q)
            if category == QuestionCategory.interpretation:
                return self._interpretation(q)
            if category == QuestionCategory.tool_use:
                return self._tool_use(q)
        except MarketDataError as exc:
            return ReferenceResult(q.id, category.value, "missing_data", notes=str(exc))
        return ReferenceResult(q.id, category.value, "not_applicable")

    def _require(self, q: BenchmarkQuestion, need_dates: bool = True) -> tuple[str, str, str]:
        if not q.tickers:
            raise MarketDataError("questão sem tickers")
        if need_dates and (not q.start_date or not q.end_date):
            raise MarketDataError("questão sem datas")
        return q.tickers[0], q.start_date, q.end_date

    def _factual(self, q: BenchmarkQuestion) -> ReferenceResult:
        if not q.tickers:
            raise MarketDataError("questão sem tickers")
        day = q.end_date or q.start_date
        if not day:
            raise MarketDataError("questão factual sem data")
        ticker = q.tickers[0]
        close, bar = self._close_on(ticker, day)
        ea = {"type": q.expected_answer.type or "numeric", "value": close,
              "unit": q.expected_answer.unit, "tolerance": q.expected_answer.tolerance}
        return ReferenceResult(
            q.id, "factual", "generated", ea,
            self._audit(f"close({ticker}, {day})", [bar]),
        )

    def _calculation(self, q: BenchmarkQuestion) -> ReferenceResult:
        ticker, start, end = self._require(q)
        r = self.toolset.calculate_return(ticker, start, end)
        if not r.get("found"):
            raise MarketDataError(r.get("error", "sem dados para o retorno"))
        ea = {"type": q.expected_answer.type or "percentage", "value": r["return_pct"],
              "unit": q.expected_answer.unit or "%", "tolerance": q.expected_answer.tolerance}
        audit = self._audit(
            "retorno(%) = ((preco_final - preco_inicial) / preco_inicial) * 100",
            [{"start_price": r["start_price"], "start_date": r["start_observed_date"],
              "end_price": r["end_price"], "end_date": r["end_observed_date"]}],
        )
        return ReferenceResult(q.id, "calculation", "generated", ea, audit)

    def _comparison(self, q: BenchmarkQuestion) -> ReferenceResult:
        if len(q.tickers) < 2 or not q.start_date or not q.end_date:
            raise MarketDataError("comparação exige ≥2 tickers e datas")
        returns = {}
        sources = []
        for ticker in q.tickers:
            r = self.toolset.calculate_return(ticker, q.start_date, q.end_date)
            if not r.get("found"):
                raise MarketDataError(f"sem dados para {ticker}")
            returns[ticker] = r["return_pct"]
            sources.append({"ticker": ticker, "return_pct": r["return_pct"]})
        best = max(returns, key=returns.get)
        worst = min(returns, key=returns.get)
        diff = round(returns[best] - returns[worst], 6)
        if (q.expected_answer.type or "").lower() in ("percentage", "numeric", "currency"):
            ea = {"type": q.expected_answer.type, "value": diff, "unit": "%",
                  "tolerance": q.expected_answer.tolerance}
        else:
            ea = {"type": "categorical", "value": best, "accept": [best, best.split(".")[0]]}
        audit = self._audit("retorno por ativo; melhor/pior/diferença", sources)
        audit["best"] = best
        audit["worst"] = worst
        audit["diff_pp"] = diff
        return ReferenceResult(q.id, "comparison", "generated", ea, audit)

    def _interpretation(self, q: BenchmarkQuestion) -> ReferenceResult:
        ticker, start, end = self._require(q)
        hist = self.toolset.get_stock_history(ticker, start, end)
        if not hist.get("found"):
            raise MarketDataError("sem histórico para interpretação")
        bars = hist["bars"]
        first, last = bars[0]["close"], bars[-1]["close"]
        direction = "alta" if last > first else "baixa" if last < first else "estável"
        required_facts = [
            f"fechamento inicial de {ticker} = {first} em {bars[0]['date']}",
            f"fechamento final de {ticker} = {last} em {bars[-1]['date']}",
            f"tendência de {direction} no período",
        ]
        audit = self._audit("interpretação baseada nos fechamentos do período",
                            [bars[0], bars[-1]])
        # Interpretação não tem valor numérico único.
        ea = {"type": "rubric", "value": None, "unit": None, "tolerance": None}
        return ReferenceResult(
            q.id, "interpretation", "generated", ea, audit,
            required_facts=required_facts,
            forbidden_claims=list(q.forbidden_claims),
        )

    def _tool_use(self, q: BenchmarkQuestion) -> ReferenceResult:
        expected_tool = q.expected_tool or "get_stock_history"
        ticker, start, end = self._require(q, need_dates=False)
        params = {"symbol": ticker}
        if q.start_date and q.end_date:
            params.update({"start_date": q.start_date, "end_date": q.end_date})
        # Executa a ferramenta esperada para registrar o dado esperado.
        expected_data = None
        if expected_tool == "get_stock_quote":
            expected_data = self.toolset.get_stock_quote(ticker)
        elif expected_tool == "calculate_return" and q.start_date and q.end_date:
            expected_data = self.toolset.calculate_return(ticker, q.start_date, q.end_date)
        elif expected_tool == "get_stock_history" and q.start_date and q.end_date:
            expected_data = self.toolset.get_stock_history(ticker, q.start_date, q.end_date)
        elif expected_tool == "compare_stocks":
            expected_data = self.toolset.compare_stocks(q.tickers)
        audit = self._audit(f"ferramenta esperada={expected_tool}", [])
        audit.update({"expected_tool": expected_tool, "expected_params": params,
                      "expected_data": expected_data})
        ea = {"type": "tool_use", "value": None}
        return ReferenceResult(q.id, "tool_use", "generated", ea, audit)

    def generate_all(self, questions: list[BenchmarkQuestion]) -> list[ReferenceResult]:
        return [self.generate_for(q) for q in questions]


# --- Versionamento / persistência -------------------------------------------

def save_references(results: list[ReferenceResult], path: str | Path, overwrite: bool = False) -> None:
    """Salva as referências. Não sobrescreve um arquivo validado sem nova versão."""
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} já existe. Gere uma nova versão (novo dataset_version) em vez "
            "de sobrescrever um gabarito validado."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generator_version": GENERATOR_VERSION, "references": [asdict(r) for r in results]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# --- CLI --------------------------------------------------------------------

def _load_benchmark(dataset_path: str):
    from experiments.datasets.benchmark_loader import load_benchmark_dataset

    return load_benchmark_dataset(dataset_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gabaritos determinísticos de snapshots congelados.")
    parser.add_argument("command", choices=["validate", "generate"])
    parser.add_argument("--dataset", default="experiments/datasets/benchmark_v2.json")
    parser.add_argument("--snapshot-id", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    manager = SnapshotManager()
    frozen = [m for m in manager.list_snapshots() if m.status == SnapshotStatus.frozen]
    if not frozen:
        print("Nenhum snapshot CONGELADO disponível. Não é possível gerar/validar "
              "gabaritos (não fabricamos valores). Congele um snapshot primeiro.")
        return 1

    snapshot_id = args.snapshot_id or frozen[-1].snapshot_id
    dataset = _load_benchmark(args.dataset)
    generator = ReferenceAnswerGenerator(manager, snapshot_id)
    results = generator.generate_all(dataset.questions)

    generated = [r for r in results if r.status == "generated"]
    missing = [r for r in results if r.status == "missing_data"]
    print(f"Snapshot: {snapshot_id} | questões: {len(results)} | "
          f"geradas: {len(generated)} | sem dados: {len(missing)}")
    for r in missing[:30]:
        print(f"  - {r.question_id} ({r.category}): {r.notes}")

    if args.command == "generate":
        out = args.out or f"experiments/datasets/references/{dataset.dataset_version}/references.json"
        try:
            save_references(results, out)
            print(f"Referências salvas em {out}")
        except FileExistsError as exc:
            print(str(exc))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
