"""Métricas científicas.

Separa métricas AUTOMÁTICAS (precisão factual, tokens, latência, custo, taxa de
sucesso, acurácia de ferramenta) da avaliação HUMANA (cega) e do LLM-as-a-judge
(opcional, sempre identificado como IA).
"""

from app.metrics.aggregate import (
    build_scored_records,
    factual_accuracy,
    success_rate,
    to_dataframe,
    tool_accuracy,
    tool_correct,
)
from app.metrics.agentic import (
    data_grounding_accuracy,
    task_success_rate,
    tool_execution_success_rate,
    tool_selection_accuracy,
)
from app.metrics.answer_parsing import extract_number, final_answer_line
from app.metrics.factual import FactualScore, score_answer
from app.metrics.human_eval import (
    CRITERIA,
    RUBRIC,
    generate_blind_evaluation,
    import_blind_evaluation,
    rubric_markdown,
)
from app.metrics.llm_judge import judge_answer
from app.metrics.pricing import PriceTable, load_price_table
from app.metrics.agreement import (
    cohen_kappa,
    krippendorff_alpha,
    pairwise_kappa_matrix,
    weighted_kappa,
)
from app.metrics.human_eval_final import (
    CRITERIA_FINAL,
    compute_agreement,
    generate_final_blind_evaluation,
    import_final_blind_evaluation,
)

__all__ = [
    # factual / parsing
    "FactualScore",
    "score_answer",
    "extract_number",
    "final_answer_line",
    # aggregate
    "build_scored_records",
    "success_rate",
    "factual_accuracy",
    "tool_accuracy",
    "tool_correct",
    "to_dataframe",
    # pricing
    "PriceTable",
    "load_price_table",
    # human eval
    "CRITERIA",
    "RUBRIC",
    "rubric_markdown",
    "generate_blind_evaluation",
    "import_blind_evaluation",
    # llm judge
    "judge_answer",
]
