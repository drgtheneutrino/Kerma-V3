"""Notebook cell dataclass."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CellKind(str, Enum):
    MATH   = "math"
    PYTHON = "python"
    TEXT   = "text"


@dataclass
class Cell:
    kind: CellKind
    source: str = ""
    # runtime-only (not serialized):
    id:          str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    output:      Optional[str] = None          # formatted numeric result
    latex:       Optional[str] = None          # rendered-math string
    error:       Optional[str] = None          # traceback/short error
    value:       Any = None                    # last evaluated Python value

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "source": self.source}

    @classmethod
    def from_dict(cls, d: dict) -> "Cell":
        return cls(kind=CellKind(d.get("kind", "python")), source=d.get("source", ""))
