"""Testes das estratégias de prompting.

Verificam a regra experimental fundamental: as três estratégias recebem a mesma
questão, não alteram os dados financeiros e diferem APENAS na característica da
técnica. Também verificam o versionamento dos prompts.
"""

from __future__ import annotations

import pytest

from app.prompts import (
    ChainOfThoughtStrategy,
    FewShotStrategy,
    UnknownStrategyError,
    ZeroShotStrategy,
    available_strategies,
    get_prompt_strategy,
)
from app.prompts.shared import RESPONSE_FORMAT, SHARED_CONSTRAINTS

QUESTION = "Qual foi a variação da PETR4.SA entre 2024-01-02 e 2024-06-03?"
CONTEXT = (
    "PETR4.SA: fechamento 36,00 BRL (2024-01-02) e 37,80 BRL (2024-06-03), "
    "fonte snapshot:default."
)

ALL_NAMES = ["zero_shot", "few_shot", "chain_of_thought"]


# --- Registro ----------------------------------------------------------------

def test_registry_returns_correct_types() -> None:
    assert isinstance(get_prompt_strategy("zero_shot"), ZeroShotStrategy)
    assert isinstance(get_prompt_strategy("few_shot"), FewShotStrategy)
    assert isinstance(get_prompt_strategy("chain_of_thought"), ChainOfThoughtStrategy)


def test_available_strategies() -> None:
    assert set(available_strategies()) == set(ALL_NAMES)


def test_unknown_strategy_raises() -> None:
    with pytest.raises(UnknownStrategyError):
        get_prompt_strategy("nao_existe")


def test_strategy_name_case_insensitive() -> None:
    assert get_prompt_strategy("ZERO_SHOT").name == "zero_shot"


# --- Versionamento -----------------------------------------------------------

def test_prompt_versions() -> None:
    assert get_prompt_strategy("zero_shot").prompt_version == "zero_shot_v1"
    assert get_prompt_strategy("few_shot").prompt_version == "few_shot_v1"
    assert get_prompt_strategy("chain_of_thought").prompt_version == "chain_of_thought_v1"


# --- Invariância experimental ------------------------------------------------

def test_all_strategies_same_task_message() -> None:
    """A mesma questão e o mesmo contexto produzem a MESMA mensagem de tarefa."""
    task_messages = {
        get_prompt_strategy(name).build_task_message(QUESTION, CONTEXT)
        for name in ALL_NAMES
    }
    assert len(task_messages) == 1  # todas idênticas


def test_financial_context_unchanged_in_all() -> None:
    """Nenhuma estratégia altera os dados financeiros fornecidos."""
    for name in ALL_NAMES:
        strategy = get_prompt_strategy(name)
        task = strategy.build_task_message(QUESTION, CONTEXT)
        assert CONTEXT in task  # inserido verbatim


def test_all_share_constraints_and_format() -> None:
    """Restrições e formato de resposta são idênticos em todas as estratégias."""
    for name in ALL_NAMES:
        system = get_prompt_strategy(name).build_system_prompt()
        assert SHARED_CONSTRAINTS.strip() in system
        assert RESPONSE_FORMAT.strip() in system


# --- Cada estratégia implementa apenas sua característica --------------------

def test_zero_shot_has_no_examples_and_no_reasoning_block() -> None:
    system = ZeroShotStrategy().build_system_prompt()
    assert "Exemplos ilustrativos" not in system
    assert "decomponha o problema" not in system


def test_few_shot_has_examples_only() -> None:
    system = FewShotStrategy().build_system_prompt()
    assert "Exemplos ilustrativos" in system
    assert "decomponha o problema" not in system


def test_chain_of_thought_has_reasoning_only() -> None:
    system = ChainOfThoughtStrategy().build_system_prompt()
    assert "decomponha o problema" in system
    assert "Exemplos ilustrativos" not in system


def test_only_technique_block_differs() -> None:
    """Removendo o bloco de técnica, os prompts de sistema coincidem."""
    zero = ZeroShotStrategy().build_system_prompt()
    few = FewShotStrategy().build_system_prompt()
    cot = ChainOfThoughtStrategy().build_system_prompt()

    # zero-shot é o "esqueleto" compartilhado (sem bloco de técnica).
    # few-shot = esqueleto + exemplos; cot = esqueleto + raciocínio.
    assert FewShotStrategy().few_shot_examples().strip() in few
    assert ChainOfThoughtStrategy().technique_instructions().strip() in cot
    # O esqueleto (constraints + formato) está presente nos três.
    for system in (zero, few, cot):
        assert SHARED_CONSTRAINTS.strip() in system
        assert RESPONSE_FORMAT.strip() in system


def test_build_messages_structure() -> None:
    messages = ZeroShotStrategy().build_messages(QUESTION, CONTEXT)
    assert len(messages) == 2
    assert messages[0].type == "system"
    assert messages[1].type == "human"
    assert QUESTION in messages[1].content
