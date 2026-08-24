"""Importador da planilha experimental (.xlsx).

Mapeia as abas: Ativos, Dados_Mercado, Dados_FII_CVM, Perguntas, Fontes.
Não altera silenciosamente valores da planilha e preserva a proveniência.
Valores ausentes permanecem ausentes (None) — nada é fabricado.
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from app.config.logging import get_logger
from app.data_import.base import MarketDataImporter
from app.data_import.models import (
    Asset,
    FIIRecord,
    ImportBundle,
    MarketRecord,
    Provenance,
    SourceRef,
)
from app.models.benchmark import BenchmarkQuestion, ExpectedAnswer

logger = get_logger(__name__)

_SHEET_HEADER_ROW = 2  # título na linha 0, branco na 1, cabeçalho na 2


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c for c in text.lower() if c.isalnum())


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if pd.isna(value):
        return None
    return value


def _num(value) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def _iso(value) -> str | None:
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[: len(fmt) + 2], fmt).date().isoformat()
        except ValueError:
            continue
    return text  # preserva o valor original se não reconhecer o formato


def _split(value) -> list[str]:
    value = _clean(value)
    if value is None:
        return []
    parts: list[str] = []
    for chunk in str(value).replace("\n", ";").split(";"):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def _truthy(value) -> bool:
    value = _clean(value)
    return str(value).strip().lower() in {"sim", "true", "1", "x", "validado", "validada"}


_ASSET_CLASS = {"acao": "stock", "stock": "stock", "fii": "fii", "indice": "index", "index": "index"}
_STATUS = {"rascunho": "draft", "draft": "draft", "validado": "validated", "validada": "validated",
           "congelado": "frozen", "congelada": "frozen", "frozen": "frozen"}


class ExcelImporter(MarketDataImporter):
    """Importa a planilha experimental completa."""

    source_name = "excel"

    def __init__(self, path: str | Path, dataset_version: str = "excel-import"):
        self.path = Path(path)
        self.dataset_version = dataset_version

    # --- utilidades ---------------------------------------------------------
    def _read(self, sheet: str) -> tuple[pd.DataFrame, dict[str, str]]:
        df = pd.read_excel(self.path, sheet_name=sheet, header=_SHEET_HEADER_ROW)
        df = df.dropna(how="all")
        colmap = {_norm(c): c for c in df.columns}
        return df, colmap

    @staticmethod
    def _get(row, colmap, *keys):
        for key in keys:
            actual = colmap.get(_norm(key))
            if actual is not None and actual in row:
                return row[actual]
        return None

    # --- abas ---------------------------------------------------------------
    def import_assets(self) -> list[Asset]:
        df, cm = self._read("Ativos")
        assets: list[Asset] = []
        for _, row in df.iterrows():
            ticker = _clean(self._get(row, cm, "Ticker"))
            if not ticker:
                continue
            assets.append(Asset(
                ticker=str(ticker),
                name=_clean(self._get(row, cm, "Nome/Descrição", "NomeDescricao", "Nome")),
                asset_type=_clean(self._get(row, cm, "Tipo")),
                segment=_clean(self._get(row, cm, "Segmento")),
                benchmark=_clean(self._get(row, cm, "Benchmark")),
                use_in_experiment=_truthy(self._get(row, cm, "Usar no Experimento?", "UsarNoExperimento")),
                preferred_source=_clean(self._get(row, cm, "Fonte Preferencial", "FontePreferencial")),
                notes=_clean(self._get(row, cm, "Observações", "Observacoes")),
            ))
        return assets

    def import_sources(self) -> list[SourceRef]:
        df, cm = self._read("Fontes")
        sources: list[SourceRef] = []
        for _, row in df.iterrows():
            sid = _clean(self._get(row, cm, "ID_Fonte", "IDFonte"))
            name = _clean(self._get(row, cm, "Nome"))
            if not sid and not name:
                continue
            sources.append(SourceRef(
                id=str(sid) if sid else None,
                name=name,
                data_type=_clean(self._get(row, cm, "Tipo de Dado", "TipoDeDado")),
                url=_clean(self._get(row, cm, "URL")),
                usage=_clean(self._get(row, cm, "Uso na Pesquisa", "UsoNaPesquisa")),
                verified_at=_iso(self._get(row, cm, "Data_Verificação", "DataVerificacao")),
                notes=_clean(self._get(row, cm, "Observações", "Observacoes")),
            ))
        return sources

    def import_market_data(self) -> list[MarketRecord]:
        df, cm = self._read("Dados_Mercado")
        records: list[MarketRecord] = []
        for _, row in df.iterrows():
            ticker = _clean(self._get(row, cm, "Ticker"))
            date_v = _iso(self._get(row, cm, "Data"))
            if not ticker or not date_v:
                continue  # linha vazia do template
            records.append(MarketRecord(
                ticker=str(ticker),
                date=date_v,
                asset_type=_clean(self._get(row, cm, "Tipo")),
                open=_num(self._get(row, cm, "Abertura")),
                high=_num(self._get(row, cm, "Máxima", "Maxima")),
                low=_num(self._get(row, cm, "Mínima", "Minima")),
                close=_num(self._get(row, cm, "Fechamento")),
                volume=_num(self._get(row, cm, "Volume")),
                dividends=_num(self._get(row, cm, "Dividendos")),
                currency=str(_clean(self._get(row, cm, "Moeda")) or "BRL"),
                snapshot_id=_clean(self._get(row, cm, "Snapshot_ID", "SnapshotID")),
                validated=_truthy(self._get(row, cm, "Validado")),
                provenance=Provenance(
                    source_name=self.source_name,
                    source_url=_clean(self._get(row, cm, "Fonte_URL", "FonteURL")),
                    collection_datetime=_iso(self._get(row, cm, "Data_Coleta", "DataColeta")),
                    original_date=date_v,
                    dataset_version=self.dataset_version,
                ),
            ))
        return records

    def import_fii_data(self) -> list[FIIRecord]:
        df, cm = self._read("Dados_FII_CVM")
        records: list[FIIRecord] = []
        for _, row in df.iterrows():
            ticker = _clean(self._get(row, cm, "Ticker"))
            ref = _iso(self._get(row, cm, "Data_Referência", "DataReferencia"))
            if not ticker or not ref:
                continue
            records.append(FIIRecord(
                ticker=str(ticker),
                reference_date=ref,
                net_worth=_num(self._get(row, cm, "Patrimônio_Líquido", "PatrimonioLiquido")),
                num_shareholders=_int(self._get(row, cm, "Nº_Cotistas", "NoCotistas", "NCotistas")),
                num_shares=_num(self._get(row, cm, "Qtd_Cotas", "QtdCotas")),
                nav_per_share=_num(self._get(row, cm, "Valor_Patrimonial_por_Cota", "ValorPatrimonialporCota")),
                income_per_share=_num(self._get(row, cm, "Rendimento_por_Cota", "RendimentoporCota")),
                segment=_clean(self._get(row, cm, "Segmento")),
                snapshot_id=_clean(self._get(row, cm, "Snapshot_ID", "SnapshotID")),
                source_document=_clean(self._get(row, cm, "Documento_Origem", "DocumentoOrigem")),
                validated=_truthy(self._get(row, cm, "Validado")),
                provenance=Provenance(
                    source_name="cvm",
                    source_url=_clean(self._get(row, cm, "Fonte_URL", "FonteURL")),
                    collection_datetime=_iso(self._get(row, cm, "Data_Coleta", "DataColeta")),
                    original_date=ref,
                    dataset_version=self.dataset_version,
                ),
            ))
        return records

    def import_questions(self) -> tuple[list[BenchmarkQuestion], list[str]]:
        df, cm = self._read("Perguntas")
        questions: list[BenchmarkQuestion] = []
        errors: list[str] = []
        for _, row in df.iterrows():
            qid = _clean(self._get(row, cm, "ID"))
            if not qid:
                continue
            tickers = [str(t) for t in (
                _clean(self._get(row, cm, "Ticker_1", "Ticker1")),
                _clean(self._get(row, cm, "Ticker_2", "Ticker2")),
                _clean(self._get(row, cm, "Ticker_3", "Ticker3")),
            ) if t]
            asset_class_raw = _clean(self._get(row, cm, "Classe_Ativo", "ClasseAtivo"))
            asset_class = _ASSET_CLASS.get(_norm(asset_class_raw), "unknown") if asset_class_raw else "unknown"
            status_raw = _clean(self._get(row, cm, "Status"))
            status = _STATUS.get(_norm(status_raw), "draft") if status_raw else "draft"

            expected = ExpectedAnswer(
                type=str(_clean(self._get(row, cm, "Tipo_Resposta", "TipoResposta")) or "qualitative"),
                value=_num(self._get(row, cm, "Gabarito_Automático", "GabaritoAutomatico")),
                unit=_clean(self._get(row, cm, "Unidade")),
                tolerance=_num(self._get(row, cm, "Tolerância", "Tolerancia")),
            )
            try:
                question = BenchmarkQuestion(
                    id=str(qid),
                    category=str(_clean(self._get(row, cm, "Categoria"))),
                    difficulty=str(_clean(self._get(row, cm, "Dificuldade"))),
                    asset_class=asset_class,
                    tickers=tickers,
                    start_date=_iso(self._get(row, cm, "Data_Inicial", "DataInicial")),
                    end_date=_iso(self._get(row, cm, "Data_Final", "DataFinal")),
                    snapshot_id=_clean(self._get(row, cm, "Snapshot_ID", "SnapshotID")),
                    question=_clean(self._get(row, cm, "Pergunta_Final", "PerguntaFinal")),
                    expected_answer=expected,
                    expected_tool=_clean(self._get(row, cm, "Ferramenta_Esperada", "FerramentaEsperada")),
                    required_facts=_split(self._get(row, cm, "Fatos_Obrigatórios", "FatosObrigatorios")),
                    forbidden_claims=_split(self._get(row, cm, "Afirmações_Proibidas", "AfirmacoesProibidas")),
                    evaluation_metrics=_split(self._get(row, cm, "Métricas", "Metricas")),
                    status=status,
                    dataset_version=self.dataset_version,
                    source=f"excel:{self.path.name}",
                )
                questions.append(question)
            except Exception as exc:  # linha inconsistente: registra e continua
                errors.append(f"{qid}: {type(exc).__name__}: {exc}")
        return questions, errors

    def import_all(self) -> ImportBundle:
        questions, q_errors = self.import_questions()
        return ImportBundle(
            assets=self.import_assets(),
            market_records=self.import_market_data(),
            fii_records=self.import_fii_data(),
            questions=questions,
            sources=self.import_sources(),
            errors=q_errors,
            dataset_version=self.dataset_version,
        )
