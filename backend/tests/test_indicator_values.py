from types import SimpleNamespace

import pytest

from app.services.indicator_values import (
    IndicatorValueError,
    normalize_indicator_value,
    normalize_ocr_indicator_value,
    parse_numeric_value,
)


def _numeric_definition(unit):
    return SimpleNamespace(value_type="numeric", unit=unit)


def test_ambiguous_decimal_comma_is_never_silently_converted():
    definition = _numeric_definition("mmol/L")

    assert parse_numeric_value("5,6 mmol/L") is None
    with pytest.raises(IndicatorValueError, match="comma is ambiguous"):
        normalize_indicator_value(definition, "5,6 mmol/L")


@pytest.mark.parametrize("raw_value", ["389 μmol/L", "389 µmol/L", "389 umol/L"])
def test_micro_unit_spellings_are_equivalent(raw_value):
    definition = _numeric_definition("μmol/L")

    assert normalize_ocr_indicator_value(definition, raw_value) == "389"


@pytest.mark.parametrize(
    "raw_value",
    ["6.8 mmol·L-1", "6.8 mmol⋅L−1"],
)
def test_per_litre_exponent_unit_is_normalized(raw_value):
    definition = _numeric_definition("mmol/L")

    assert normalize_ocr_indicator_value(definition, raw_value) == "6.8"


def test_unmarked_multiple_numbers_still_require_manual_correction():
    definition = _numeric_definition("mmol/L")

    with pytest.raises(IndicatorValueError, match="one number"):
        normalize_ocr_indicator_value(definition, "5.6 / 6.1")
