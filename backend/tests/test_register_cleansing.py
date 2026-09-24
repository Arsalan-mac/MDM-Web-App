from app.cleansing.register_cleansing_service import (
    CLS_CANONICAL,
    CLS_JUNK,
    CLS_LLM,
    CLS_STANDARD,
    _is_canonical,
    _validate_llm_cleaned,
    classify_value,
    standardize_register_number,
)


def test_standardize_unifies_prefix_spacing():
    assert standardize_register_number("HRB3792") == ("HRB 3792", "Praefix-Format vereinheitlicht")


def test_standardize_unifies_lowercase_prefix():
    assert standardize_register_number("hrb 3792") == ("HRB 3792", "Praefix-Format vereinheitlicht")


def test_standardize_already_canonical_returns_none():
    assert standardize_register_number("HRB 3792") == (None, "")


def test_standardize_collapses_whitespace_for_unknown_prefix():
    # An unrecognized prefix doesn't match the known-prefix pattern, so it
    # falls through to the generic whitespace-collapse fallback.
    assert standardize_register_number("ABC  123") == ("ABC 123", "Leerzeichen bereinigt")


def test_standardize_empty_returns_none():
    assert standardize_register_number("") == (None, "")
    assert standardize_register_number(None) == (None, "")


def test_is_canonical_pure_digits():
    assert _is_canonical("258099")


def test_is_canonical_at_firmenbuch_digit_suffix():
    assert _is_canonical("258099h")


def test_is_canonical_country_code_digits():
    assert _is_canonical("BZ-207496")


def test_is_canonical_rejects_arbitrary_text():
    assert not _is_canonical("HRN 227565 B")


def test_classify_value_standard():
    assert classify_value("HRB3792") == (CLS_STANDARD, "HRB 3792", "Praefix-Format vereinheitlicht")


def test_classify_value_canonical():
    assert classify_value("HRB 3792") == (CLS_CANONICAL, None, "")


def test_classify_value_junk_placeholder():
    cls, neu, grund = classify_value("keine")
    assert cls == CLS_JUNK


def test_classify_value_junk_dummy_digits():
    cls, _, _ = classify_value("1234")
    assert cls == CLS_JUNK


def test_classify_value_llm_legacy_hrn_prefix():
    cls, _, _ = classify_value("HRN 227565 B")
    assert cls == CLS_LLM


def test_classify_value_llm_court_text_is_not_junk():
    # Addon-only issue (court text, number extractable) -> LLM, not JUNK.
    cls, _, _ = classify_value("HRB 71290 Amtsgericht Frankfurt")
    assert cls == CLS_LLM


def test_validate_llm_cleaned_accepts_matching_digits():
    assert _validate_llm_cleaned("HRB 71290 Amtsgericht Frankfurt", "HRB 71290")


def test_validate_llm_cleaned_rejects_invented_digits():
    assert not _validate_llm_cleaned("HRB 71290", "HRB 99999")


def test_validate_llm_cleaned_rejects_empty():
    assert not _validate_llm_cleaned("HRB 71290", "")
