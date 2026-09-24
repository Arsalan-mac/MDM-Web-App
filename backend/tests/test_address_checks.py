from app.cleansing.address_checks import (
    ACTION_CLEAR,
    ACTION_MANUAL,
    ACTION_REPLACE,
    CAT_ADRESSE_FEHLT,
    CAT_FIRMENNAME,
    CAT_KEINE_HAUSNUMMER,
    CAT_KONTAKTINFO,
    CAT_ORT_IM_ADRESSFELD,
    CAT_PLATZHALTER,
    CAT_RECHTSFORM,
    CONF_HIGH,
    check_addresses,
)


def _row(**overrides):
    base = {
        "IDParty": "1",
        "UserCode_Added": "",
        "UserCode_Kummerer": "",
        "CompanyName": "Acme GmbH",
        "IsOrganisation": "1",
        "IsIndividual": "0",
        "IsInactive": "0",
        "Address": "",
        "City": "Berlin",
        "ZipCode": "10115",
        "CountryCode": "DE",
    }
    base.update(overrides)
    return base


def test_clean_address_produces_no_finding():
    rows = [_row(Address="Musterstrasse 12")]
    findings = check_addresses(rows, {}, "2026-01-01")
    assert findings == []


def test_missing_address_flagged_manual():
    rows = [_row(Address="")]
    [finding] = check_addresses(rows, {}, "2026-01-01")
    assert finding["Kategorie"] == CAT_ADRESSE_FEHLT
    assert finding["Aktion"] == ACTION_MANUAL


def test_placeholder_address_cleared_with_high_confidence():
    rows = [_row(Address="UNBEKANNT")]
    [finding] = check_addresses(rows, {}, "2026-01-01")
    assert finding["Kategorie"] == CAT_PLATZHALTER
    assert finding["Aktion"] == ACTION_CLEAR
    assert finding["Confidence"] == CONF_HIGH
    assert finding["Neu"] == ""


def test_legal_form_in_address_is_manual():
    rows = [_row(Address="Musterstrasse 12, Acme GmbH")]
    [finding] = check_addresses(rows, {}, "2026-01-01")
    assert finding["Kategorie"] == CAT_RECHTSFORM
    assert finding["Aktion"] == ACTION_MANUAL


def test_contact_info_in_address_is_manual():
    rows = [_row(Address="Musterstrasse 12, info@acme.example")]
    [finding] = check_addresses(rows, {}, "2026-01-01")
    assert finding["Kategorie"] == CAT_KONTAKTINFO
    assert finding["Aktion"] == ACTION_MANUAL


def test_no_house_number_flagged():
    rows = [_row(Address="Musterstrasse")]
    [finding] = check_addresses(rows, {}, "2026-01-01")
    assert finding["Kategorie"] == CAT_KEINE_HAUSNUMMER


def test_city_in_address_field_stripped_and_proposed():
    rows = [_row(Address="Musterstrasse 12, Berlin", City="Berlin")]
    [finding] = check_addresses(rows, {}, "2026-01-01")
    assert finding["Kategorie"] == CAT_ORT_IM_ADRESSFELD
    assert finding["Aktion"] == ACTION_REPLACE
    assert finding["Neu"] == "Musterstrasse 12"
    assert finding["Confidence"] == CONF_HIGH


def test_bare_city_name_as_whole_address_is_manual_firmenname():
    # A bare city name has no digits (fails _looks_like_address -> KEINE_HAUSNUMMER)
    # and no street word (-> FIRMENNAME_STATT_ADRESSE), *and* matches the
    # "Stadtname im Adressfeld" branch (-> ORT_IM_ADRESSFELD); _CAT_PRIORITY
    # ranks FIRMENNAME_STATT_ADRESSE above both, so that's the one shown.
    rows = [_row(Address="Berlin", City="Berlin")]
    [finding] = check_addresses(rows, {}, "2026-01-01")
    assert finding["Kategorie"] == CAT_FIRMENNAME
    assert finding["Aktion"] == ACTION_MANUAL
    assert finding["Neu"] == ""
