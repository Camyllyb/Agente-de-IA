"""Snapshots científicos congelados."""

from app.snapshots.errors import (
    SnapshotError,
    SnapshotFrozenError,
    SnapshotIntegrityError,
    SnapshotNotFoundError,
)
from app.snapshots.manager import SnapshotManager, SnapshotValidation
from app.snapshots.metadata import SnapshotMetadata, SnapshotStatus
from app.snapshots.provider import FrozenSnapshotDataProvider

__all__ = [
    "SnapshotManager",
    "SnapshotValidation",
    "SnapshotMetadata",
    "SnapshotStatus",
    "FrozenSnapshotDataProvider",
    "SnapshotError",
    "SnapshotNotFoundError",
    "SnapshotFrozenError",
    "SnapshotIntegrityError",
]
