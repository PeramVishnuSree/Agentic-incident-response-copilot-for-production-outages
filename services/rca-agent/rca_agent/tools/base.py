"""Shared read-only tool definition (kept separate to avoid circular imports)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadOnlyTool:
    name: str
    description: str
    run: Callable[..., object]
    writes: bool = False  # invariant: must stay False for every RCA tool
