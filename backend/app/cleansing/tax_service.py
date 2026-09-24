"""Tax Cleansing: VAT-Cleansing, Steuernummer-Cleansing (Fiscal Code) and
Migration Preparation tabs. Ported from tax_cleansing_module.py's
run_unified_vat_analysis / run_vat_duplicate_analysis /
run_fiscal_code_analysis, the FISCAL_RULES DB layer, and the Migration
Preparation workflow (_run_vat_migration_if_requested,
_run_steuer_migration_if_requested, validate_taxtypes_against_categories,
the TAXTYPE_REMAP/TAXTYPE_ROW_FIX apply/CRUD layer, VAT_MAPPING).

Migration Preparation here deliberately drops two things from the
original:
- Every per-region/per-country Excel export (EU master file, one file per
  Non-EU country+code, separate RU1/RU3 files, Organizations/Individuals
  subfolders for Steuernummer). That's file-delivery mechanics, not
  migration logic - the underlying TaxMigrationResult table is this app's
  equivalent deliverable, retrievable over the API - consistent with
  every other stage's Excel-export deferral so far. The TAXTYPE
  assignment logic itself (including Canada's RT/BN pattern-based
  special-casing) is ported faithfully since that's real business logic,
  not export mechanics.
- SAP-Abgleich (run_sap_taxtype_sync): the original's own current version
  already hides this tab ("der SAP-Bestand wird nicht mehr als Referenz
  verwendet") and it depends on the SAP-Steuernummern upload this backend
  hasn't ported either, so there's nothing to wire it to.
"""

import re
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.constants import MANDANT_VAT_COL
from app.cleansing.fiscal_rules_seed import FISCAL_RULES_SEED
from app.cleansing.quality_report import compute_quality_report
from app.cleansing.sap_tax_categories import OBSOLETE_CATEGORIES, SAP_TAX_CATEGORIES
from app.cleansing.vat_mapping_seed import VAT_MAPPING_SEED
from app.cleansing.vat_rules import VAT_RULES, clean_norwegian_vat, clean_swiss_vat, clean_tax_number, split_russian_tax_number
from app.models.tenant import FiscalRule, Mandant, TaxMigrationResult, TaxtypeRemap, TaxtypeRowFix, VatMapping

_PLACEHOLDER_TOKENS = ("?", "*", "!", "TBA", "PENDING", "UNKNOWN")
_STRIP_NON_ALNUM_RE = re.compile(r"[^A-Z0-9Ñ&]")


