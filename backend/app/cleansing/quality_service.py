"""Quality Analysis: a set of independent, read-mostly data-quality checks
over Mandanten (and one over Auftraege). Ported from app_analysis_ui and its
BLOCK 5-10 helper functions in 2202MandantenCleansing.py.

Unlike Address Cleansing, none of these checks have a persistent "Nacharbeit"
review/accept workflow in the original app - each is a "run it, look at the
result, optionally download it" utility. So nothing here is persisted to its
own results table; every check recomputes and returns its result on each
call, and the frontend just displays whatever the last call returned. The
original's local-Excel-file exports (save_to_local_drive, DQ_Quality_Report.
xlsx) have no equivalent in a multi-tenant cloud backend and aren't ported,
consistent with every other stage's deferral of Excel export so far.

Missing ID (Mandanten ohne IDParty) is NOT ported: IDParty is Mandant's NOT
NULL primary key column here (see app/models/tenant.py), so a Mandant row
with no IDParty cannot exist in this schema in the first place - the check
would always return zero, unlike the original's schema-less SQLite table
which allowed it.
"""

import re
import uuid

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.quality_report import compute_quality_report
from app.cleansing.register_checks import register_number_issues
from app.models.tenant import Auftrag, Mandant

try:
    from email_validator import EmailNotValidError, validate_email

    _EMAIL_VALIDATOR_AVAILABLE = True
except ImportError:  # pragma: no cover - always installed, mirrors original's fallback
    _EMAIL_VALIDATOR_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neighbors import NearestNeighbors

    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SKLEARN_AVAILABLE = False


def _is_clean(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none", "na", "<na>", "nat")


_SYSTEM_MANDANT_FIELDS = {"project_id", "IDParty", "extra", "SapOverridden", "Load_Date", "Source_FILE", "Change_Reason"}
_TEXT_MANDANT_FIELDS = [c.name for c in Mandant.__table__.columns if c.name not in _SYSTEM_MANDANT_FIELDS]


# ─────────────────────────────────────────────────────────────────────────
# DB-Bereinigung: replace known junk values with empty (Mandanten only - the
# original always calls this with MANDANT_TABLE_NAME hardcoded despite its
# generic-looking signature, so scoping it to Mandant isn't a narrowing).
# ─────────────────────────────────────────────────────────────────────────


async def run_value_cleanup(db: AsyncSession, project_id: uuid.UUID, bad_values: list[str]) -> dict:
    targets = {v.strip() for v in bad_values if v.strip()}
    if not targets:
        return {"cleared": 0}

    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())

    cleared = 0
    for m in mandanten:
        for field in _TEXT_MANDANT_FIELDS:
            val = getattr(m, field)
            if val is not None and str(val) in targets:
                setattr(m, field, "")
                cleared += 1
        if m.extra:
            new_extra = dict(m.extra)
            changed = False
            for k, v in new_extra.items():
                if v is not None and str(v) in targets:
                    new_extra[k] = ""
                    changed = True
                    cleared += 1
            if changed:
                m.extra = new_extra

    await db.commit()
    return {"cleared": cleared}


# ─────────────────────────────────────────────────────────────────────────
# Fuzzy duplicate check: TF-IDF + Nearest Neighbors, sub-blocked by country
# and (for large countries) ZIP-code prefix. Ported as closely as possible
# to the original's algorithm; runs synchronously in the request like every
# other check here - fine for the dataset sizes this has been tested
# against, a known scaling limit for very large tenants (same caveat as
# Name Splitting's synchronous LLM call).
# ─────────────────────────────────────────────────────────────────────────


