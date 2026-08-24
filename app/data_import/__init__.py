"""Pipeline de importação de dados reais (desacoplado do benchmark)."""

from app.data_import.base import MarketDataImporter
from app.data_import.csv_importer import CSVImporter
from app.data_import.excel_importer import ExcelImporter
from app.data_import.models import (
    Asset,
    FIIRecord,
    ImportBundle,
    MarketRecord,
    Provenance,
    SourceRef,
)
from app.data_import.remote_importers import BrapiImporter, CVMFIIImporter

__all__ = [
    "MarketDataImporter",
    "ExcelImporter",
    "CSVImporter",
    "BrapiImporter",
    "CVMFIIImporter",
    "MarketRecord",
    "FIIRecord",
    "Asset",
    "SourceRef",
    "Provenance",
    "ImportBundle",
]