def _is_clean(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none", "na", "<na>")


def _base_fields(m: Mandant) -> dict:
    return {
        "id_party": m.IDParty, "company_name": m.CompanyName,
        "is_organisation": m.IsOrganisation, "is_individual": m.IsIndividual,
        "is_inactive": m.IsInactive, "country_code": m.CountryCode,
    }


class _Entry(dict):
    """One value to run through the syntax/pattern checks - normally one per
    Mandant with a VAT number, but a Russian compound value ("INN / KPP")
    splits into two independent entries sharing the same IDParty."""


async def run_vat_analysis(db: AsyncSession, project_id: uuid.UUID) -> dict:
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())

    # Stage 1: backfill an empty VATNumber from ViesNumber (the only stage
    # that mutates Mandanten - everything below is read-only analysis).
    vies_backfilled = 0
    for m in mandanten:
        if _is_clean(m.VATNumber) and not _is_clean(m.ViesNumber):
            m.VATNumber = m.ViesNumber
            vies_backfilled += 1
    if vies_backfilled:
        await db.commit()

    entries: list[_Entry] = []
    ru_precleaning: list[dict] = []
    junk: list[dict] = []

    for m in mandanten:
        if _is_clean(m.VATNumber):
            continue
        base = _base_fields(m)
        cc = (m.CountryCode or "").strip().upper()
        working = m.VATNumber.strip().upper()

        if cc == "CH":
            working = clean_swiss_vat(working)
        elif cc == "NO":
            working = clean_norwegian_vat(working)

        if cc == "RU":
            inn, kpp, slash_count = split_russian_tax_number(working)
            if slash_count >= 2:
                junk.append(
                    {**base, "vat_number": working,
                     "reason": "RU Compound: More than 2 parts (2+ slashes) - cannot split", "rule_used": "RU"}
                )
                continue
            if slash_count == 1:
                entries.append(_Entry(**base, vat_value=inn, ru_type="INN"))
                entries.append(_Entry(**base, vat_value=kpp, ru_type="KPP"))
                ru_precleaning.append(
                    {**base, "vat_number_original": m.VATNumber.strip().upper(), "inn_cleaned": inn,
                     "kpp_cleaned": kpp, "reason": "RU Split: INN -> RU1, KPP -> RU3"}
                )
                continue
            working = inn
            ru_precleaning.append(
                {**base, "vat_number_original": m.VATNumber.strip().upper(), "inn_cleaned": inn,
                 "kpp_cleaned": "", "reason": "RU pre-cleaning: INN only"}
            )

        entries.append(_Entry(**base, vat_value=working, ru_type=None))

    # Stage 2: syntax check (junk detection) - every entry, including both
    # halves of a split RU compound value.
    valid_entries: list[_Entry] = []
    for e in entries:
        vat_raw = e["vat_value"]
        vat_clean = clean_tax_number(vat_raw, country=e["country_code"] or "")
        alnum = _STRIP_NON_ALNUM_RE.sub("", vat_clean)

        reason = None
        if len(alnum) < 5:
            reason = "Too Short (< 5 chars)"
        elif len(alnum) > 20:
            reason = "Too Long (> 20 chars)"
        elif set(alnum) == {"0"}:
            reason = "Placeholder (nur Nullen)"
        elif any(tok in vat_raw for tok in _PLACEHOLDER_TOKENS):
            reason = "Contains Invalid Characters/Placeholders"

        if reason:
            junk.append({**{k: e[k] for k in ("id_party", "company_name", "is_organisation", "is_individual", "is_inactive", "country_code")},
                         "vat_number": vat_raw, "reason": reason, "rule_used": ""})
        else:
            valid_entries.append(e)

    # Stage 3: pattern validation against the per-country VAT_RULES table.
    for e in valid_entries:
        cc = (e["country_code"] or "").strip().upper()
        vat_clean = clean_tax_number(e["vat_value"], country=cc)

        if e["ru_type"] == "KPP":
            kpp_digits = re.sub(r"[^0-9]", "", vat_clean)
            if not re.match(r"^[0-9]{9}$", kpp_digits):
                junk.append({**{k: e[k] for k in ("id_party", "company_name", "is_organisation", "is_individual", "is_inactive", "country_code")},
                             "vat_number": e["vat_value"], "reason": "RU KPP: Invalid format (expected 9 digits)", "rule_used": "RU3"})
            continue

        prefix = _STRIP_NON_ALNUM_RE.sub("", vat_clean)[:2]
        validation_string = vat_clean
        if prefix in VAT_RULES:
            rule_country = prefix
        elif cc in VAT_RULES:
            rule_country = cc
            if not vat_clean.startswith(cc):
                if cc == "CH" and vat_clean.startswith("CHE"):
                    pass
                else:
                    validation_string = cc + vat_clean
        else:
            continue

        if rule_country == "NO":
            if not validation_string.startswith("NO"):
                validation_string = "NO" + re.sub(r"[^0-9A-Z]", "", validation_string)
            core = validation_string[2:]
            if re.match(r"^\d{9}$", core):
                validation_string = "NO" + core + "MVA"

        pattern = VAT_RULES.get(rule_country)
        if pattern and not re.match(pattern, validation_string):
            msg_type = "Prefix" if rule_country == prefix else "CountryCol"
            junk.append({**{k: e[k] for k in ("id_party", "company_name", "is_organisation", "is_individual", "is_inactive", "country_code")},
                         "vat_number": e["vat_value"], "reason": f"Pattern Mismatch ({msg_type} Rule)", "rule_used": rule_country})

    junk_ids = {j["id_party"] for j in junk}
    empty_ids = {m.IDParty for m in mandanten if _is_clean(m.VATNumber)}
    rows = [{"IDParty": m.IDParty, "IsOrganisation": m.IsOrganisation, "IsIndividual": m.IsIndividual} for m in mandanten]
    quality_report = compute_quality_report(rows, junk_ids, empty_ids, optional_field=True)

    return {
        "vies_backfilled": vies_backfilled,
        "ru_precleaning": ru_precleaning,
        "junk": junk,
        "quality_report": quality_report,
    }


