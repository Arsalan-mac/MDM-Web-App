from app.cleansing.sap_template_mappings import ADRC_ADDRESS, BUT000_GENERAL
from app.cleansing.sap_template_service import _apply_field, apply_date_format
from app.models.tenant import Mandant


def _spec(sheet, target_field):
    return next(s for s in sheet if s.target_field == target_field)


def test_apply_date_format_iso_datetime():
    value, ok = apply_date_format("2026-09-22 10:15:00.000", "YYYYMMDD")
    assert value == "20260922"
    assert ok is True


def test_apply_date_format_iso_compact():
    value, ok = apply_date_format("20260922", "YYYYMMDD")
    assert value == "20260922"
    assert ok is True


def test_apply_date_format_eu_day_first():
    value, ok = apply_date_format("22.09.2026", "YYYYMMDD")
    assert value == "20260922"
    assert ok is True


def test_apply_date_format_unrecognized_kept_unchanged():
    value, ok = apply_date_format("not a date", "YYYYMMDD")
    assert value == "not a date"
    assert ok is False


def test_apply_date_format_empty_stays_empty():
    value, ok = apply_date_format("", "YYYYMMDD")
    assert value == ""
    assert ok is True


def test_apply_date_format_implausible_month_rejected():
    value, ok = apply_date_format("2026-13-01", "YYYYMMDD")
    assert value == "2026-13-01"
    assert ok is False


def test_direct_copy_source_id():
    spec = _spec(BUT000_GENERAL, "SOURCE_ID")
    m = Mandant(IDParty="P-0001234567890123")
    value, ok = _apply_field(m, spec, {})
    assert value == "P-0001234567890123"
    assert ok is False  # 18 chars > allowed 16


def test_not_applicable_is_always_empty():
    spec = _spec(BUT000_GENERAL, "PARTNER")
    m = Mandant(IDParty="P1")
    value, ok = _apply_field(m, spec, {})
    assert value == ""
    assert ok is True


def test_constant_rule():
    spec = _spec(BUT000_GENERAL, "BUSINESS_SYSTEM")
    m = Mandant(IDParty="P1")
    value, ok = _apply_field(m, spec, {})
    assert value == "CARP"
    assert ok is True


def test_conditional_map_bpkind_organisation():
    spec = _spec(BUT000_GENERAL, "BPKIND")
    m = Mandant(IDParty="P1", IsOrganisation="1")
    value, _ = _apply_field(m, spec, {})
    assert value == "2"


def test_conditional_map_bpkind_person():
    spec = _spec(BUT000_GENERAL, "BPKIND")
    m = Mandant(IDParty="P1", IsOrganisation="0")
    value, _ = _apply_field(m, spec, {})
    assert value == "1"


def test_conditional_map_bu_group_roedl():
    spec = _spec(BUT000_GENERAL, "BU_GROUP")
    m = Mandant(IDParty="P1", RoedlCompanyNumber="12345")
    value, _ = _apply_field(m, spec, {})
    assert value == "ZICO"


def test_conditional_map_bu_group_non_roedl():
    spec = _spec(BUT000_GENERAL, "BU_GROUP")
    m = Mandant(IDParty="P1", RoedlCompanyNumber=None)
    value, _ = _apply_field(m, spec, {})
    assert value == "ZMDH"


def test_conditional_copy_title_only_for_individuals():
    spec = _spec(BUT000_GENERAL, "TITLE")
    m = Mandant(IDParty="P1", IsIndividual="1", TitleCode="DR")
    value, _ = _apply_field(m, spec, {})
    assert value == "DR"


def test_conditional_copy_title_empty_for_organisations():
    spec = _spec(BUT000_GENERAL, "TITLE")
    m = Mandant(IDParty="P1", IsIndividual="0", TitleCode="DR")
    value, _ = _apply_field(m, spec, {})
    assert value == ""


def test_xdele_flag_for_inactive():
    spec = _spec(BUT000_GENERAL, "XDELE")
    m = Mandant(IDParty="P1", IsInactive="1")
    value, _ = _apply_field(m, spec, {})
    assert value == "X"


def test_xdele_empty_for_active():
    spec = _spec(BUT000_GENERAL, "XDELE")
    m = Mandant(IDParty="P1", IsInactive="0")
    value, _ = _apply_field(m, spec, {})
    assert value == ""


def test_adrc_comment_flags_junk_address_via_join():
    spec = _spec(ADRC_ADDRESS, "_COMMENT")
    m = Mandant(IDParty="P1")
    value, _ = _apply_field(m, spec, {"JunkAddress": {"P1"}})
    assert value == "Fehlerhafte Anschrift"


def test_adrc_comment_empty_when_not_in_junk_address():
    spec = _spec(ADRC_ADDRESS, "_COMMENT")
    m = Mandant(IDParty="P2")
    value, _ = _apply_field(m, spec, {"JunkAddress": {"P1"}})
    assert value == ""


def test_adrc_date_from_formats_added_date():
    spec = _spec(ADRC_ADDRESS, "DATE_FROM")
    m = Mandant(IDParty="P1", AddedDate="2026-01-15 08:00:00.000")
    value, ok = _apply_field(m, spec, {})
    assert value == "20260115"
    assert ok is True


def test_adrc_region_always_empty_constant():
    spec = _spec(ADRC_ADDRESS, "REGION")
    m = Mandant(IDParty="P1")
    value, ok = _apply_field(m, spec, {})
    assert value == ""
    assert ok is True


def test_adrc_street_overflow_flagged():
    spec = _spec(ADRC_ADDRESS, "STREET")
    m = Mandant(IDParty="P1", STREET="X" * 65)
    value, ok = _apply_field(m, spec, {})
    assert len(value) == 65
    assert ok is False


def test_adrc_street_within_limit_not_flagged():
    spec = _spec(ADRC_ADDRESS, "STREET")
    m = Mandant(IDParty="P1", STREET="Musterstraße")
    value, ok = _apply_field(m, spec, {})
    assert value == "Musterstraße"
    assert ok is True


def test_but000_general_has_16_fields_matching_original():
    assert len(BUT000_GENERAL) == 16


def test_adrc_address_has_14_fields_matching_original():
    assert len(ADRC_ADDRESS) == 14
