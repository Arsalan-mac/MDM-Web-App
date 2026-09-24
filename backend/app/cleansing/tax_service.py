"""Tax Cleansing - Phase A: VAT-Cleansing tab only (unified VAT analysis,
duplicate check, quality report). Ported from tax_cleansing_module.py's
run_unified_vat_analysis / run_vat_duplicate_analysis / _run_vat_summary_report.

Fiscal Code (Steuernummer-Cleansing) and Migration Preparation are separate,
larger follow-up phases - see docs/ROADMAP.md.
"""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.constants import MANDANT_VAT_COL
from app.cleansing.quality_report import compute_quality_report
from app.cleansing.vat_rules import VAT_RULES, clean_norwegian_vat, clean_swiss_vat, clean_tax_number, split_russian_tax_number
from app.models.tenant import Mandant

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
