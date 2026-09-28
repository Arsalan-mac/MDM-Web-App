"""Custom (no-code) check interpreter tests - app/checks/custom.py. Uses
arbitrary column names throughout, same convention as test_checks.py."""

from app.checks.custom import (
    run_cross_dataset_exists,
    run_in_list,
    run_range,
    run_regex,
    run_required,
    run_unique,
)


def test_required_flags_empty_values():
    rows = [{"vat": "DE123"}, {"vat": ""}, {"vat": None}]
    findings = run_required(rows, {"column": "vat"}, "error")
    assert [f.row_index for f in findings] == [1, 2]
    assert findings[0].severity == "error"


def test_regex_flags_non_matching_non_empty_values():
    rows = [{"code": "AB-1234"}, {"code": "bad"}, {"code": ""}]
    findings = run_regex(rows, {"column": "code", "pattern": r"^[A-Z]{2}-\d{4}$"}, "warning")
    assert [f.row_index for f in findings] == [1]


def test_in_list_flags_values_outside_the_allowed_set():
    rows = [{"status": "active"}, {"status": "pending"}, {"status": ""}]
    findings = run_in_list(rows, {"column": "status", "values": ["active", "inactive"]}, "warning")
    assert [f.row_index for f in findings] == [1]


def test_range_flags_out_of_bounds_and_non_numeric():
    rows = [{"age": "30"}, {"age": "150"}, {"age": "abc"}, {"age": ""}]
    findings = run_range(rows, {"column": "age", "min": 0, "max": 120}, "error")
    assert {f.row_index for f in findings} == {1, 2}


def test_range_with_only_a_min_ignores_max():
    rows = [{"amount": "-5"}, {"amount": "1000000"}]
    findings = run_range(rows, {"column": "amount", "min": 0, "max": None}, "error")
    assert [f.row_index for f in findings] == [0]


def test_unique_flags_every_repeat_after_the_first():
    rows = [{"sku": "A1"}, {"sku": "A1"}, {"sku": "B2"}, {"sku": "A1"}]
    findings = run_unique(rows, {"column": "sku"}, "error")
    assert [f.row_index for f in findings] == [1, 3]
    assert "row 1" in findings[0].message


def test_unique_ignores_empty_values():
    rows = [{"sku": ""}, {"sku": ""}]
    assert run_unique(rows, {"column": "sku"}, "error") == []


def test_cross_dataset_exists_flags_unmatched_rows():
    rows = [{"customer_id": "C1"}, {"customer_id": "C2"}, {"customer_id": ""}]
    related_rows = [{"cust_ref": "C1"}]
    findings = run_cross_dataset_exists(rows, {}, "error", related_rows, "customer_id", "cust_ref")
    assert [f.row_index for f in findings] == [1]
    assert findings[0].field == "customer_id"


def test_cross_dataset_exists_all_matched_gives_no_findings():
    rows = [{"customer_id": "C1"}, {"customer_id": "C2"}]
    related_rows = [{"cust_ref": "C1"}, {"cust_ref": "C2"}]
    assert run_cross_dataset_exists(rows, {}, "error", related_rows, "customer_id", "cust_ref") == []
