"""Exceções do SnapshotManager."""

from __future__ import annotations


class SnapshotError(Exception):
    """Erro base de snapshots."""


class SnapshotNotFoundError(SnapshotError):
    """Snapshot solicitado não existe."""


class SnapshotFrozenError(SnapshotError):
    """Tentativa de alterar um snapshot já congelado."""


class SnapshotIntegrityError(SnapshotError):
    """O checksum não confere: o snapshot foi alterado após o congelamento."""