async def run_fuzzy_duplicate_check(db: AsyncSession, project_id: uuid.UUID) -> list[dict]:
    if not _SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn is not installed on the backend.")

    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())
    if not mandanten:
        return []

    df = pd.DataFrame(
        [
            {
                "IDParty": m.IDParty,
                "CompanyName": (m.CompanyName or "").lower().strip(),
                "Address": (m.Address or "").lower().strip(),
                "City": (m.City or "").lower().strip(),
                "ZipCode": (m.ZipCode or "").lower().strip(),
                "CountryCode": (m.CountryCode or "").upper().strip(),
                "VAT_NORM": (m.VATNumber or "").upper().strip(),
                "IsInactive": (m.IsInactive or "").replace(".0", ""),
                "UserCode_Kummerer": m.UserCode_Kummerer,
            }
            for m in mandanten
        ]
    )
    df["soup"] = df["CompanyName"] + " " + df["CompanyName"] + " " + df["ZipCode"] + " " + df["City"] + " " + df["Address"]

    countries = df["CountryCode"].value_counts()
    relevant = countries[countries > 1].index.tolist()

    all_matches = []
    for cc in relevant:
        dfl = df[df["CountryCode"] == cc]
        if len(dfl) > 5000:
            blocks = []
            bk = dfl["ZipCode"].str[0].replace("", "0")
            for _, b in dfl.groupby(bk):
                if len(b) > 1:
                    blocks.append(b)
        else:
            blocks = [dfl]

        for block in blocks:
            if len(block) < 2:
                continue
            try:
                vec = TfidfVectorizer(
                    analyzer="word" if len(block) > 20000 else "char_wb", ngram_range=(2, 3), min_df=1
                )
                mat = vec.fit_transform(block["soup"])
                nbrs = NearestNeighbors(n_neighbors=min(len(block), 5), metric="cosine", n_jobs=-1).fit(mat)
                dists, inds = nbrs.kneighbors(mat)
                rows_idx, cols_idx = np.where(dists[:, 1:] < 0.5)
                cols_idx += 1
                for r, c in zip(rows_idx, cols_idx):
                    idx_i, idx_j = inds[r, 0], inds[r, c]
                    if idx_i >= idx_j:
                        continue
                    row_i = block.iloc[idx_i]
                    row_j = block.iloc[idx_j]
                    if row_i["VAT_NORM"] and row_j["VAT_NORM"] and row_i["VAT_NORM"] == row_j["VAT_NORM"]:
                        continue
                    sim = (1 - dists[r, c]) * 100
                    if sim >= 85:
                        category = "Very High Likelihood"
                    elif sim >= 70:
                        category = "High Likelihood"
                    elif sim >= 50:
                        category = "Some Likelihood"
                    else:
                        category = "Low Likelihood"
                    all_matches.append(
                        {
                            "id_party_i": row_i["IDParty"], "is_inactive_i": row_i["IsInactive"],
                            "company_name_i": row_i["CompanyName"], "address_i": row_i["Address"],
                            "city_i": row_i["City"], "zip_code_i": row_i["ZipCode"],
                            "usercode_kummerer_i": row_i["UserCode_Kummerer"],
                            "id_party_j": row_j["IDParty"], "is_inactive_j": row_j["IsInactive"],
                            "company_name_j": row_j["CompanyName"], "address_j": row_j["Address"],
                            "city_j": row_j["City"], "zip_code_j": row_j["ZipCode"],
                            "usercode_kummerer_j": row_j["UserCode_Kummerer"],
                            "country_code": cc, "similarity_pct": round(float(sim), 2),
                            "category": category,
                        }
                    )
            except Exception:
                continue

    all_matches.sort(key=lambda m: m["similarity_pct"], reverse=True)
    return all_matches[:500]


# ─────────────────────────────────────────────────────────────────────────
# Register-Nr. check (detection only - standardization lives in the future
# RegisterNumber Cleansing stage)
# ─────────────────────────────────────────────────────────────────────────