async def run_vat_duplicate_check(db: AsyncSession, project_id: uuid.UUID) -> list[dict]:
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())

    by_clean: dict[str, list[Mandant]] = {}
    for m in mandanten:
        if _is_clean(getattr(m, MANDANT_VAT_COL)):
            continue
        clean = re.sub(r"[^A-Z0-9]", "", m.VATNumber.upper())
        if len(clean) <= 5:
            continue
        by_clean.setdefault(clean, []).append(m)

    dupes = []
    for clean, group in sorted(by_clean.items()):
        if len(group) < 2:
            continue
        for m in group:
            dupes.append({"id_party": m.IDParty, "company_name": m.CompanyName, "vat_number": m.VATNumber})
    return dupes


# ─────────────────────────────────────────────────────────────────────────
# FISCAL_RULES: per-project, editable country/entity-type FiscalCode rules
# ─────────────────────────────────────────────────────────────────────────


async def _seed_fiscal_rules(db: AsyncSession, project_id: uuid.UUID) -> None:
    for country, entities in FISCAL_RULES_SEED.items():
        for entity_type, rule in entities.items():
            desc = rule.get("desc", "")
            if "[LOW confidence]" in desc:
                confidence = "LOW"
            elif "[MEDIUM confidence]" in desc:
                confidence = "MEDIUM"
            else:
                confidence = "HIGH"
            db.add(
                FiscalRule(
                    project_id=project_id,
                    CountryCode=country,
                    EntityType=entity_type,
                    SapCode=rule.get("sap_code", ""),
                    Regex=rule.get("regex", r"^.+$"),
                    RegexAliases=rule.get("aliases", []),
                    Description=desc,
                    SourceUrl=rule.get("source", ""),
                    Confidence=confidence,
                )
            )
    await db.commit()


async def ensure_fiscal_rules(db: AsyncSession, project_id: uuid.UUID) -> None:
    """Seeds this project's rules from FISCAL_RULES_SEED the first time
    they're needed - mirrors the original's lazy ensure_fiscal_rules_table."""
    count = (
        await db.execute(select(func.count()).select_from(FiscalRule).where(FiscalRule.project_id == project_id))
    ).scalar_one()
    if count == 0:
        await _seed_fiscal_rules(db, project_id)


async def list_fiscal_rules(db: AsyncSession, project_id: uuid.UUID) -> list[FiscalRule]:
    await ensure_fiscal_rules(db, project_id)
    result = await db.execute(
        select(FiscalRule).where(FiscalRule.project_id == project_id).order_by(FiscalRule.CountryCode, FiscalRule.EntityType)
    )
    return list(result.scalars().all())


async def upsert_fiscal_rules(db: AsyncSession, project_id: uuid.UUID, rules: list[dict]) -> int:
    """Adds or updates rules by (country_code, entity_type) - mirrors the
    Regelwerk editor's "Aenderungen speichern" upsert. A rule dict:
    country_code, entity_type, sap_code, regex, aliases, description,
    source_url, confidence."""
    await ensure_fiscal_rules(db, project_id)
    existing_result = await db.execute(select(FiscalRule).where(FiscalRule.project_id == project_id))
    existing = {(r.CountryCode, r.EntityType): r for r in existing_result.scalars().all()}

    saved = 0
    for r in rules:
        cc = (r.get("country_code") or "").strip().upper()
        et = (r.get("entity_type") or "").strip().upper()
        if not cc or not et:
            continue
        row = existing.get((cc, et))
        if row is None:
            row = FiscalRule(project_id=project_id, CountryCode=cc, EntityType=et)
            db.add(row)
            existing[(cc, et)] = row
        row.SapCode = r.get("sap_code") or ""
        row.Regex = r.get("regex") or r"^.+$"
        row.RegexAliases = r.get("aliases") or []
        row.Description = r.get("description") or ""
        row.SourceUrl = r.get("source_url") or ""
        row.Confidence = r.get("confidence") or "HIGH"
        saved += 1

    await db.commit()
    return saved


