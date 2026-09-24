from app.cleansing.address_decomposition import (
    CONF_HIGH,
    CONF_MANUAL,
    CONF_MED,
    needs_llm,
    parse_address,
    spell_out_street,
)


def test_t1_house_number_at_end():
    r = parse_address("Hauptstraße 12", "DE")
    assert r.street == "Hauptstraße"
    assert r.house_num == "12"
    assert r.method == "T1_NR_HINTEN"
    assert r.confidence == CONF_HIGH


def test_t1_eats_leading_comma():
    r = parse_address("Via Trieste, 23", "IT")
    assert r.street == "Via Trieste"
    assert r.house_num == "23"


def test_t2_house_number_at_front_for_us_convention():
    r = parse_address("514 Henderson Street", "US")
    assert r.street == "Henderson Street"
    assert r.house_num == "514"
    assert r.method == "T2_NR_VORNE"


def test_ambiguous_front_and_end_decided_by_country():
    # '16 Church Road 3' could parse either way; GB is number-first.
    r = parse_address("16 Church Road", "GB")
    assert r.house_num == "16"
    assert r.street == "Church Road"


def test_t0_postfach_goes_entirely_to_street():
    r = parse_address("Postfach 1234", "DE")
    assert r.method == "T0_POSTFACH"
    assert r.street == "Postfach 1234"
    assert r.house_num == ""
    assert r.confidence == CONF_HIGH


def test_co_prefix_moves_to_supplement():
    r = parse_address("c/o Musterfirma GmbH, Bahnhofstr. 5", "DE")
    assert r.suppl1 == "c/o Musterfirma GmbH"
    assert r.street == "Bahnhofstr."
    assert r.house_num == "5"
    assert r.confidence == CONF_MED


def test_parenthesized_suffix_becomes_building():
    r = parse_address("Tekniikantie 14 (Innopoli 2)", "FI")
    assert r.street == "Tekniikantie"
    assert r.house_num == "14"
    assert r.building == "Innopoli 2"


def test_t3_complex_comma_segments_with_house_number_pair():
    r = parse_address("Strada Vulturilor, Nr. 98", "RO")
    assert r.street == "Strada Vulturilor"
    assert r.house_num == "98"


def test_t3_no_house_number_flags_manual():
    r = parse_address("Musterstraße ohne Nummer irgendwo", "DE")
    assert r.method in ("T3_REGEX",)
    assert "Keine Hausnummer erkannt" in r.hinweis
    assert r.confidence == CONF_MANUAL


def test_empty_address_is_manual():
    r = parse_address("", "DE")
    assert r.confidence == CONF_MANUAL
    assert r.hinweis == "Adresse leer"


def test_house_number_too_long_falls_back_into_street():
    r = parse_address("Musterweg 123456789012345", "DE")
    assert r.house_num == ""
    assert r.confidence == CONF_MANUAL
    assert "Hausnummer" in r.hinweis


def test_distribute_street_never_exceeds_field_lengths():
    long_street = "A" * 200 + " 1"
    r = parse_address(long_street, "DE")
    assert len(r.street) <= 60
    assert len(r.suppl1) <= 40
    assert len(r.suppl2) <= 40
    assert len(r.suppl3) <= 40


def test_spell_out_street_de():
    assert spell_out_street("Hauptstr.", "DE") == "Hauptstraße"


def test_spell_out_street_ch_uses_strasse():
    assert spell_out_street("Bahnhofstr", "CH") == "Bahnhofstrasse"


def test_spell_out_street_noop_for_unsupported_country():
    assert spell_out_street("Main Street", "US") == ""


def test_spell_out_street_noop_when_nothing_to_change():
    assert spell_out_street("Musterweg", "DE") == ""


def test_needs_llm_true_for_manual_confidence():
    r = parse_address("", "DE")
    assert needs_llm(r)


def test_needs_llm_false_for_high_confidence():
    r = parse_address("Hauptstraße 12", "DE")
    assert not needs_llm(r)


def test_needs_llm_true_for_t3_regex_even_with_medium_confidence():
    r = parse_address("Gebäude X, Strada Vulturilor, Nr. 98", "RO")
    assert r.method == "T3_REGEX"
    assert r.confidence == CONF_MED
    # T3 always goes to the LLM scope regardless of confidence.
    assert needs_llm(r)