async def run_register_number_check(db: AsyncSession, project_id: uuid.UUID) -> dict:
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())
    if not mandanten:
        return {"junk": [], "quality_report": []}

    junk = []
    junk_ids = set()
    empty_ids = set()
    for m in mandanten:
        if _is_clean(m.RegisterNumber):
            empty_ids.add(m.IDParty)
            continue
        reasons = register_number_issues(m.RegisterNumber)
        if reasons:
            junk_ids.add(m.IDParty)
            junk.append(
                {
                    "id_party": m.IDParty, "company_name": m.CompanyName,
                    "is_organisation": m.IsOrganisation, "is_individual": m.IsIndividual,
                    "is_inactive": m.IsInactive, "country_code": m.CountryCode,
                    "register_number": m.RegisterNumber, "register_city": m.RegisterCity,
                    "register_court_kind_code": m.RegisterCourtKindCode,
                    "reason": ", ".join(reasons),
                }
            )

    rows = [{"IDParty": m.IDParty, "IsOrganisation": m.IsOrganisation, "IsIndividual": m.IsIndividual} for m in mandanten]
    report = compute_quality_report(rows, junk_ids, empty_ids, optional_field=True)
    return {"junk": junk, "quality_report": report}


# ─────────────────────────────────────────────────────────────────────────
# Communication check: Email / Website / Phone / Fax
# ─────────────────────────────────────────────────────────────────────────

_WEBSITE_RE = re.compile(r"^(https?://)?(www\.)?([a-zA-Z0-9-]+)(\.[a-zA-Z]{2,})+.*$")


def _check_email(mandanten: list[Mandant]) -> dict:
    issues = []
    junk_ids, empty_ids = set(), set()
    for m in mandanten:
        if _is_clean(m.Email):
            empty_ids.add(m.IDParty)
            continue
        email = m.Email.strip()
        if _EMAIL_VALIDATOR_AVAILABLE:
            try:
                validate_email(email, check_deliverability=False)
            except EmailNotValidError as exc:
                junk_ids.add(m.IDParty)
                issues.append(_contact_issue(m, "invalid_value", email, str(exc)))
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            junk_ids.add(m.IDParty)
            issues.append(_contact_issue(m, "invalid_value", email, "Invalid Format (Regex)"))
    rows = [{"IDParty": m.IDParty, "IsOrganisation": m.IsOrganisation, "IsIndividual": m.IsIndividual} for m in mandanten]
    return {"issues": issues, "quality_report": compute_quality_report(rows, junk_ids, empty_ids, optional_field=True)}


def _check_website(mandanten: list[Mandant]) -> dict:
    issues = []
    junk_ids, empty_ids = set(), set()
    for m in mandanten:
        if _is_clean(m.WebSite):
            empty_ids.add(m.IDParty)
            continue
        if not _WEBSITE_RE.match(m.WebSite.strip()):
            junk_ids.add(m.IDParty)
            issues.append(_contact_issue(m, "invalid_value", m.WebSite.strip(), "Invalid URL Format"))
    rows = [{"IDParty": m.IDParty, "IsOrganisation": m.IsOrganisation, "IsIndividual": m.IsIndividual} for m in mandanten]
    return {"issues": issues, "quality_report": compute_quality_report(rows, junk_ids, empty_ids, optional_field=True)}


def _check_phone_fax(mandanten: list[Mandant], field: str, label: str) -> dict:
    issues = []
    junk_ids, empty_ids = set(), set()
    for m in mandanten:
        raw = getattr(m, field)
        if _is_clean(raw):
            empty_ids.add(m.IDParty)
            continue
        cleaned = re.sub(r"[^0-9+]", "", str(raw))
        reason = None
        if len(cleaned) < 5:
            reason = "Too Short (<5)"
        elif len(cleaned) > 20:
            reason = "Too Long (>20)"
        elif "+" in cleaned[1:]:
            reason = "Invalid Format (+ inside number)"
        if reason:
            junk_ids.add(m.IDParty)
            issues.append({**_contact_issue(m, "invalid_value", str(raw).strip(), reason), "cleaned_value": cleaned})
    rows = [{"IDParty": m.IDParty, "IsOrganisation": m.IsOrganisation, "IsIndividual": m.IsIndividual} for m in mandanten]
    return {"issues": issues, "quality_report": compute_quality_report(rows, junk_ids, empty_ids, optional_field=True)}


def _contact_issue(m: Mandant, value_key: str, value: str, reason: str) -> dict:
    return {
        "id_party": m.IDParty, "company_name": m.CompanyName,
        "is_organisation": m.IsOrganisation, "is_individual": m.IsIndividual, "is_inactive": m.IsInactive,
        value_key: value, "reason": reason,
    }


