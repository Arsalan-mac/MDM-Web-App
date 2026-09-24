"""Hand-encoded mapping config for SAP Template Migration's BUT000-General
and ADRC-Address sheets, extracted from the original app's mapping-spec
files (mapping_specs/"BUT000-General.map" and mapping_specs/"ADRC -
Address.map").

The original parses these as text files at runtime (a small DSL - see
sap_template_module.py::parse_spec_file), but that parser exists only
because the spec files are meant to be hand-edited outside the app (see the
files' own header comments: "Bearbeiten z. B. in VS Code") and then
re-ingested - there is no in-app text editor for them, and nothing here
reads the spec format back out as text. Reference config that's edited as
code, not through the UI, is exactly the pattern this app already uses for
FISCAL_RULES/VAT_MAPPING/SAP_TAX_CATEGORIES: extracted once (there,
programmatically via ast.literal_eval; here, by hand, since the source is a
small custom DSL rather than a Python literal) and checked in as structured
data instead of re-implementing a runtime text parser nothing else needs.

Every field mapping below was checked against the original .map file
verbatim - same target field order, same lengths, same rule types, same
conditions. Two sheets only, chosen as the first slice of SAP Template
Migration because both use the default base table (`Mandanten`, no fan-out)
and only the FLAG overflow policy (see docs/ROADMAP.md) - the four
materialized-table sheets (BUT100/BUT0ID/BUT0IS/BUT000-Append) and
DFKKBPTAXNUM are deliberately not ported yet.

REGION has no source: the original stopped exporting it on 2026-09-22 (the
SAP cockpit rejected the Bundesland codes it used to carry) and its own
.map file documents mapping Mandanten.REGION straight through - but that
column was never populated by anything even in the original after that
decision, so it's represented here as an always-empty CONSTANT rather than
adding a dead Mandant column for a field nothing ever fills in.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    target_field: str
    target_length: int = 0
    rule: str = "DIRECT_COPY"  # DIRECT_COPY | CONSTANT | CONDITIONAL_MAP | CONDITIONAL_COPY | NOT_APPLICABLE

    # DIRECT_COPY: the Mandant attribute to copy. CONDITIONAL_MAP/COPY: the
    # Mandant attribute the condition tests (unless overridden by
    # `join_exists_on`, see below).
    source: str | None = None
    # CONDITIONAL_COPY's Then value: another Mandant attribute to copy from
    # (mutually exclusive with `then_value`).
    then_source: str | None = None

    # A join-based existence test instead of a Mandant field - only used by
    # ADRC's _COMMENT ("does this IDParty have an open JUNK_ADDRESS row?").
    join_exists_on: str | None = None  # model class name, joined on IDParty

    fixed_value: str | None = None  # CONSTANT
    condition_op: str | None = None  # "eq" | "not_empty", for CONDITIONAL_MAP/COPY
    condition_value: str | None = None  # for "eq"
    then_value: str | None = None  # CONDITIONAL_MAP's literal Then
    else_value: str | None = None  # literal Else - "" (stays empty) if not given

    date_format: str | None = None  # e.g. "YYYYMMDD", applied after the rule runs
    on_overflow: str | None = None  # "FLAG" (the only policy these two sheets use)
    anonymize: str | None = None  # metadata only - anonymized export isn't ported yet


BUT000_GENERAL: list[FieldSpec] = [
    FieldSpec("SOURCE_ID", 16, "DIRECT_COPY", source="IDParty", on_overflow="FLAG", anonymize="ID"),
    FieldSpec("BUSINESS_SYSTEM", 60, "CONSTANT", fixed_value="CARP", on_overflow="FLAG"),
    FieldSpec("PARTNER", 10, "NOT_APPLICABLE"),
    FieldSpec("TYPE", 1, "NOT_APPLICABLE"),
    FieldSpec(
        "BPKIND", 4, "CONDITIONAL_MAP", source="IsOrganisation",
        condition_op="eq", condition_value="1", then_value="2", else_value="1", on_overflow="FLAG",
    ),
    FieldSpec(
        "BU_GROUP", 4, "CONDITIONAL_MAP", source="RoedlCompanyNumber",
        condition_op="not_empty", then_value="ZICO", else_value="ZMDH", on_overflow="FLAG",
    ),
    FieldSpec("BU_SORT1", 40, "DIRECT_COPY", source="Name1", on_overflow="FLAG", anonymize="ORG_NAME"),
    FieldSpec(
        "TITLE", 4, "CONDITIONAL_COPY", source="IsIndividual", then_source="TitleCode",
        condition_op="eq", condition_value="1", on_overflow="FLAG",
    ),
    FieldSpec("NAME1_ORG", 40, "DIRECT_COPY", source="Name1", on_overflow="FLAG", anonymize="ORG_NAME"),
    FieldSpec("NAME2_ORG", 40, "DIRECT_COPY", source="Name2", on_overflow="FLAG", anonymize="TEXT"),
    FieldSpec("NAME3_ORG", 40, "DIRECT_COPY", source="Name3", on_overflow="FLAG", anonymize="TEXT"),
    FieldSpec("NAME4_ORG", 40, "DIRECT_COPY", source="Name4", on_overflow="FLAG", anonymize="TEXT"),
    FieldSpec(
        "XDELE", 1, "CONDITIONAL_MAP", source="IsInactive",
        condition_op="eq", condition_value="1", then_value="X", on_overflow="FLAG",
    ),
    FieldSpec("LEGAL_ENTY", 2, "DIRECT_COPY", source="LegalFormCode", on_overflow="FLAG"),
    FieldSpec("BU_NAMEP_F", 40, "DIRECT_COPY", source="FirstName", on_overflow="FLAG", anonymize="FIRST_NAME"),
    FieldSpec("BU_NAMEP_L", 40, "DIRECT_COPY", source="LastName", on_overflow="FLAG", anonymize="LAST_NAME"),
]

ADRC_ADDRESS: list[FieldSpec] = [
    FieldSpec(
        "_COMMENT", 0, "CONDITIONAL_MAP", join_exists_on="JunkAddress",
        condition_op="not_empty", then_value="Fehlerhafte Anschrift",
    ),
    FieldSpec("SOURCE_ID", 16, "DIRECT_COPY", source="IDParty", on_overflow="FLAG", anonymize="ID"),
    FieldSpec("SOURCE_ADDRNUMBER", 10, "NOT_APPLICABLE"),
    FieldSpec("DATE_FROM", 8, "DIRECT_COPY", source="AddedDate", date_format="YYYYMMDD", on_overflow="FLAG"),
    FieldSpec("CITY1", 40, "DIRECT_COPY", source="City", on_overflow="FLAG"),
    FieldSpec("POST_CODE1", 10, "DIRECT_COPY", source="ZipCode", on_overflow="FLAG"),
    FieldSpec("STREET", 60, "DIRECT_COPY", source="STREET", on_overflow="FLAG", anonymize="STREET"),
    FieldSpec("STR_SUPPL1", 40, "DIRECT_COPY", source="STR_SUPPL1", on_overflow="FLAG", anonymize="TEXT"),
    FieldSpec("STR_SUPPL2", 40, "DIRECT_COPY", source="STR_SUPPL2", on_overflow="FLAG", anonymize="TEXT"),
    FieldSpec("STR_SUPPL3", 40, "DIRECT_COPY", source="STR_SUPPL3", on_overflow="FLAG", anonymize="TEXT"),
    FieldSpec("HOUSE_NUM1", 10, "DIRECT_COPY", source="HOUSE_NUM1", on_overflow="FLAG", anonymize="HOUSE_NUMBER"),
    FieldSpec("BUILDING", 20, "DIRECT_COPY", source="BUILDING", on_overflow="FLAG", anonymize="TEXT"),
    FieldSpec("COUNTRY", 3, "DIRECT_COPY", source="CountryCode", on_overflow="FLAG"),
    FieldSpec("REGION", 3, "CONSTANT", fixed_value="", on_overflow="FLAG"),
]

SHEETS: dict[str, list[FieldSpec]] = {
    "BUT000-General": BUT000_GENERAL,
    "ADRC-Address": ADRC_ADDRESS,
}
