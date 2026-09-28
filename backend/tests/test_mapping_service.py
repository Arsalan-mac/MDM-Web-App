"""Mapping/Transform Studio - pure-function pieces of app/cleansing/
mapping_service.py. The DB-backed CRUD/generate functions are exercised via
the live end-to-end flow instead, same convention as relation_service and
dataset_service (see docs/ROADMAP.md)."""

from app.cleansing.mapping_service import _parse_suggestions


def test_parse_suggestions_maps_numbered_lines_to_targets():
    text = "1. CustomerID\n2. CompanyName\n3. NONE"
    targets = ["customer_id", "name", "unmatched_field"]
    assert _parse_suggestions(text, targets) == {
        "customer_id": "CustomerID",
        "name": "CompanyName",
        "unmatched_field": None,
    }


def test_parse_suggestions_ignores_unparseable_lines():
    text = "Sure, here are the matches:\n1. CustomerID\nsome extra chatter\n2. NONE"
    targets = ["customer_id", "name"]
    result = _parse_suggestions(text, targets)
    assert result["customer_id"] == "CustomerID"
    assert result["name"] is None


def test_parse_suggestions_defaults_missing_indices_to_none():
    text = "1. CustomerID"
    targets = ["customer_id", "name"]
    assert _parse_suggestions(text, targets) == {"customer_id": "CustomerID", "name": None}


def test_parse_suggestions_ignores_out_of_range_index():
    text = "1. CustomerID\n5. Bogus"
    targets = ["customer_id"]
    assert _parse_suggestions(text, targets) == {"customer_id": "CustomerID"}