async def run_communication_check(db: AsyncSession, project_id: uuid.UUID) -> dict:
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())
    if not mandanten:
        return {"email": {"issues": [], "quality_report": []}, "website": {"issues": [], "quality_report": []},
                "phone": {"issues": [], "quality_report": []}, "fax": {"issues": [], "quality_report": []}}

    return {
        "email": _check_email(mandanten),
        "website": _check_website(mandanten),
        "phone": _check_phone_fax(mandanten, "PhoneNumber", "Phone"),
        "fax": _check_phone_fax(mandanten, "FaxNumber", "Fax"),
    }


# ─────────────────────────────────────────────────────────────────────────
# Completeness check: fill-rate per attribute, split Organisation /
# Natuerliche Person. Ported column list from the original (matches SAP
# BUT000's real field set); a column that isn't one of Mandant's typed
# fields is read from `extra` instead.
# ─────────────────────────────────────────────────────────────────────────

_COMPLETENESS_TARGET_COLS = [
    "CompanyName", "GroupName", "RoedlCompanyNumber", "FirstName", "LastName", "BirthDate",
    "IsOrganisation", "IsIndividual", "IsProtected", "IsRoedlCompany", "IsInactive", "IsPIE",
    "IsVIP", "IsInBlackList", "VATNumber", "ViesNumber", "FiscalCode", "SocialSecurityNumber",
    "PassportIDCardNumber", "RegisterNumber", "RegisterCity", "Email", "WebSite", "PhoneNumber",
    "FaxNumber", "IsExcludedFromConflictCheck", "AddedDate", "UserCode_Added", "UserCode_Kummerer",
    "Address", "City", "CountryCode", "DistrictCode", "ZipCode", "TitleCode", "AcademTitleCode",
    "SearchTerm1", "LegalFormCode", "DateFounded", "LiquidationDate", "RegisterCourtDate",
    "RegisterCourtKindCode", "Anti_Money_Laundering", "CommentForAntiMoneyLaundering", "Routing",
    "InvoiceSendingComment", "CommunicationLanguageCode", "CommunicationMobile",
    "TaxNumberCategoryCode", "TaxNumber",
]
_COMPLETENESS_FLAG_COLS = {
    "IsOrganisation", "IsIndividual", "IsProtected", "IsInactive", "IsPIE", "IsVIP",
    "IsInBlackList", "Anti_Money_Laundering", "IsExcludedFromConflictCheck",
}
_TRUE_STRINGS = {"1", "1.0", "true", "True"}


def _field_value(m: Mandant, col: str):
    if col in _TEXT_MANDANT_FIELDS:
        return getattr(m, col)
    return (m.extra or {}).get(col)


def _calculate_completeness_stats(mandanten: list[Mandant]) -> list[dict]:
    stats = []
    total_rows = len(mandanten)
    is_roedl = [str(_field_value(m, "IsRoedlCompany")) in _TRUE_STRINGS for m in mandanten]

    for col in _COMPLETENESS_TARGET_COLS:
        if col == "IsRoedlCompany":
            active = sum(is_roedl)
            stats.append({"attribute": col, "check_type": "Statusfeld", "total_rows": total_rows,
                          "count_relevant": active, "pct": None})
        elif col == "RoedlCompanyNumber":
            base_ms = [m for m, r in zip(mandanten, is_roedl) if r]
            filled = sum(1 for m in base_ms if not _is_clean(_field_value(m, col)))
            base = len(base_ms)
            stats.append({"attribute": col, "check_type": "Bedingt (IsRoedlCompany=1)", "total_rows": base,
                          "count_relevant": filled, "pct": round(filled / base * 100, 2) if base else 0})
        elif col in _COMPLETENESS_FLAG_COLS:
            active = sum(1 for m in mandanten if str(_field_value(m, col)) in _TRUE_STRINGS)
            stats.append({"attribute": col, "check_type": "Statusfeld", "total_rows": total_rows,
                          "count_relevant": active, "pct": round(active / total_rows * 100, 2) if total_rows else 0})
        else:
            filled = sum(1 for m in mandanten if not _is_clean(_field_value(m, col)))
            stats.append({"attribute": col, "check_type": "Kein Statusfeld", "total_rows": total_rows,
                          "count_relevant": filled, "pct": round(filled / total_rows * 100, 2) if total_rows else 0})
    return stats