async def reset_fiscal_rules(db: AsyncSession, project_id: uuid.UUID) -> int:
    await db.execute(delete(FiscalRule).where(FiscalRule.project_id == project_id))
    await db.commit()
    await _seed_fiscal_rules(db, project_id)
    result = await db.execute(
        select(func.count()).select_from(FiscalRule).where(FiscalRule.project_id == project_id)
    )
    return result.scalar_one()


# ─────────────────────────────────────────────────────────────────────────
# Fiscal Code (Steuernummer) analysis: 2-stage syntax + pattern check
# against this project's FiscalRule table.
# ─────────────────────────────────────────────────────────────────────────

_TRUE_STRINGS = ("1", "1.0", "true", "True")


async def run_fiscal_code_analysis(db: AsyncSession, project_id: uuid.UUID) -> dict:
    await ensure_fiscal_rules(db, project_id)
    rules_result = await db.execute(select(FiscalRule).where(FiscalRule.project_id == project_id))
    rules_by_country: dict[str, dict[str, FiscalRule]] = {}
    for r in rules_result.scalars().all():
        rules_by_country.setdefault(r.CountryCode, {})[r.EntityType] = r

    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())

    junk: list[dict] = []
    valid_entries: list[tuple[Mandant, str, str]] = []

    for m in mandanten:
        if _is_clean(m.FiscalCode):
            continue
        fc_raw = m.FiscalCode.strip().upper()
        cc = (m.CountryCode or "").strip().upper()
        fc_clean = re.sub(r"[^A-Z0-9]", "", clean_tax_number(fc_raw, country=cc))

        reason = None
        if len(fc_clean) < 5:
            reason = "Too Short (< 5 chars)"
        elif len(fc_clean) > 20:
            reason = "Too Long (> 20 chars)"
        elif set(fc_clean) == {"0"}:
            reason = "Placeholder (nur Nullen)"
        elif any(tok in fc_raw for tok in _PLACEHOLDER_TOKENS):
            reason = "Contains Invalid Characters/Placeholders"

        if reason:
            junk.append({**_base_fields(m), "fiscal_code": fc_raw, "reason": reason, "allowed_pattern": ""})
            continue
        valid_entries.append((m, fc_clean, cc))

    for m, clean_code, cc in valid_entries:
        if not cc or cc not in rules_by_country:
            continue
        is_org = str(m.IsOrganisation or "").strip() in _TRUE_STRINGS
        is_ind = str(m.IsIndividual or "").strip() in _TRUE_STRINGS
        entity_type = "ORG" if is_org else ("IND" if is_ind else "GENERIC")
        rule = rules_by_country[cc].get(entity_type)
        if rule is None:
            continue

        primary_ok = bool(re.match(rule.Regex, clean_code))
        alias_ok = any(re.match(alt, clean_code) for alt in (rule.RegexAliases or []))
        if not (primary_ok or alias_ok):
            reason = "Leer nach Bereinigung" if len(clean_code) == 0 else f"Ungueltiges Pattern (Erwartet: {rule.Description})"
            junk.append(
                {**_base_fields(m), "fiscal_code": m.FiscalCode.strip().upper(), "reason": reason, "allowed_pattern": rule.Regex}
            )

    junk_ids = {j["id_party"] for j in junk}
    empty_ids = {m.IDParty for m in mandanten if _is_clean(m.FiscalCode)}
    rows = [{"IDParty": m.IDParty, "IsOrganisation": m.IsOrganisation, "IsIndividual": m.IsIndividual} for m in mandanten]
    quality_report = compute_quality_report(rows, junk_ids, empty_ids, optional_field=True)

    return {"junk": junk, "quality_report": quality_report}


# ─────────────────────────────────────────────────────────────────────────
# VAT_MAPPING: editable country -> TAXTYPE table for the VAT migration track
# ─────────────────────────────────────────────────────────────────────────


async def ensure_vat_mapping(db: AsyncSession, project_id: uuid.UUID) -> None:
    count = (
        await db.execute(select(func.count()).select_from(VatMapping).where(VatMapping.project_id == project_id))
    ).scalar_one()
    if count == 0:
        for entry in VAT_MAPPING_SEED:
            db.add(VatMapping(project_id=project_id, SapCode=entry["Code"], Region=entry["Region"]))
        await db.commit()


