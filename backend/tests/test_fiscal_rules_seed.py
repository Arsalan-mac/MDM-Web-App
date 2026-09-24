import re

from app.cleansing.fiscal_rules_seed import FISCAL_RULES_SEED

_ALLOWED_ENTITY_TYPES = {"ORG", "IND", "GENERIC"}


def test_seed_has_expected_country_count():
    assert len(FISCAL_RULES_SEED) >= 85


def test_every_country_code_is_uppercase_and_well_formed():
    for country in FISCAL_RULES_SEED:
        assert country == country.upper()
        assert re.match(r"^[A-Z]{2}$", country), country


def test_every_entity_type_is_known():
    for country, entities in FISCAL_RULES_SEED.items():
        for entity_type in entities:
            assert entity_type in _ALLOWED_ENTITY_TYPES, f"{country}/{entity_type}"


def test_every_rule_has_required_keys_and_compiles():
    for country, entities in FISCAL_RULES_SEED.items():
        for entity_type, rule in entities.items():
            assert "regex" in rule, f"{country}/{entity_type} missing regex"
            re.compile(rule["regex"])
            for alias in rule.get("aliases", []):
                re.compile(alias)
            assert isinstance(rule.get("aliases", []), list)
            assert "desc" in rule


def test_germany_org_matches_ten_digit_tax_number():
    rule = FISCAL_RULES_SEED["DE"]["ORG"]
    assert re.match(rule["regex"], "1234567890")


def test_germany_org_rejects_too_short():
    rule = FISCAL_RULES_SEED["DE"]["ORG"]
    assert not re.match(rule["regex"], "12345")


def test_italy_individual_accepts_codice_fiscale_and_alias_partita_iva():
    rule = FISCAL_RULES_SEED["IT"]["IND"]
    assert re.match(rule["regex"], "RSSMRA80A01H501U")
    assert any(re.match(alt, "12345678901") for alt in rule["aliases"])


def test_every_country_has_generic_fallback():
    for country, entities in FISCAL_RULES_SEED.items():
        assert "GENERIC" in entities, country
