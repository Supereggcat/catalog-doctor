from __future__ import annotations

import pytest

from catalog_doctor.taxonomy import (
    CATEGORIES,
    CATEGORY_MAP,
    convert,
    format_number,
    parse_measurement,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("180mm", (180.0, "mm")),
        ("18 cm", (18.0, "cm")),
        (" 1.8m ", (1.8, "m")),
        ("500克", (500.0, "克")),
        ("32", (32.0, None)),
    ],
)
def test_parse_measurement(raw, expected):
    assert parse_measurement(raw) == expected


@pytest.mark.parametrize("raw", ["", "待定", "约32左右", None, "abc"])
def test_parse_measurement_rejects_noise(raw):
    parsed = parse_measurement(raw)
    assert parsed is None or parsed[1] is not None


@pytest.mark.parametrize(
    ("value", "source", "target", "expected"),
    [
        (1, "kg", "g", 1000),
        (1000, "g", "kg", 1),
        (1, "m", "cm", 100),
        (10, "mm", "cm", 1),
        (1, "L", "ml", 1000),
    ],
)
def test_convert_within_family(value, source, target, expected):
    assert convert(value, source, target) == pytest.approx(expected)


def test_convert_across_families_returns_none():
    assert convert(1, "kg", "ml") is None


def test_format_number_trims_noise():
    assert format_number(12.0) == "12"
    assert format_number(1.23456) == "1.235"


def test_every_category_has_required_attributes_and_price_band():
    assert len(CATEGORIES) == 6
    for category in CATEGORIES:
        assert category.required_keys, category.category_id
        assert category.price_floor < category.price_ceiling
        assert category.category_id in CATEGORY_MAP


def test_enum_attributes_expose_alias_vocabulary():
    for category in CATEGORIES:
        for attr in category.attributes:
            if attr.dtype == "enum":
                assert attr.enum_values, f"{category.category_id}.{attr.key} 缺少标准词表"
                assert attr.aliases, f"{category.category_id}.{attr.key} 缺少别名映射"

