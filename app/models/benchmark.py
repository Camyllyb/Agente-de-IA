"""Schema do benchmark científico definitivo (30 questões).

Suporta o novo formato de questão (com dificuldade, classe de ativo, tickers,
snapshot, ferramenta esperada, fatos obrigatórios/proibidos e métricas de
avaliação) e traz validações rigorosas para o congelamento do dataset.

Regra científica: os gabaritos NÃO são fabricados aqui. Questões podem existir
como rascunho (``status = "draft"``) sem valores de referência; as validações
estritas (exigir gabarito/métricas) só se aplicam ao congelar (``strict=True``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tools.registry import is_valid_tool


class QuestionCategory(str, Enum):
    factual = "factual"
    calculation = "calculation"
    comparison = "comparison"
    interpretation = "interpretation"
    tool_use = "tool_use"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class AssetClass(str, Enum):
    stock = "stock"
    fii = "fii"
    index = "index"
    unknown = "unknown"


class QuestionStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    frozen = "frozen"


# Normalização de rótulos vindos da planilha (pt-BR) para os valores canônicos.
_DIFFICULTY_ALIASES = {
    "facil": "easy", "fácil": "easy", "easy": "easy",
    "media": "medium", "média": "medium", "medio": "medium", "médio": "medium", "medium": "medium",
    "dificil": "hard", "difícil": "hard", "hard": "hard",
}
_CATEGORY_ALIASES = {
    "factual": "factual", "fato": "factual", "factual_quote": "factual",
    "calculation": "calculation", "calculo": "calculation", "cálculo": "calculation",
    "return_calculation": "calculation",
    "comparison": "comparison", "comparacao": "comparison", "comparação": "comparison",
    "interpretation": "interpretation", "interpretacao": "interpretation", "interpretação": "interpretation",
    "trend_analysis": "interpretation",
    "tool_use": "tool_use", "uso_de_ferramentas": "tool_use", "ferramentas": "tool_use",
}

# Categorias/dificuldade alvo do benchmark definitivo.
TARGET_PER_CATEGORY = 6
TARGET_PER_DIFFICULTY = 10
TARGET_TOTAL = 30


class ExpectedAnswer(BaseModel):
    """Resposta de referência (pode estar vazia em rascunho)."""

    model_config = ConfigDict(extra="allow")

    type: str = "qualitative"
    value: float | str | None = None
    unit: str | None = None
    tolerance: float | None = None
    # Para interpretação/rubrica:
    acceptable_facts: list[str] = Field(default_factory=list)

    @field_validator("tolerance")
    @classmethod
    def _non_negative_tolerance(cls, v):
        if v is not None and v < 0:
            raise ValueError("tolerance não pode ser negativa.")
        return v


class ReferenceAudit(BaseModel):
    """Auditoria de um gabarito gerado deterministicamente (ver PROMPT 16)."""

    model_config = ConfigDict(extra="allow")

    snapshot_id: str | None = None
    formula: str | None = None
    source_records: list[dict] = Field(default_factory=list)
    generated_at: str | None = None
    generator_version: str | None = None


class BenchmarkQuestion(BaseModel):
    """Questão do benchmark científico."""

    model_config = ConfigDict(extra="allow")

    id: str
    category: QuestionCategory
    difficulty: Difficulty
    asset_class: AssetClass = AssetClass.unknown
    tickers: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    snapshot_id: str | None = None
    question: str | None = None
    expected_answer: ExpectedAnswer = Field(default_factory=ExpectedAnswer)
    expected_tool: str | None = None
    required_facts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    evaluation_metrics: list[str] = Field(default_factory=list)
    status: QuestionStatus = QuestionStatus.draft
    # Proveniência / auditoria
    dataset_version: str | None = None
    source: str | None = None
    reference_audit: ReferenceAudit | None = None

    @field_validator("difficulty", mode="before")
    @classmethod
    def _normalize_difficulty(cls, v):
        if isinstance(v, str):
            return _DIFFICULTY_ALIASES.get(v.strip().lower(), v.strip().lower())
        return v

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, v):
        if isinstance(v, str):
            return _CATEGORY_ALIASES.get(v.strip().lower(), v.strip().lower())
        return v

    @field_validator("expected_tool")
    @classmethod
    def _valid_tool(cls, v):
        if not is_valid_tool(v):
            raise ValueError(f"expected_tool inválido: {v!r}")
        return v

    # Observação: a consistência de datas é verificada em ``validate_dataset``
    # (não na construção), para permitir importar rascunhos e sinalizar o
    # problema em vez de falhar de imediato.

    def to_runner_dict(self) -> dict:
        """Adapta a questão para o formato consumido pelo ExperimentRunner antigo."""
        params: dict = {}
        if self.tickers:
            params["symbol"] = self.tickers[0]
            params["symbols"] = list(self.tickers)
        if self.start_date:
            params["start_date"] = self.start_date
        if self.end_date:
            params["end_date"] = self.end_date

        type_map = {"percentage": "numeric", "currency": "numeric", "numeric": "numeric",
                    "categorical": "categorical", "rubric": "qualitative", "qualitative": "qualitative"}
        ea = self.expected_answer
        expected_answer = {
            "type": type_map.get(ea.type, ea.type),
            "value": ea.value,
            "unit": ea.unit,
            "tolerance": ea.tolerance,
        }
        return {
            "id": self.id,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "question": self.question or "",
            "params": params,
            "expected_tools": [self.expected_tool] if self.expected_tool and self.expected_tool != "none" else [],
            "expected_answer": expected_answer,
            "required_facts": self.required_facts,
            "forbidden_claims": self.forbidden_claims,
        }


class BenchmarkDataset(BaseModel):
    """Conjunto de questões do benchmark, com metadados."""

    model_config = ConfigDict(extra="allow")

    dataset_version: str
    schema_version: str = "v2"
    snapshot_id: str | None = None
    source: str | None = None
    frozen: bool = False
    note: str | None = None
    questions: list[BenchmarkQuestion] = Field(default_factory=list)

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for q in self.questions:
            counts[q.category.value] = counts.get(q.category.value, 0) + 1
        return counts

    def difficulty_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for q in self.questions:
            counts[q.difficulty.value] = counts.get(q.difficulty.value, 0) + 1
        return counts


@dataclass
class DatasetValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def _requires_reference(q: BenchmarkQuestion) -> bool:
    """Questões objetivas exigem gabarito ao congelar."""
    return q.category in (QuestionCategory.factual, QuestionCategory.calculation, QuestionCategory.comparison) \
        and q.expected_answer.type not in ("rubric", "qualitative")


def validate_dataset(
    dataset: BenchmarkDataset,
    known_snapshots: set[str] | None = None,
    strict: bool = False,
    enforce_distribution: bool = False,
) -> DatasetValidationResult:
    """Valida o dataset.

    Sempre verifica: IDs únicos, categoria/dificuldade válidas, datas
    consistentes, tolerância não negativa, ferramenta esperada existente.

    Com ``strict=True`` (congelamento) também exige: métricas de avaliação e
    gabarito para questões objetivas.

    Com ``enforce_distribution=True`` exige 30 questões, 6 por categoria e 10 por
    dificuldade.
    """
    result = DatasetValidationResult(ok=True)
    known_snapshots = known_snapshots or set()

    seen_ids: set[str] = set()
    for q in dataset.questions:
        if q.id in seen_ids:
            result.add_error(f"ID duplicado: {q.id}")
        seen_ids.add(q.id)

        # datas
        for label, value in (("start_date", q.start_date), ("end_date", q.end_date)):
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError:
                    result.add_error(f"{q.id}: {label} inválida ({value!r})")
        if q.start_date and q.end_date:
            try:
                if date.fromisoformat(q.start_date) > date.fromisoformat(q.end_date):
                    result.add_error(f"{q.id}: start_date > end_date")
            except ValueError:
                pass

        # tolerância
        if q.expected_answer.tolerance is not None and q.expected_answer.tolerance < 0:
            result.add_error(f"{q.id}: tolerância negativa")

        # ferramenta
        if not is_valid_tool(q.expected_tool):
            result.add_error(f"{q.id}: expected_tool inexistente ({q.expected_tool!r})")

        # snapshot referenciado
        if q.snapshot_id and known_snapshots and q.snapshot_id not in known_snapshots:
            result.add_error(f"{q.id}: snapshot inexistente ({q.snapshot_id})")

        # verificações estritas (congelamento)
        if strict:
            if not q.evaluation_metrics:
                result.add_error(f"{q.id}: sem métrica de avaliação")
            if not (q.question or "").strip():
                result.add_error(f"{q.id}: sem texto de pergunta")
            if _requires_reference(q) and q.expected_answer.value is None:
                result.add_error(f"{q.id}: questão objetiva sem gabarito (dataset congelado)")

    if enforce_distribution:
        if len(dataset.questions) != TARGET_TOTAL:
            result.add_error(f"Total de questões = {len(dataset.questions)} (esperado {TARGET_TOTAL})")
        for cat, n in dataset.category_counts().items():
            if n != TARGET_PER_CATEGORY:
                result.add_error(f"Categoria '{cat}' com {n} questões (esperado {TARGET_PER_CATEGORY})")
        for diff, n in dataset.difficulty_counts().items():
            if n != TARGET_PER_DIFFICULTY:
                result.add_error(f"Dificuldade '{diff}' com {n} questões (esperado {TARGET_PER_DIFFICULTY})")

    return result
