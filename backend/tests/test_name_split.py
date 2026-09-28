"""app/cleansing/name_split.py - shared by SAP-CARP's Name Splitting step
(app/cleansing/sap_carp_service.py, tested via its own old private names in
test_sap_carp.py) and Mapping Studio's "name_split" field kind. Re-tested
here directly under its public names so the shared module has its own
coverage independent of either caller."""

from app.cleansing.name_split import name_needs_llm, split_name


def test_split_name_comma_format():
    result = split_name("Mueller, Hans")
    assert result == {"first_name": "Hans", "last_name": "Mueller", "method": "komma"}


def test_split_name_two_token():
    result = split_name("Hans Mueller")
    assert result == {"first_name": "Hans", "last_name": "Mueller", "method": "2-token"}


def test_split_name_single_token_is_unclear():
    result = split_name("Mueller")
    assert result == {"first_name": "", "last_name": "Mueller", "method": "unklar"}


def test_split_name_empty_is_unclear():
    assert split_name("") == {"first_name": "", "last_name": "", "method": "unklar"}


def test_split_name_three_token_uses_llm_cache_when_present():
    cache = {"Hans Peter Mueller": {"first_name": "Hans Peter", "last_name": "Mueller", "method": "llm"}}
    result = split_name("Hans Peter Mueller", cache)
    assert result == cache["Hans Peter Mueller"]


def test_split_name_three_token_falls_back_when_no_llm_result():
    result = split_name("Hans Peter Mueller", llm_cache={})
    assert result == {"first_name": "Hans", "last_name": "Peter Mueller", "method": "unklar"}


def test_name_needs_llm_flags_three_plus_tokens():
    assert name_needs_llm("Hans Peter Mueller") == "Hans Peter Mueller"


def test_name_needs_llm_skips_comma_format():
    assert name_needs_llm("Mueller, Hans Peter") is None


def test_name_needs_llm_skips_two_tokens():
    assert name_needs_llm("Hans Mueller") is None
