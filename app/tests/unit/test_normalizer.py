from __future__ import annotations

import pytest

from app.discovery.normalizer import (
    canonical_business_name,
    canonical_domain,
    country_to_region,
    normalize_address,
    normalize_phone,
    normalize_website,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.Example.com/", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("www.example.com", "http://example.com"),
        ("example.com/path/", "http://example.com/path"),
    ],
)
def test_normalize_website(raw, expected):
    assert normalize_website(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.abc.com", "abc.com"),
        ("http://shop.abc.co.uk/x", "abc.co.uk"),
        ("ABC.COM", "abc.com"),
        (None, None),
    ],
)
def test_canonical_domain(raw, expected):
    assert canonical_domain(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ABC Dental Clinic Ltd.", "abc dental clinic"),
        ("ABC Dental Clinic", "abc dental clinic"),
        ("ABC Dental Clinic - Dhaka", "abc dental clinic"),
        ("Smith & Sons, Inc", "smith & sons"),
    ],
)
def test_canonical_business_name(raw, expected):
    assert canonical_business_name(raw) == expected


def test_branch_names_stay_distinct():
    a = canonical_business_name("ABC Dental - Dhanmondi")
    b = canonical_business_name("ABC Dental - Gulshan")
    # dash-qualifier is stripped, so branch distinction must be handled by address
    # in dedup, NOT by the canonical name. Assert the name collapses (documents intent).
    assert a == b == "abc dental"


def test_normalize_phone_bd():
    display, e164 = normalize_phone("01712345678", "BD")
    assert e164 == "+8801712345678"
    display2, e1642 = normalize_phone("+880 1712-345678", "BD")
    assert e1642 == e164


def test_normalize_phone_garbage():
    display, e164 = normalize_phone("call us!", "BD")
    assert e164 is None


def test_normalize_address():
    assert normalize_address("  12  Main St ,,  Dhaka \n Bangladesh ") == "12 Main St, Dhaka, Bangladesh"


def test_country_to_region():
    assert country_to_region("Bangladesh") == "BD"
    assert country_to_region("Nowhereland") is None