async def run_completeness_check(db: AsyncSession, project_id: uuid.UUID) -> list[dict]:
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())
    if not mandanten:
        return []

    org = [m for m in mandanten if str(m.IsOrganisation) in _TRUE_STRINGS]
    ind = [m for m in mandanten if str(m.IsIndividual) in _TRUE_STRINGS]

    rows = []
    for typ, subset in [("Organisation", org), ("Natuerliche Person", ind)]:
        for stat in _calculate_completeness_stats(subset):
            rows.append({"type": typ, **stat})
    return rows


# ─────────────────────────────────────────────────────────────────────────
# Date standardization: DateFounded/LiquidationDate use day-first=False
# (US-style mm/dd/yyyy, matching the original's use_us_format=True for
# these two); RegisterCourtDate uses day-first=True and additionally
# requires an explicit 4-digit year before attempting a parse, to avoid
# misreading ambiguous short dates.
# ─────────────────────────────────────────────────────────────────────────

_DATE_FIELDS = {"DateFounded": True, "LiquidationDate": True, "RegisterCourtDate": False}


def _parse_date_smartly(value, *, use_us_format: bool, require_year: bool) -> str | None:
    s = "" if value is None else str(value).strip()
    if not s or s.lower() in ("nan", "nat", "none", "null"):
        return None
    if require_year and not re.search(r"(19|20)\d{2}", s):
        return None
    try:
        parsed = pd.to_datetime(s, dayfirst=not use_us_format, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


async def run_date_standardization(db: AsyncSession, project_id: uuid.UUID) -> dict:
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(result.scalars().all())

    preview = []
    updated = 0
    for m in mandanten:
        row_changes = {}
        for col, us_fmt in _DATE_FIELDS.items():
            old_val = getattr(m, col)
            if _is_clean(old_val):
                continue
            new_val = _parse_date_smartly(old_val, use_us_format=us_fmt, require_year=(col == "RegisterCourtDate"))
            if new_val and new_val != old_val:
                row_changes[col] = {"old": old_val, "new": new_val}
        if row_changes:
            for col, change in row_changes.items():
                setattr(m, col, change["new"])
            updated += len(row_changes)
            preview.append({"id_party": m.IDParty, "company_name": m.CompanyName, "changes": row_changes})

    await db.commit()
    return {"updated": updated, "preview": preview[:100]}


# ─────────────────────────────────────────────────────────────────────────
# Auftraege DQ: ID-Project check
# ─────────────────────────────────────────────────────────────────────────


async def run_auftrag_id_project_check(db: AsyncSession, project_id: uuid.UUID) -> list[dict]:
    result = await db.execute(select(Auftrag).where(Auftrag.project_id == project_id))
    auftraege = list(result.scalars().all())
    if not auftraege:
        return []

    groups: dict[tuple[str, str, str], set[str]] = {}
    for a in auftraege:
        key = ((a.IDParty or "").strip(), (a.ProjectName or "").strip(), (a.AddedDate or "").strip())
        groups.setdefault(key, set()).add((a.ServiceName or "").strip())

    flagged_keys = {key for key, services in groups.items() if len(services) > 1}
    if not flagged_keys:
        return []

    flagged = [
        {"id_party": a.IDParty, "project_name": a.ProjectName, "added_date": a.AddedDate, "service_name": a.ServiceName}
        for a in auftraege
        if ((a.IDParty or "").strip(), (a.ProjectName or "").strip(), (a.AddedDate or "").strip()) in flagged_keys
    ]
    flagged.sort(key=lambda r: (r["id_party"] or "", r["project_name"] or "", r["added_date"] or "", r["service_name"] or ""))
    return flagged
