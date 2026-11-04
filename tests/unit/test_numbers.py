from __future__ import annotations

import pytest

from irobot.domain.numbers import to_float


@pytest.mark.parametrize("value, expected", [("1.5", 1.5), (3, 3.0), (2.5, 2.5)])
def test_to_float_converts(value, expected):
    assert to_float(value) == expected


@pytest.mark.parametrize("value", [None, "abc", [], {}])
def test_to_float_invalid_returns_default(value):
    assert to_float(value) is None
    assert to_float(value, 7.0) == 7.0


@pytest.mark.parametrize("value", ["nan", "inf", float("-inf")])
def test_to_float_finiteness_only_when_required(value):
    assert to_float(value, 1.0) != 1.0
    assert to_float(value, 1.0, require_finite=True) == 1.0
    assert to_float(value, require_finite=True) is None
