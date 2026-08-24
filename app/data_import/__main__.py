"""CLI de importação da planilha experimental.

Uso:
    python -m app.data_import --excel data/imports/dataset_experimental_agente_financeiro.xlsx

Gera o dataset de benchmark (rascunho, sem gabaritos fabricados) e persiste os
dados brutos importados (ativos, mercado, FII, fontes) com proveniência.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.data_import.excel_importer import ExcelImporter
from app.models.benchmark import BenchmarkDataset, validate_dataset
from experiments.datasets.benchmark_loader import save_benchmark_dataset

_DEFAULT_EXCEL = "data/imports/dataset_experimental_agente_financeiro.xlsx"


def _dump(objs, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [o.model_dump() for o in objs]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Importa a planilha experimental.")
    parser.add_argument("--excel", default=_DEFAULT_EXCEL)
    parser.add_argument("--dataset-version", default="excel-v1")
    parser.add_argument("--out-dataset", default="experiments/datasets/benchmark_v2.json")
    parser.add_argument("--out-dir", default="data/imports/parsed")
    args = parser.parse_args(argv)

    importer = ExcelImporter(args.excel, dataset_version=args.dataset_version)
    bundle = importer.import_all()

    dataset = BenchmarkDataset(
        dataset_version=args.dataset_version,
        schema_version="v2",
        snapshot_id=None,
        source=f"excel:{Path(args.excel).name}",
        frozen=False,
        note=(
            "Rascunho importado da planilha. Gabaritos NÃO fabricados: valores "
            "ausentes permanecem nulos até a coleta e o congelamento dos dados."
        ),
        questions=bundle.questions,
    )
    save_benchmark_dataset(dataset, args.out_dataset)

    out_dir = Path(args.out_dir)
    _dump(bundle.assets, out_dir / "assets.json")
    _dump(bundle.market_records, out_dir / "market_records.json")
    _dump(bundle.fii_records, out_dir / "fii_records.json")
    _dump(bundle.sources, out_dir / "sources.json")

    print("Importação concluída:")
    for key, value in bundle.summary().items():
        print(f"  {key}: {value}")
    print(f"  dataset (v2): {args.out_dataset}")

    result = validate_dataset(dataset)
    print(f"  IDs únicos/estrutura básica: {'OK' if result.ok else 'ERROS'}")
    if bundle.errors:
        print("  Linhas com erro (registradas, não fabricadas):")
        for err in bundle.errors[:20]:
            print(f"    - {err}")

    # Verificação honesta do estado dos dados reais.
    filled = sum(1 for q in dataset.questions if (q.question or "").strip())
    with_gabarito = sum(1 for q in dataset.questions if q.expected_answer.value is not None)
    print(
        f"  Estado: {filled}/{len(dataset.questions)} questões com texto; "
        f"{with_gabarito}/{len(dataset.questions)} com gabarito; "
        f"{len(bundle.market_records)} registros de mercado."
    )
    if with_gabarito == 0 or len(bundle.market_records) == 0:
        print(
            "  >>> Dados reais ainda não coletados. Preencha a planilha (ou use os "
            "importadores Brapi/CVM) e congele um snapshot antes de gerar gabaritos."
        )


if __name__ == "__main__":
    main()
