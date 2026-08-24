"""Extração de valores da resposta do agente (para métricas automáticas)."""

from __future__ import annotations

import re

_FINAL_RE = re.compile(r"\s*resposta final\s*:?\s*(.*)", re.IGNORECASE)
_TICKER_RE = re.compile(r"[A-Za-z]{1,6}\d{0,2}\.[A-Za-z]{1,4}")
_NUM_RE = re.compile(r"-?\d[\d.,]*")


def final_answer_line(text: str) -> str:
    """Retorna o conteúdo após 'Resposta final:'. Se ausente, o texto todo."""
    if not text:
        return ""
    for line in text.splitlines():
        match = _FINAL_RE.match(line)
        if match:
            return match.group(1).strip()
    return text.strip()


def _to_float(token: str) -> float | None:
    token = token.strip().rstrip(".,")
    if not any(ch.isdigit() for ch in token):
        return None
    has_dot, has_comma = "." in token, "," in token
    if has_dot and has_comma:
        # O último separador é o decimal.
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif has_comma:
        token = token.replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def extract_number(text: str) -> float | None:
    """Extrai o primeiro número da string, ignorando tickers (ex.: PETR4.SA).

    Aceita formatos com ponto ou vírgula decimal. Retorna ``None`` se não houver
    número — nunca inventa um valor.
    """
    if not text:
        return None
    cleaned = _TICKER_RE.sub(" ", text)
    for token in _NUM_RE.findall(cleaned):
        value = _to_float(token)
        if value is not None:
            return value
    return None
