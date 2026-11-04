from __future__ import annotations

import math
from typing import Any, overload


@overload
def to_float(value: Any, default: float, *, require_finite: bool = False) -> float: ...


@overload
def to_float(value: Any, default: None = None, *, require_finite: bool = False) -> float | None: ...


def to_float(value: Any, default: float | None = None, *, require_finite: bool = False) -> float | None:
    """Convertit en float ; renvoie `default` si la conversion échoue (ou si non fini et `require_finite`)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if require_finite and not math.isfinite(number):
        return default
    return number
