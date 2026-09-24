import re

from app.cleansing.vat_rules import (
    VAT_RULES,
    clean_norwegian_vat,
    clean_swiss_vat,
    clean_tax_number,
    split_russian_tax_number,
)


def test_clean_swiss_vat_from_dotted_format_with_suffix():
    assert clean_swiss_vat("CHE-123.456.789 MWST") == "CHE123456789MWST"


def test_clean_swiss_vat_from_bare_digits():
    assert clean_swiss_vat("123.456.789") == "CHE123456789"


def test_clean_swiss_vat_already_canonical():
    assert clean_swiss_vat("CHE123456789TVA") == "CHE123456789TVA"


def test_clean_norwegian_vat_adds_prefix_and_suffix():
    assert clean_norwegian_vat("123456789") == "NO123456789MVA"


def test_clean_norwegian_vat_already_canonical():
    assert clean_norwegian_vat("NO123456789MVA") == "NO123456789MVA"


def test_clean_tax_number_strips_dots_hyphens_spaces():
    assert clean_tax_number("12.34-56 78", country="DE") == "12345678"


def test_clean_tax_number_preserves_slash_for_russia():
    assert clean_tax_number("781 / 101", country="RU") == "781 / 101"


def test_split_russian_tax_number_no_slash():
    assert split_russian_tax_number("7816017139") == ("7816017139", None, 0)


def test_split_russian_tax_number_one_slash():
    assert split_russian_tax_number("7816017139 / 781101001") == ("7816017139", "781101001", 1)


def test_split_russian_tax_number_two_slashes_not_splittable():
    inn, kpp, count = split_russian_tax_number("A/B/C")
    assert kpp is None
    assert count == 2


def test_split_russian_tax_number_strips_inn_kpp_labels():
    assert split_russian_tax_number("INN7816017139 / KPP781101001") == ("7816017139", "781101001", 1)


def test_vat_rules_de_valid():
    assert re.match(VAT_RULES["DE"], "DE123456789")


def test_vat_rules_de_invalid_too_short():
    assert not re.match(VAT_RULES["DE"], "DE12345678")


def test_vat_rules_ch_valid_with_suffix():
    assert re.match(VAT_RULES["CH"], "CHE123456789MWST")


def test_vat_rules_no_requires_mva_suffix():
    assert re.match(VAT_RULES["NO"], "NO123456789MVA")
    assert not re.match(VAT_RULES["NO"], "NO123456789")


def test_vat_rules_covers_expected_country_count():
    # AT..RU, plus several non-EU markets - guards against an accidental
    # truncation of the dict during a future edit.
    assert len(VAT_RULES) >= 65
