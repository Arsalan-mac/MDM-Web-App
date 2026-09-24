from app.cleansing.sap_carp_service import (
    _MANDANT_COLUMN_TO_ATTR,
    _name_needs_llm,
    _parse_condition,
    _resolve_sap_key,
    _split_name,
)


def test_resolve_sap_key_prefers_idparty():
    assert _resolve_sap_key(["Ext. Partnernummer", "IDParty", "CompanyName"]) == "IDParty"


def test_resolve_sap_key_falls_back_to_ext_partnernummer():
    assert _resolve_sap_key(["Ext. Partnernummer", "CompanyName"]) == "Ext. Partnernummer"


def test_resolve_sap_key_returns_none_when_neither_present():
    assert _resolve_sap_key(["CompanyName"]) is None


def test_parse_condition_variants():
    assert _parse_condition("IsOrganisation = 1") == "1"
    assert _parse_condition("IsOrganisation=1") == "1"
    assert _parse_condition("IsOrganisation = 0") == "0"
    assert _parse_condition("") is None
    assert _parse_condition(None) is None
    assert _parse_condition("something else") is None


def test_split_name_comma_format():
    result = _split_name("Mueller, Hans")
    assert result == {"first_name": "Hans", "last_name": "Mueller", "method": "komma"}


def test_split_name_two_token():
    result = _split_name("Hans Mueller")
    assert result == {"first_name": "Hans", "last_name": "Mueller", "method": "2-token"}


def test_split_name_single_token_is_unclear():
    result = _split_name("Mueller")
    assert result == {"first_name": "", "last_name": "Mueller", "method": "unklar"}


def test_split_name_empty_is_unclear():
    result = _split_name("")
    assert result == {"first_name": "", "last_name": "", "method": "unklar"}


def test_split_name_three_token_uses_llm_cache_when_present():
    cache = {"Hans Peter Mueller": {"first_name": "Hans Peter", "last_name": "Mueller", "method": "llm"}}
    result = _split_name("Hans Peter Mueller", cache)
    assert result == cache["Hans Peter Mueller"]


def test_split_name_three_token_falls_back_when_no_llm_result():
    result = _split_name("Hans Peter Mueller", llm_cache={})
    assert result == {"first_name": "Hans", "last_name": "Peter Mueller", "method": "unklar"}


def test_name_needs_llm_flags_three_plus_tokens():
    assert _name_needs_llm("Hans Peter Mueller") == "Hans Peter Mueller"


def test_name_needs_llm_skips_comma_format():
    assert _name_needs_llm("Mueller, Hans Peter") is None


def test_name_needs_llm_skips_two_tokens():
    assert _name_needs_llm("Hans Mueller") is None


def test_writable_mandant_columns_excludes_system_fields():
    assert "CompanyName" in _MANDANT_COLUMN_TO_ATTR
    assert "IDParty" not in _MANDANT_COLUMN_TO_ATTR
    assert "project_id" not in _MANDANT_COLUMN_TO_ATTR
    assert "SapOverridden" not in _MANDANT_COLUMN_TO_ATTR
    assert "extra" not in _MANDANT_COLUMN_TO_ATTR


def test_writable_mandant_columns_maps_db_name_to_python_attr():
    # "Name 1" is the column's DB/SAP-spec name; the Python attribute
    # setattr() needs is "Name1" - see app/models/tenant.py.
    assert _MANDANT_COLUMN_TO_ATTR["Name 1"] == "Name1"
    assert _MANDANT_COLUMN_TO_ATTR["CompanyName"] == "CompanyName"