async def list_vat_mapping(db: AsyncSession, project_id: uuid.UUID) -> list[VatMapping]:
    await ensure_vat_mapping(db, project_id)
    result = await db.execute(select(VatMapping).where(VatMapping.project_id == project_id).order_by(VatMapping.SapCode))
    return list(result.scalars().all())


async def save_vat_mapping(db: AsyncSession, project_id: uuid.UUID, entries: list[dict]) -> int:
    await db.execute(delete(VatMapping).where(VatMapping.project_id == project_id))
    saved = 0
    for e in entries:
        code = (e.get("code") or "").strip().upper()
        if not code:
            continue
        region = e.get("region") or "Non-EU"
        if region not in ("EU / Europe", "Non-EU"):
            region = "Non-EU"
        db.add(VatMapping(project_id=project_id, SapCode=code, Region=region))
        saved += 1
    await db.commit()
    return saved


async def reset_vat_mapping(db: AsyncSession, project_id: uuid.UUID) -> int:
    await db.execute(delete(VatMapping).where(VatMapping.project_id == project_id))
    await db.commit()
    await ensure_vat_mapping(db, project_id)
    result = await db.execute(select(func.count()).select_from(VatMapping).where(VatMapping.project_id == project_id))
    return result.scalar_one()


# ─────────────────────────────────────────────────────────────────────────
# Migration result persistence + the two migration tracks (VAT, Steuernummer)
# ─────────────────────────────────────────────────────────────────────────


def _migration_row(id_party: str, value: str, taxtype: str, country_code: str | None) -> dict:
    value = value or ""
    return {
        "IDParty": id_party,
        "SourceValue": value,
        "TAXTYPE": taxtype,
        "TAXNUML": value if len(value) <= 20 else None,
        "TAXNUMXL": value if len(value) > 20 else None,
        "CountryCode": country_code,
    }


async def _save_tax_migration_result(
    db: AsyncSession, project_id: uuid.UUID, migration_type: str, rows: list[dict]
) -> None:
    """Full replace of this migration type's rows - the other track's rows
    (VAT vs STEUERNUMMER) are untouched, matching save_tax_migration_result."""
    await db.execute(
        delete(TaxMigrationResult).where(
            TaxMigrationResult.project_id == project_id, TaxMigrationResult.Migration == migration_type
        )
    )
    for r in rows:
        db.add(TaxMigrationResult(project_id=project_id, Migration=migration_type, **r))
    await db.commit()


def _assign_ca_code(vat_value: str) -> tuple[str | None, str]:
    """Canada: RT-suffixed accounts (GST/HST) keep the full number under
    CA1; RC/RP/other R[A-Z] accounts and bare 9-digit Business Numbers
    reduce to their 9-digit BN under CA2."""
    v = re.sub(r"[^A-Z0-9]", "", clean_tax_number(vat_value, country="CA"))
    digits = re.sub(r"\D", "", v)
    if re.search(r"RT\d{4}", v) and len(digits) >= 9:
        return ("CA1", v)
    if re.search(r"R[A-Z]\d{4}", v) and len(digits) >= 9:
        return ("CA2", digits[:9])
    if len(digits) == 9:
        return ("CA2", digits)
    return (None, v)


