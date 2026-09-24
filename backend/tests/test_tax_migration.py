from app.cleansing.tax_service import _assign_ca_code, _migration_row, suggest_collision_code


def test_assign_ca_code_rt_pattern_keeps_full_value():
    assert _assign_ca_code("123456789RT0001") == ("CA1", "123456789RT0001")


def test_assign_ca_code_bare_nine_digits():
    assert _assign_ca_code("123456789") == ("CA2", "123456789")


def test_assign_ca_code_other_r_letter_pattern_extracts_bn():
    assert _assign_ca_code("123456789RC0001") == ("CA2", "123456789")


def test_assign_ca_code_unrecognized_pattern_returns_none_code():
    code, value = _assign_ca_code("RC0001")
    assert code is None
    assert value == "RC0001"


def test_assign_ca_code_strips_punctuation_before_matching():
    assert _assign_ca_code("123 456 789 RT 0001") == ("CA1", "123456789RT0001")


def test_migration_row_short_value_uses_taxnuml():
    row = _migration_row("P1", "DE123456789", "DE0", "DE")
    assert row["TAXNUML"] == "DE123456789"
    assert row["TAXNUMXL"] is None


def test_migration_row_long_value_uses_taxnumxl():
    long_value = "X" * 25
    row = _migration_row("P1", long_value, "DE1", "DE")
    assert row["TAXNUML"] is None
    assert row["TAXNUMXL"] == long_value


def test_migration_row_empty_value_defaults_to_empty_string():
    row = _migration_row("P1", "", "DE0", "DE")
    assert row["SourceValue"] == ""
    assert row["TAXNUML"] == ""


def test_suggest_collision_code_vat_suggests_official_vat_category():
    assert suggest_collision_code("DE", "DE1", "VAT") == "DE0"


def test_suggest_collision_code_vat_no_alternative_when_already_correct():
    assert suggest_collision_code("DE", "DE0", "VAT") is None


def test_suggest_collision_code_steuernummer_prefers_steuer_description():
    assert suggest_collision_code("DE", "DE0", "STEUERNUMMER") == "DE1"


def test_suggest_collision_code_unknown_country_returns_none():
    assert suggest_collision_code("ZZ", "ZZ0", "VAT") is None
