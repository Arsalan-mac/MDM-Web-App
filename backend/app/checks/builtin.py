"""Built-in checks, registered on import (see app/checks/__init__.py).

Each one wraps existing, already-tested logic from app/cleansing/ rather
than reimplementing it - the actual rules (what makes an address junk,
what makes a register number a placeholder, ...) are untouched; only the
column-name assumptions are lifted out into role_mapping so the same logic
runs against any dataset, not just the fixed Mandanten shape.
"""

import re

from app.checks.base import CheckDefinition, FindingDraft, register_check
from app.cleansing.address_checks import check_addresses
from app.cleansing.fiscal_rules_seed import FISCAL_RULES_SEED
from app.cleansing.register_checks import register_number_issues
from app.cleansing.vat_rules import VAT_RULES, clean_norwegian_vat, clean_swiss_vat, clean_tax_number

try:
    from email_validator import EmailNotValidError, validate_email

    _EMAIL_VALIDATOR_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only if the dep is missing
    _EMAIL_VALIDATOR_AVAILABLE = False

_EMAIL_FALLBACK_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")
_WEBSITE_RE = re.compile(r"^(https?://)?([\w-]+\.)+[a-zA-Z]{2,}([/?#].*)?$")


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none", "<na>", "") else s


# ─────────────────────────────────────────────────────────────────────────
# Register number format - direct pass-through to the existing pure
# function (app/cleansing/register_checks.py), one role: the column that
# plays "register_number" in this dataset.
# ─────────────────────────────────────────────────────────────────────────