async def run_vat_migration(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Builds the VAT-track rows of TaxMigrationResult: excludes the VAT
    junk population (recomputed fresh via run_vat_analysis, rather than
    depending on a persisted junk table from a possibly-stale prior run -
    see module docstring's stateless-checks note), applies CH/NO/RU
    pre-cleaning, resolves a TAXTYPE from VatMapping (RU always splits
    into RU1/RU3 regardless of the mapping table; CA is pattern-assigned
    via _assign_ca_code), and computes TAXNUML/TAXNUMXL by length."""
    analysis = await run_vat_analysis(db, project_id)
    junk_ids = {j["id_party"] for j in analysis["junk"]}

    mapping_rows = await list_vat_mapping(db, project_id)
    country_to_code = {m.SapCode[:2]: m.SapCode for m in mapping_rows if m.SapCode[:2] not in ("CA", "RU")}

    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())

    rows: list[dict] = []
    empty_removed = 0
    for m in mandanten:
        if m.IDParty in junk_ids:
            continue
        if _is_clean(m.VATNumber):
            empty_removed += 1
            continue
        cc = (m.CountryCode or "").strip().upper()
        vat = m.VATNumber.strip().upper()

        if cc == "CH":
            vat = clean_swiss_vat(vat)
        elif cc == "NO":
            vat = clean_norwegian_vat(vat)

        if cc == "RU":
            inn, kpp, slash_count = split_russian_tax_number(vat)
            rows.append(_migration_row(m.IDParty, inn, "RU1", cc))
            if slash_count == 1:
                rows.append(_migration_row(m.IDParty, kpp, "RU3", cc))
            continue

        if cc == "CA":
            code, value = _assign_ca_code(vat)
            if code:
                rows.append(_migration_row(m.IDParty, value, code, cc))
            continue

        code = country_to_code.get(cc)
        if not code:
            continue
        rows.append(_migration_row(m.IDParty, vat, code, cc))

    await _save_tax_migration_result(db, project_id, "VAT", rows)
    await apply_taxtype_remap(db, project_id)
    await apply_taxtype_row_fixes(db, project_id)
    validation = await run_taxtype_validation(db, project_id)

    return {
        "total_raw": len(mandanten),
        "total_junk_removed": len(junk_ids),
        "total_empty_removed": empty_removed,
        "migrated": len(rows),
        "validation": validation,
    }


async def run_steuer_migration(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Builds the STEUERNUMMER-track rows of TaxMigrationResult: excludes
    the FiscalCode junk population (recomputed fresh, same reasoning as
    run_vat_migration), resolves a TAXTYPE from this project's FiscalRule
    table by (country, entity_type).sap_code, and computes TAXNUML/TAXNUMXL."""
    fiscal_analysis = await run_fiscal_code_analysis(db, project_id)
    junk_ids = {j["id_party"] for j in fiscal_analysis["junk"]}

    await ensure_fiscal_rules(db, project_id)
    rules_result = await db.execute(select(FiscalRule).where(FiscalRule.project_id == project_id))
    sap_code_by_key = {(r.CountryCode, r.EntityType): r.SapCode for r in rules_result.scalars().all()}

    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())

    rows: list[dict] = []
    empty_removed = 0
    for m in mandanten:
        if m.IDParty in junk_ids:
            continue
        if _is_clean(m.FiscalCode):
            empty_removed += 1
            continue
        cc = (m.CountryCode or "").strip().upper()
        is_org = str(m.IsOrganisation or "").strip() in _TRUE_STRINGS
        is_ind = str(m.IsIndividual or "").strip() in _TRUE_STRINGS
        entity_type = "ORG" if is_org else ("IND" if is_ind else "GENERIC")
        sap_code = sap_code_by_key.get((cc, entity_type))
        if not sap_code:
            continue
        clean_fc = re.sub(r"[/\-.,^\s]", "", m.FiscalCode.strip().upper())
        rows.append(_migration_row(m.IDParty, clean_fc, sap_code, cc))

    await _save_tax_migration_result(db, project_id, "STEUERNUMMER", rows)
    await apply_taxtype_remap(db, project_id)
    await apply_taxtype_row_fixes(db, project_id)
    validation = await run_taxtype_validation(db, project_id)

    return {
        "total_raw": len(mandanten),
        "total_junk_removed": len(junk_ids),
        "total_empty_removed": empty_removed,
        "migrated": len(rows),
        "validation": validation,
    }


# ─────────────────────────────────────────────────────────────────────────
# TAXTYPE validation against the official SAP_TAX_CATEGORIES reference
# ─────────────────────────────────────────────────────────────────────────


async def run_taxtype_validation(db: AsyncSession, project_id: uuid.UUID) -> dict:
    result = await db.execute(select(TaxMigrationResult).where(TaxMigrationResult.project_id == project_id))
    tax_rows = list(result.scalars().all())
    if not tax_rows:
        return {"error": "No migration result yet - run the VAT or Steuernummer migration first."}

    known = {c for c, _n, _d in SAP_TAX_CATEGORIES}
    desc_map = {c: d for c, _n, d in SAP_TAX_CATEGORIES}
    vat_cats: dict[str, set[str]] = {}
    for code, _country, desc in SAP_TAX_CATEGORIES:
        if "Umsatzsteuer-Id" in desc:
            vat_cats.setdefault(code[:2], set()).add(code)

    key_counts: dict[tuple[str, str], int] = {}
    for r in tax_rows:
        key = ((r.IDParty or "").strip(), (r.TAXTYPE or "").strip().upper())
        key_counts[key] = key_counts.get(key, 0) + 1

    findings = []
    counts = {"unknown": 0, "obsolete": 0, "mismatch": 0, "vat_hint": 0, "collision": 0}
    for r in tax_rows:
        taxtype = (r.TAXTYPE or "").strip().upper()
        cc = (r.CountryCode or "").strip().upper()
        is_unknown = taxtype not in known
        is_obsolete = taxtype in OBSOLETE_CATEGORIES
        is_mismatch = (not is_unknown) and (not is_obsolete) and cc != "" and taxtype[:2] != cc
        is_vat_hint = (
            (not is_unknown) and (r.Migration or "").upper() == "VAT" and cc in vat_cats and taxtype not in vat_cats[cc]
        )
        is_collision = key_counts.get(((r.IDParty or "").strip(), taxtype), 0) > 1

        labels = []
        if is_unknown:
            labels.append("UNKNOWN")
            counts["unknown"] += 1
        if is_obsolete:
            labels.append("OBSOLETE")
            counts["obsolete"] += 1
        if is_mismatch:
            labels.append("COUNTRY_MISMATCH")
            counts["mismatch"] += 1
        if is_vat_hint:
            labels.append("VAT_CATEGORY_HINT")
            counts["vat_hint"] += 1
        if is_collision:
            labels.append("KEY_COLLISION")
            counts["collision"] += 1

        for label in labels:
            findings.append(
                {
                    "migration": r.Migration,
                    "id_party": r.IDParty,
                    "source_value": r.SourceValue,
                    "taxtype": r.TAXTYPE,
                    "country_code": r.CountryCode,
                    "finding": label,
                    "sap_description": desc_map.get(taxtype, ""),
                }
            )

    return {"total": len(tax_rows), **counts, "findings": findings[:500]}


def suggest_collision_code(country_code: str, current_code: str, migration: str) -> str | None:
    """A sensible resolution for a KEY_COLLISION finding: for VAT rows, the
    country's official VAT-ID category; for STEUERNUMMER rows, a non-VAT
    category (preferring one whose description mentions "Steuer"). None
    means no suggestion is available - leave the row as-is."""
    cats = [(c, d) for c, _n, d in SAP_TAX_CATEGORIES if c[:2] == country_code and c not in OBSOLETE_CATEGORIES]
    desc_by_code = dict(cats)
    vat_set = {c for c, d in desc_by_code.items() if "Umsatzsteuer-Id" in d}
    if migration.upper() == "VAT":
        candidates = sorted(c for c in vat_set if c != current_code)
        return candidates[0] if candidates else None
    candidates = sorted(c for c in desc_by_code if c not in vat_set and c != current_code)
    preferred = [c for c in candidates if "steuer" in desc_by_code[c].lower()]
    ranked = preferred or candidates
    return ranked[0] if ranked else None


# ─────────────────────────────────────────────────────────────────────────
# TAXTYPE_REMAP: global source -> target code correction, re-applied on
# every migration run
# ─────────────────────────────────────────────────────────────────────────


async def list_taxtype_remaps(db: AsyncSession, project_id: uuid.UUID) -> list[TaxtypeRemap]:
    result = await db.execute(select(TaxtypeRemap).where(TaxtypeRemap.project_id == project_id).order_by(TaxtypeRemap.SourceCode))
    return list(result.scalars().all())


async def save_taxtype_remap_entry(db: AsyncSession, project_id: uuid.UUID, source_code: str, target_code: str) -> None:
    source_code = source_code.strip().upper()
    target_code = target_code.strip().upper()
    existing = (
        await db.execute(
            select(TaxtypeRemap).where(TaxtypeRemap.project_id == project_id, TaxtypeRemap.SourceCode == source_code)
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(TaxtypeRemap(project_id=project_id, SourceCode=source_code, TargetCode=target_code))
    else:
        existing.TargetCode = target_code
    await db.commit()


async def delete_taxtype_remaps(db: AsyncSession, project_id: uuid.UUID, source_codes: list[str]) -> int:
    codes = [c.strip().upper() for c in source_codes]
    result = await db.execute(
        delete(TaxtypeRemap).where(TaxtypeRemap.project_id == project_id, TaxtypeRemap.SourceCode.in_(codes))
    )
    await db.commit()
    return result.rowcount or 0


async def apply_taxtype_remap(db: AsyncSession, project_id: uuid.UUID) -> dict:
    remaps_result = await db.execute(select(TaxtypeRemap).where(TaxtypeRemap.project_id == project_id))
    remaps = {r.SourceCode: r.TargetCode for r in remaps_result.scalars().all()}
    if not remaps:
        return {"applied": 0}

    tax_result = await db.execute(select(TaxMigrationResult).where(TaxMigrationResult.project_id == project_id))
    applied = 0
    for row in tax_result.scalars().all():
        target = remaps.get((row.TAXTYPE or "").strip().upper())
        if target:
            row.TAXTYPE = target
            applied += 1
    if applied:
        await db.commit()
    return {"applied": applied}


# ─────────────────────────────────────────────────────────────────────────
# TAXTYPE_ROW_FIX: row-level TAXTYPE correction (one specific IDParty +
# Migration + source code), re-applied on every migration run
# ─────────────────────────────────────────────────────────────────────────


async def list_taxtype_row_fixes(db: AsyncSession, project_id: uuid.UUID) -> list[TaxtypeRowFix]:
    result = await db.execute(
        select(TaxtypeRowFix).where(TaxtypeRowFix.project_id == project_id).order_by(TaxtypeRowFix.IDParty)
    )
    return list(result.scalars().all())


async def save_taxtype_row_fix_entry(
    db: AsyncSession, project_id: uuid.UUID, id_party: str, migration: str, source_code: str, target_code: str
) -> None:
    id_party = id_party.strip()
    migration = migration.strip().upper()
    source_code = source_code.strip().upper()
    target_code = target_code.strip().upper()
    existing = (
        await db.execute(
            select(TaxtypeRowFix).where(
                TaxtypeRowFix.project_id == project_id,
                TaxtypeRowFix.IDParty == id_party,
                TaxtypeRowFix.Migration == migration,
                TaxtypeRowFix.SourceCode == source_code,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            TaxtypeRowFix(
                project_id=project_id, IDParty=id_party, Migration=migration, SourceCode=source_code, TargetCode=target_code
            )
        )
    else:
        existing.TargetCode = target_code
    await db.commit()


async def delete_taxtype_row_fixes(db: AsyncSession, project_id: uuid.UUID, keys: list[tuple[str, str, str]]) -> int:
    deleted = 0
    for id_party, migration, source_code in keys:
        result = await db.execute(
            delete(TaxtypeRowFix).where(
                TaxtypeRowFix.project_id == project_id,
                TaxtypeRowFix.IDParty == id_party.strip(),
                TaxtypeRowFix.Migration == migration.strip().upper(),
                TaxtypeRowFix.SourceCode == source_code.strip().upper(),
            )
        )
        deleted += result.rowcount or 0
    await db.commit()
    return deleted


async def apply_taxtype_row_fixes(db: AsyncSession, project_id: uuid.UUID) -> dict:
    fixes = await list_taxtype_row_fixes(db, project_id)
    if not fixes:
        return {"applied": 0}

    tax_result = await db.execute(select(TaxMigrationResult).where(TaxMigrationResult.project_id == project_id))
    by_key: dict[tuple[str, str, str], list[TaxMigrationResult]] = {}
    for row in tax_result.scalars().all():
        key = ((row.IDParty or "").strip(), (row.Migration or "").strip().upper(), (row.TAXTYPE or "").strip().upper())
        by_key.setdefault(key, []).append(row)

    applied = 0
    for fix in fixes:
        for row in by_key.get((fix.IDParty, fix.Migration, fix.SourceCode), []):
            row.TAXTYPE = fix.TargetCode
            applied += 1
    if applied:
        await db.commit()
    return {"applied": applied}
