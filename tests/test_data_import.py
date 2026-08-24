"""Testes do pipeline de importação (offline; sem chamadas externas)."""

from __future__ import annotations

from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from app.data_import import CSVImporter, ExcelImporter  # noqa: E402
from app.models.benchmark import BenchmarkDataset, validate_dataset  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REAL_XLSX = ROOT / "data" / "imports" / "dataset_experimental_agente_financeiro.xlsx"


# --- Fixture: planilha mínima com dados reais (para testar o caminho com dados) ---

def _build_fixture_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def add_sheet(name, header, rows):
        ws = wb.create_sheet(name)
        ws.append([f"Título {name}"])  # linha 0
        ws.append([])                   # linha 1 (branco)
        ws.append(header)               # linha 2 (cabeçalho)
        for r in rows:
            ws.append(r)

    add_sheet("Ativos", ["Ticker", "Nome/Descrição", "Tipo", "Segmento", "Benchmark",
                          "Usar no Experimento?", "Fonte Preferencial", "Observações"],
              [["PETR4", "Petrobras", "Ação", "Energia", "IBOV", "Sim", "Brapi", ""]])
    add_sheet("Dados_Mercado", ["Snapshot_ID", "Ticker", "Tipo", "Data", "Abertura", "Máxima",
                                "Mínima", "Fechamento", "Volume", "Dividendos", "Moeda",
                                "Fonte_URL", "Data_Coleta", "Validado", "Observações"],
              [["snap_test", "PETR4", "stock", "2024-01-02", 35.0, 36.0, 34.5, 36.0, 1000000,
                0.0, "BRL", "https://brapi.dev", "2024-01-03", "Sim", ""]])
    add_sheet("Dados_FII_CVM", ["Snapshot_ID", "Ticker", "Data_Referência", "Patrimônio_Líquido",
                                "Nº_Cotistas", "Qtd_Cotas", "Valor_Patrimonial_por_Cota",
                                "Rendimento_por_Cota", "Segmento", "Fonte_URL", "Data_Coleta",
                                "Validado", "Documento_Origem", "Observações"], [])
    add_sheet("Perguntas", ["ID", "Categoria", "Dificuldade", "Classe_Ativo", "Ticker_1",
                            "Data_Inicial", "Data_Final", "Snapshot_ID", "Pergunta_Final",
                            "Tipo_Resposta", "Gabarito_Automático", "Unidade", "Tolerância",
                            "Ferramenta_Esperada", "Métricas", "Status"],
              [["Q001", "calculation", "Média", "stock", "PETR4", "2024-01-02", "2024-06-03",
                "snap_test", "Qual o retorno da PETR4?", "percentage", 5.0, "%", 0.1,
                "calculate_return", "factual_precision", "Validado"]])
    add_sheet("Fontes", ["ID_Fonte", "Nome", "Tipo de Dado", "URL", "Uso na Pesquisa",
                         "Data_Verificação", "Observações"],
              [["SRC001", "Brapi", "OHLCV", "https://brapi.dev", "Cotações", "2026-08-24", ""]])
    wb.save(path)


@pytest.fixture()
def fixture_xlsx(tmp_path) -> Path:
    path = tmp_path / "fixture.xlsx"
    _build_fixture_xlsx(path)
    return path


# --- Caminho COM dados -------------------------------------------------------

def test_excel_market_records_with_provenance(fixture_xlsx) -> None:
    importer = ExcelImporter(fixture_xlsx, dataset_version="fix-v1")
    records = importer.import_market_data()
    assert len(records) == 1
    rec = records[0]
    assert rec.ticker == "PETR4" and rec.close == 36.0 and rec.date == "2024-01-02"
    assert rec.provenance.source_url == "https://brapi.dev"
    assert rec.provenance.dataset_version == "fix-v1"
    assert rec.snapshot_id == "snap_test"


def test_excel_question_with_reference(fixture_xlsx) -> None:
    importer = ExcelImporter(fixture_xlsx)
    questions, errors = importer.import_questions()
    assert not errors
    q = questions[0]
    assert q.id == "Q001"
    assert q.category.value == "calculation"
    assert q.difficulty.value == "medium"
    assert q.expected_answer.value == 5.0
    assert q.expected_tool == "calculate_return"
    assert q.status.value == "validated"


def test_csv_importer(tmp_path) -> None:
    csv_path = tmp_path / "m.csv"
    csv_path.write_text(
        "ticker,date,open,high,low,close,volume\nVALE3,2024-01-02,78,79,77,78.5,500\n",
        encoding="utf-8",
    )
    records = CSVImporter(csv_path).import_market_data()
    assert len(records) == 1
    assert records[0].ticker == "VALE3" and records[0].close == 78.5


# --- Caminho SEM dados (planilha real: rascunhos, sem fabricação) ------------

@pytest.mark.skipif(not REAL_XLSX.exists(), reason="planilha real não presente")
def test_real_excel_is_draft_without_fabrication() -> None:
    bundle = ExcelImporter(REAL_XLSX, dataset_version="excel-v1").import_all()
    assert len(bundle.questions) == 30
    assert len(bundle.assets) == 12  # 5 ações + 5 FIIs + 2 índices
    assert len(bundle.sources) == 4
    # Dados reais ainda não coletados -> nada fabricado.
    assert len(bundle.market_records) == 0
    assert all(q.expected_answer.value is None for q in bundle.questions)

    dataset = BenchmarkDataset(dataset_version="excel-v1", questions=bundle.questions)
    assert dataset.category_counts() == {
        "factual": 6, "calculation": 6, "comparison": 6, "interpretation": 6, "tool_use": 6,
    }
    assert dataset.difficulty_counts() == {"easy": 10, "medium": 10, "hard": 10}
    assert validate_dataset(dataset).ok  # estrutura básica válida (rascunho)