def _run_register_number(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    col = role_mapping["register_number"]
    out = []
    for i, row in enumerate(rows):
        issues = register_number_issues(row.get(col))
        if issues:
            out.append(FindingDraft(row_index=i, field=col, severity="warning", message="; ".join(issues)))
    return out


register_check(
    CheckDefinition(
        key="register_number_format",
        label="Register Number Format",
        description=(
            "Flags placeholder text, missing digits, dummy sequences, or embedded court/legal text in a "
            "company-registration-number field."
        ),
        required_roles=["register_number"],
    ),
    _run_register_number,
)


# ─────────────────────────────────────────────────────────────────────────
# Address format - adapts app/cleansing/address_checks.py::check_addresses
# (a pure dict-in/dict-out function) by translating role_mapping into the
# fixed key names it expects, then translating its output back.
# ─────────────────────────────────────────────────────────────────────────


def _run_address_format(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    address_col = role_mapping["address"]
    city_col = role_mapping.get("city")
    zip_col = role_mapping.get("postal_code")
    country_col = role_mapping.get("country_code")

    mapped_rows = [
        {
            "IDParty": str(i),
            "Address": row.get(address_col),
            "City": row.get(city_col) if city_col else None,
            "ZipCode": row.get(zip_col) if zip_col else None,
            "CountryCode": row.get(country_col) if country_col else None,
        }
        for i, row in enumerate(rows)
    ]
    results = check_addresses(mapped_rows, {}, "")

    out = []
    for rec in results:
        severity = "warning" if rec["Aktion"] == "MANUELL" else "error"
        out.append(
            FindingDraft(
                row_index=int(rec["IDParty"]),
                field=address_col,
                severity=severity,
                message=rec["Reason"],
                proposed_value=rec["Neu"] or None,
            )
        )
    return out


register_check(
    CheckDefinition(
        key="address_format",
        label="Address Format",
        description=(
            "Flags placeholder text, an embedded city/postal code, a missing house number, or legal-form/"
            "contact-info text inside a free-text address field."
        ),
        required_roles=["address"],
        optional_roles=["city", "postal_code", "country_code"],
    ),
    _run_address_format,
)


# ─────────────────────────────────────────────────────────────────────────
# Email format
# ─────────────────────────────────────────────────────────────────────────


def _run_email_format(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    col = role_mapping["email"]
    out = []
    for i, row in enumerate(rows):
        val = _clean(row.get(col))
        if not val:
            continue
        valid, reason = True, ""
        if _EMAIL_VALIDATOR_AVAILABLE:
            try:
                validate_email(val, check_deliverability=False)
            except EmailNotValidError as exc:
                valid, reason = False, str(exc)
        elif not _EMAIL_FALLBACK_RE.match(val):
            valid, reason = False, "Invalid email format"
        if not valid:
            out.append(FindingDraft(row_index=i, field=col, severity="warning", message=reason))
    return out


register_check(
    CheckDefinition(
        key="email_format",
        label="Email Format",
        description="Flags a value that isn't a syntactically valid email address. Empty values are ignored.",
        required_roles=["email"],
    ),
    _run_email_format,
)


# ─────────────────────────────────────────────────────────────────────────
# Website format
# ─────────────────────────────────────────────────────────────────────────


def _run_website_format(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    col = role_mapping["website"]
    out = []
    for i, row in enumerate(rows):
        val = _clean(row.get(col))
        if not val:
            continue
        if not _WEBSITE_RE.match(val):
            out.append(FindingDraft(row_index=i, field=col, severity="warning", message="Invalid URL format"))
    return out


register_check(
    CheckDefinition(
        key="website_format",
        label="Website Format",
        description="Flags a value that isn't a syntactically valid URL/domain. Empty values are ignored.",
        required_roles=["website"],
    ),
    _run_website_format,
)


# ─────────────────────────────────────────────────────────────────────────
# Phone/fax format
# ─────────────────────────────────────────────────────────────────────────


def _run_phone_format(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    col = role_mapping["phone"]
    out = []
    for i, row in enumerate(rows):
        raw = _clean(row.get(col))
        if not raw:
            continue
        digits = re.sub(r"[^0-9+]", "", raw)
        reason = None
        if len(digits) < 5:
            reason = "Too short (<5 digits)"
        elif len(digits) > 20:
            reason = "Too long (>20 digits)"
        elif "+" in digits[1:]:
            reason = "Invalid format (+ inside number)"
        if reason:
            out.append(FindingDraft(row_index=i, field=col, severity="warning", message=reason))
    return out


register_check(
    CheckDefinition(
        key="phone_format",
        label="Phone/Fax Format",
        description="Flags a value that's too short, too long, or has a '+' outside the leading position.",
        required_roles=["phone"],
    ),
    _run_phone_format,
)


# ─────────────────────────────────────────────────────────────────────────
# Required field completeness
# ─────────────────────────────────────────────────────────────────────────


def _run_completeness(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    cols = role_mapping["required_fields"]
    if isinstance(cols, str):
        cols = [cols]
    out = []
    for i, row in enumerate(rows):
        for col in cols:
            if not _clean(row.get(col)):
                out.append(FindingDraft(row_index=i, field=col, severity="error", message="Required field is empty"))
    return out


register_check(
    CheckDefinition(
        key="completeness",
        label="Required Field Completeness",
        description="Flags any row where one of the fields you mark as required is empty.",
        required_roles=["required_fields"],
    ),
    _run_completeness,
)


# ─────────────────────────────────────────────────────────────────────────
# Duplicate detection - TF-IDF + nearest-neighbor similarity, generalized
# from app/cleansing/quality_service.py::run_fuzzy_duplicate_check to run
# over whatever columns the user maps as "match fields" instead of a fixed
# CompanyName/Address/City/ZipCode combination.
# ─────────────────────────────────────────────────────────────────────────


def _run_duplicate_detection(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    try:
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.neighbors import NearestNeighbors
    except ImportError:
        return []

    match_cols = role_mapping["match_fields"]
    if isinstance(match_cols, str):
        match_cols = [match_cols]
    group_col = role_mapping.get("group_by")

    soups = ["  ".join(_clean(row.get(c)).lower() for c in match_cols) for row in rows]
    groups: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        key = _clean(row.get(group_col)).upper() if group_col else "__all__"
        groups.setdefault(key, []).append(i)

    out: list[FindingDraft] = []
    for indices in groups.values():
        block = [i for i in indices if soups[i].strip()]
        if len(block) < 2:
            continue
        block_soups = [soups[i] for i in block]
        try:
            vec = TfidfVectorizer(
                analyzer="word" if len(block) > 20000 else "char_wb", ngram_range=(2, 3), min_df=1
            )
            mat = vec.fit_transform(block_soups)
            nbrs = NearestNeighbors(n_neighbors=min(len(block), 5), metric="cosine", n_jobs=-1).fit(mat)
            dists, inds = nbrs.kneighbors(mat)
        except Exception:
            continue

        rows_idx, cols_idx = np.where(dists[:, 1:] < 0.5)
        cols_idx += 1
        seen_pairs = set()
        for r, c in zip(rows_idx, cols_idx):
            a, b = block[inds[r, 0]], block[inds[r, c]]
            if a == b or (min(a, b), max(a, b)) in seen_pairs:
                continue
            seen_pairs.add((min(a, b), max(a, b)))
            sim = round((1 - dists[r, c]) * 100, 1)
            if sim < 50:
                continue
            msg = f"{sim}% similar to row {b + 1}" if a < b else f"{sim}% similar to row {a + 1}"
            out.append(FindingDraft(row_index=a, field=match_cols[0], severity="info", message=msg))

    return out


# ─────────────────────────────────────────────────────────────────────────
# VAT number format - reuses the exact per-country regex table
# (app/cleansing/vat_rules.py::VAT_RULES) that Tax Cleansing's VAT phase
# uses, self-describing off the value's own country prefix when no
# separate country column is mapped (most VAT numbers start with one).
# ─────────────────────────────────────────────────────────────────────────


def _run_vat_format(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    vat_col = role_mapping["vat_number"]
    country_col = role_mapping.get("country_code")

    out = []
    for i, row in enumerate(rows):
        raw = _clean(row.get(vat_col))
        if not raw:
            continue
        cc = _clean(row.get(country_col)).upper() if country_col else ""

        cleaned = clean_tax_number(raw, country=cc)
        if cc == "CH":
            cleaned = clean_swiss_vat(cleaned)
        elif cc == "NO":
            cleaned = clean_norwegian_vat(cleaned)

        rule_country = cc if cc in VAT_RULES else (cleaned[:2] if cleaned[:2] in VAT_RULES else None)
        if rule_country is None:
            out.append(
                FindingDraft(
                    row_index=i, field=vat_col, severity="warning",
                    message=f"Unrecognized country prefix in {raw!r} - can't validate its format.",
                )
            )
            continue

        pattern = VAT_RULES[rule_country]
        if not re.match(pattern, cleaned):
            out.append(
                FindingDraft(
                    row_index=i, field=vat_col, severity="warning",
                    message=f"{raw!r} doesn't match the {rule_country} VAT number format.",
                )
            )
    return out


register_check(
    CheckDefinition(
        key="vat_format",
        label="VAT Number Format",
        description=(
            "Flags a VAT number that doesn't match its country's format, using the same per-country pattern "
            "table as Tax Cleansing. Reads the country from the value's own prefix, or from a mapped country "
            "column if you have one."
        ),
        required_roles=["vat_number"],
        optional_roles=["country_code"],
    ),
    _run_vat_format,
)


# ─────────────────────────────────────────────────────────────────────────
# Fiscal code format - reuses the per-country, per-entity-type rule table
# (app/cleansing/fiscal_rules_seed.py::FISCAL_RULES_SEED) that Tax
# Cleansing's Fiscal Code phase uses. Needs a country column since, unlike
# a VAT number, a fiscal code carries no self-describing country prefix.
# ─────────────────────────────────────────────────────────────────────────


def _run_fiscal_code_format(rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    fiscal_col = role_mapping["fiscal_code"]
    country_col = role_mapping["country_code"]
    entity_col = role_mapping.get("entity_type")

    out = []
    for i, row in enumerate(rows):
        raw = _clean(row.get(fiscal_col))
        if not raw:
            continue
        cc = _clean(row.get(country_col)).upper()
        country_rules = FISCAL_RULES_SEED.get(cc)
        if country_rules is None:
            out.append(
                FindingDraft(
                    row_index=i, field=fiscal_col, severity="warning",
                    message=f"Unrecognized country code {cc!r} - can't validate its fiscal code format.",
                )
            )
            continue

        entity = _clean(row.get(entity_col)).upper() if entity_col else "GENERIC"
        if entity not in country_rules:
            entity = "GENERIC"
        rule = country_rules.get(entity) or country_rules.get("GENERIC")
        if rule is None:
            continue

        cleaned = re.sub(r"\s+", "", raw.strip().upper())
        candidates = [rule["regex"], *rule.get("aliases", [])]
        if not any(re.match(p, cleaned) for p in candidates):
            desc = rule.get("desc", "")
            out.append(
                FindingDraft(
                    row_index=i, field=fiscal_col, severity="warning",
                    message=f"{raw!r} doesn't match the {cc} fiscal code format{f' ({desc})' if desc else ''}.",
                )
            )
    return out


register_check(
    CheckDefinition(
        key="fiscal_code_format",
        label="Fiscal Code Format",
        description=(
            "Flags a tax/fiscal ID that doesn't match its country's format, using the same per-country, "
            "per-entity-type rule table as Tax Cleansing. Needs a country column; optionally an entity-type "
            "column (ORG/IND) for countries with different formats per type."
        ),
        required_roles=["fiscal_code", "country_code"],
        optional_roles=["entity_type"],
    ),
    _run_fiscal_code_format,
)


register_check(
    CheckDefinition(
        key="duplicate_detection",
        label="Duplicate Detection",
        description=(
            "Finds likely-duplicate rows via fuzzy text similarity across the fields you map as 'match "
            "fields' (e.g. name + address). Optionally group by a field first (e.g. country) so matches are "
            "only found within the same group."
        ),
        required_roles=["match_fields"],
        optional_roles=["group_by"],
    ),
    _run_duplicate_detection,
)
