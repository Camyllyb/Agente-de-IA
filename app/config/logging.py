"""Configuração centralizada de logging.

Fornece :func:`setup_logging` (idempotente) e :func:`get_logger`, usados por toda
a aplicação para produzir logs consistentes.
"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_configured = False


def setup_logging(level: str | None = None) -> None:
    """Configura o logging raiz uma única vez.

    Args:
        level: Nível de log (ex.: "INFO", "DEBUG"). Se ``None``, usa o valor
            definido em :class:`~app.config.settings.Settings`.
    """
    global _configured
    if _configured and level is None:
        return

    # Import local para evitar dependência circular na inicialização.
    from app.config.settings import get_settings

    resolved = (level or get_settings().log_level).upper()
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(resolved)
    # Evita handlers duplicados em recargas (ex.: testes, reload do uvicorn).
    root.handlers = [handler]
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger nomeado, garantindo que o logging esteja configurado."""
    if not _configured:
        setup_logging()
    return logging.getLogger(name)
