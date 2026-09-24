from app.cleansing.quality_report import compute_quality_report
from app.cleansing.register_checks import register_number_issues


def test_register_number_issues_clean_is_no_findings():
    assert register_number_issues("HRB 44521") == []


def test_register_number_issues_empty_is_no_findings():
    assert register_number_issues("") == []
    assert register_number_issues(None) == []


def test_register_number_issues_placeholder():
    assert "Platzhalter/Vermerk statt Nummer" in register_number_issues("unbekannt")


def test_register_number_issues_placeholder_umlaut_variant():
    assert "Platzhalter/Vermerk statt Nummer" in register_number_issues("entfällt")
    assert "Platzhalter/Vermerk statt Nummer" in register_number_issues("in gründung")


def test_register_number_issues_no_digits():
    assert "Keine Ziffer enthalten" in register_number_issues("ABC")


def test_register_number_issues_digit_repetition():
    assert register_number_issues("11111") == ["Ziffernwiederholung (1×5)"]


def test_register_number_issues_dummy_sequence():
    assert "Verdaechtige Dummy-Folge" in register_number_issues("HRB 1234")


def test_register_number_issues_too_short():
    assert "Zu kurz (< 3 Zeichen)" in register_number_issues("A1")


def test_register_number_issues_court_text():
    reasons = register_number_issues("HRB 71290 Amtsgericht Frankfurt")
    assert "Zusatztext/Gerichtsangabe" in reasons


def test_compute_quality_report_splits_org_and_individual():
    rows = [
        {"IDParty": "1", "IsOrganisation": "1", "IsIndividual": "0"},
        {"IDParty": "2", "IsOrganisation": "1", "IsIndividual": "0"},
        {"IDParty": "3", "IsOrganisation": "0", "IsIndividual": "1"},
    ]
    report = compute_quality_report(rows, junk_ids={"2"}, empty_ids=set())
    by_type = {r["type"]: r for r in report}
    assert by_type["Organisation"]["total_clients"] == 2
    assert by_type["Organisation"]["total_junk"] == 1
    assert by_type["Organisation"]["total_valid"] == 1
    assert by_type["Natuerliche Person"]["total_clients"] == 1


def test_compute_quality_report_optional_field_excludes_empty_from_denominator():
    rows = [{"IDParty": str(i), "IsOrganisation": "1", "IsIndividual": "0"} for i in range(4)]
    # 1 junk, 1 empty, 2 valid
    report = compute_quality_report(rows, junk_ids={"0"}, empty_ids={"1"}, optional_field=True)
    org = report[0]
    assert org["total_valid"] == 2
    assert org["total_junk"] == 1
    assert org["total_empty"] == 1
    # denominator excludes empty: valid+junk = 3
    assert org["pct_valid"] == round(2 / 3 * 100, 2)
    assert org["pct_junk"] == round(1 / 3 * 100, 2)
    assert org["pct_empty"] == round(1 / 4 * 100, 2)


def test_compute_quality_report_skips_type_with_no_rows():
    rows = [{"IDParty": "1", "IsOrganisation": "1", "IsIndividual": "0"}]
    report = compute_quality_report(rows, junk_ids=set(), empty_ids=set())
    assert len(report) == 1
    assert report[0]["type"] == "Organisation"
