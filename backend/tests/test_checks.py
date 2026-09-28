"""Check Catalog tests. Deliberately uses non-SAP, arbitrary column names
throughout (e.g. "reg_no" instead of "RegisterNumber", "street_addr"
instead of "Address") - the whole point of this layer is that a check
never assumes a fixed schema, only a role_mapping the caller supplies."""

import pytest

from app.checks import get_check, list_checks, missing_roles, run_check


def test_catalog_lists_all_builtin_checks():
    keys = {c.key for c in list_checks()}
    assert keys == {
        "address_format",
        "completeness",
        "duplicate_detection",
        "email_format",
        "fiscal_code_format",
        "phone_format",
        "register_number_format",
        "vat_format",
        "website_format",
    }


def test_missing_roles_reports_unmapped_required_role():
    assert missing_roles("email_format", {}) == ["email"]
    assert missing_roles("email_format", {"email": "contact_mail"}) == []


def test_missing_roles_ignores_optional_roles():
    # address_format's optional roles (city/postal_code/country_code) never
    # count as "missing" - only its required "address" role does.
    assert missing_roles("address_format", {"address": "street_addr"}) == []


def test_unknown_check_raises():
    with pytest.raises(KeyError):
        run_check("not_a_real_check", [], {})


def test_register_number_format_uses_mapped_column():
    rows = [{"reg_no": "HRB 3792"}, {"reg_no": "keine"}, {"reg_no": ""}]
    findings = run_check("register_number_format", rows, {"register_number": "reg_no"})
    assert len(findings) == 1
    assert findings[0].row_index == 1
    assert findings[0].field == "reg_no"


def test_address_format_flags_junk_and_proposes_a_fix():
    rows = [
        {"street_addr": "Hauptstrasse 12", "town": "Muenchen", "cc": "DE"},
        {"street_addr": "Hauptstrasse 12, 80331 Muenchen", "town": "Muenchen", "cc": "DE"},
    ]
    role_mapping = {"address": "street_addr", "city": "town", "country_code": "cc"}
    findings = run_check("address_format", rows, role_mapping)
    row1_findings = [f for f in findings if f.row_index == 1]
    assert row1_findings, "city embedded in the address should be flagged"
    assert row1_findings[0].field == "street_addr"


def test_email_format_flags_invalid_and_ignores_empty():
    rows = [{"contact_mail": "a@b.com"}, {"contact_mail": "not-an-email"}, {"contact_mail": ""}]
    findings = run_check("email_format", rows, {"email": "contact_mail"})
    assert [f.row_index for f in findings] == [1]


def test_website_format_flags_invalid():
    rows = [{"url": "https://example.com"}, {"url": "not a url"}]
    findings = run_check("website_format", rows, {"website": "url"})
    assert [f.row_index for f in findings] == [1]


def test_phone_format_flags_too_short():
    rows = [{"tel": "+49 89 12345678"}, {"tel": "123"}]
    findings = run_check("phone_format", rows, {"phone": "tel"})
    assert [f.row_index for f in findings] == [1]


def test_completeness_flags_empty_required_fields_across_columns():
    rows = [
        {"company": "Acme GmbH", "vat": "DE123"},
        {"company": "", "vat": "DE456"},
        {"company": "Beta", "vat": ""},
    ]
    findings = run_check("completeness", rows, {"required_fields": ["company", "vat"]})
    assert {(f.row_index, f.field) for f in findings} == {(1, "company"), (2, "vat")}


def test_completeness_accepts_a_single_column_string_too():
    rows = [{"company": "Acme"}, {"company": ""}]
    findings = run_check("completeness", rows, {"required_fields": "company"})
    assert [f.row_index for f in findings] == [1]


def test_duplicate_detection_finds_near_identical_rows():
    rows = [
        {"co_name": "Acme Consulting GmbH", "addr": "Hauptstrasse 12", "country": "DE"},
        {"co_name": "Acme Consulting GmbH", "addr": "Hauptstrasse 12", "country": "DE"},
        {"co_name": "Completely Different Ltd", "addr": "Nowhere Street 99", "country": "DE"},
    ]
    role_mapping = {"match_fields": ["co_name", "addr"], "group_by": "country"}
    findings = run_check("duplicate_detection", rows, role_mapping)
    flagged_rows = {f.row_index for f in findings}
    assert 0 in flagged_rows or 1 in flagged_rows


def test_duplicate_detection_group_by_keeps_different_groups_apart():
    rows = [
        {"co_name": "Acme GmbH", "addr": "Hauptstrasse 12", "country": "DE"},
        {"co_name": "Acme GmbH", "addr": "Hauptstrasse 12", "country": "IT"},
    ]
    role_mapping = {"match_fields": ["co_name", "addr"], "group_by": "country"}
    findings = run_check("duplicate_detection", rows, role_mapping)
    assert findings == []


def test_get_check_returns_none_for_unknown_key():
    assert get_check("nonexistent") is None


def test_vat_format_uses_self_describing_prefix_without_a_country_column():
    rows = [{"tax_id": "DE123456789"}, {"tax_id": "DE12"}, {"tax_id": ""}]
    findings = run_check("vat_format", rows, {"vat_number": "tax_id"})
    assert len(findings) == 1
    assert findings[0].row_index == 1
    assert findings[0].field == "tax_id"


def test_vat_format_uses_the_mapped_country_column_when_present():
    rows = [{"tax_id": "DE123456789", "cc": "DE"}]
    findings = run_check("vat_format", rows, {"vat_number": "tax_id", "country_code": "cc"})
    assert findings == []


def test_vat_format_flags_unrecognized_country_prefix():
    rows = [{"tax_id": "ZZ999"}]
    findings = run_check("vat_format", rows, {"vat_number": "tax_id"})
    assert len(findings) == 1
    assert "Unrecognized country prefix" in findings[0].message


def test_fiscal_code_format_valid_value_produces_no_finding():
    rows = [{"tin": "12345678901", "cc": "BR", "kind": "IND"}]
    findings = run_check(
        "fiscal_code_format", rows, {"fiscal_code": "tin", "country_code": "cc", "entity_type": "kind"}
    )
    assert findings == []


def test_fiscal_code_format_flags_a_value_not_matching_the_country_rule():
    rows = [{"tin": "notanumber", "cc": "BR", "kind": "IND"}]
    findings = run_check(
        "fiscal_code_format", rows, {"fiscal_code": "tin", "country_code": "cc", "entity_type": "kind"}
    )
    assert len(findings) == 1
    assert findings[0].field == "tin"


def test_fiscal_code_format_flags_unrecognized_country():
    rows = [{"tin": "12345", "cc": "ZZ"}]
    findings = run_check("fiscal_code_format", rows, {"fiscal_code": "tin", "country_code": "cc"})
    assert len(findings) == 1
    assert "Unrecognized country code" in findings[0].message


def test_fiscal_code_format_defaults_to_generic_entity_type_when_unmapped():
    rows = [{"tin": "12345678901", "cc": "BR"}]
    findings = run_check("fiscal_code_format", rows, {"fiscal_code": "tin", "country_code": "cc"})
    assert findings == []
