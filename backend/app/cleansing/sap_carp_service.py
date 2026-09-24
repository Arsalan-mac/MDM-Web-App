"""SAP-CARP-Ueberschreibung: overwrite Mandant fields from an uploaded SAP
export via a field-mapping table, distribute CompanyName into SAP Name 1-4
export slots, and split natural-person names into FirstName/LastName.

Ported from sap_carp_module.py. Two scope differences from the original,
both documented in docs/ROADMAP.md:
- Field-Mapping can target any of Mandant's typed columns directly; a
  target that isn't one (e.g. the Name 1-4 export slots, which nothing
  else here reads yet) is written into Mandant.extra instead of growing
  the typed column set for a field no ported stage consumes - the same
  rule the reference-table loaders already follow.
- The "erledigt" flag that unlocked the rest of the original app's nav is
  just this project's "sap_carp" Stage reaching status "done" here
  (app/cleansing/pipeline.py) - no separate settings table needed, since
  this backend already has a per-project stage-lock mechanism the
  original's single-workspace app didn't.
"""

import textwrap
import uuid

import pandas as pd
from anthropic import AsyncAnthropic
from nameparser import HumanName
from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.tenant import FieldMapping, Mandant, SapStammdaten

_SAP_KEY_CANDIDATES = ["IDParty", "Ext. Partnernummer"]

_SYSTEM_MANDANT_COLUMNS = {
    "project_id", "IDParty", "extra", "SapOverridden", "Load_Date", "Source_FILE", "Change_Reason",
}
_WRITABLE_MANDANT_COLUMNS = {c.name for c in Mandant.__table__.columns if c.name not in _SYSTEM_MANDANT_COLUMNS}

_NAME_MODEL = "claude-haiku-4-5-20251001"
_BATCH_SIZE = 50


def _is_clean(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none", "na", "<na>")


def _parse_condition(cond_val) -> str | None:
    if _is_clean(cond_val):
        return None
    s = str(cond_val).strip()
    if s.endswith("= 1") or s.endswith("=1"):
        return "1"
    if s.endswith("= 0") or s.endswith("=0"):
        return "0"
    return None


def _resolve_sap_key(columns) -> str | None:
    cols = set(columns)
    for cand in _SAP_KEY_CANDIDATES:
        if cand in cols:
            return cand
    return None


# ─────────────────────────────────────────────────────────────────────────
# SAP-Allgemeine Stammdaten upload
# ─────────────────────────────────────────────────────────────────────────


async def load_sap_stammdaten(db: AsyncSession, project_id: uuid.UUID, df: pd.DataFrame, file_name: str) -> dict:
    if df.empty:
        raise ValueError("The uploaded file has no rows.")

    sap_key_col = _resolve_sap_key(df.columns)
    if sap_key_col is None:
        raise ValueError(f"No key column ({' / '.join(_SAP_KEY_CANDIDATES)}) found in the uploaded file.")

    records = []
    seen_keys: set[str] = set()
    dup_keys = 0
    for row in df.to_dict(orient="records"):
        key_val = row.get(sap_key_col)
        if _is_clean(key_val):
            continue
        key = str(key_val).strip()
        if key in seen_keys:
            dup_keys += 1
            continue
        seen_keys.add(key)
        records.append(
            {
                "project_id": project_id,
                "sap_key": key,
                "data": {c: v for c, v in row.items() if not _is_clean(v)},
                "Source_FILE": file_name,
            }
        )

    if not records:
        raise ValueError(f"No rows with a valid '{sap_key_col}' found in the uploaded file.")

    await db.execute(delete(SapStammdaten).where(SapStammdaten.project_id == project_id))
    await db.execute(insert(SapStammdaten.__table__), records)
    await db.commit()

    return {"row_count": len(records), "columns": list(df.columns), "sap_key_col": sap_key_col, "dup_keys": dup_keys}


# ─────────────────────────────────────────────────────────────────────────
# Step 1: overwrite Mandant fields from SAP-Allgemeine Stammdaten via
# Field-Mapping
# ─────────────────────────────────────────────────────────────────────────


def _build_col_map(field_rows: list[FieldMapping]) -> dict[str, tuple[str, str | None]]:
    col_map: dict[str, tuple[str, str | None]] = {}
    for r in field_rows:
        mand_col = (r.MandantColumn or "").strip()
        sap_col = (r.SapColumn or "").strip()
        if not mand_col or not sap_col:
            continue
        col_map[mand_col] = (sap_col, _parse_condition(r.Condition))
    return col_map


async def get_overwrite_status(db: AsyncSession, project_id: uuid.UUID) -> dict:
    field_result = await db.execute(select(FieldMapping).where(FieldMapping.project_id == project_id))
    field_rows = list(field_result.scalars().all())
    col_map = _build_col_map(field_rows)

    sap_sample = (
        await db.execute(select(SapStammdaten).where(SapStammdaten.project_id == project_id).limit(1))
    ).scalar_one_or_none()
    sap_columns = set(sap_sample.data.keys()) if sap_sample is not None else set()
    sap_key_col = _resolve_sap_key(sap_columns) if sap_sample is not None else None

    sap_count = (
        await db.execute(select(func.count()).select_from(SapStammdaten).where(SapStammdaten.project_id == project_id))
    ).scalar_one()
    mandant_count = (
        await db.execute(select(func.count()).select_from(Mandant).where(Mandant.project_id == project_id))
    ).scalar_one()
    already_flagged = (
        await db.execute(
            select(func.count())
            .select_from(Mandant)
            .where(Mandant.project_id == project_id, Mandant.SapOverridden.is_(True))
        )
    ).scalar_one()

    match_count = 0
    if sap_count and mandant_count:
        sap_keys = select(SapStammdaten.sap_key).where(SapStammdaten.project_id == project_id).subquery()
        match_count = (
            await db.execute(
                select(func.count())
                .select_from(Mandant)
                .where(Mandant.project_id == project_id, Mandant.IDParty.in_(select(sap_keys)))
            )
        ).scalar_one()

    missing_sap = [sap_col for sap_col, _ in col_map.values() if sap_columns and sap_col not in sap_columns]

    return {
        "sap_ok": sap_count > 0,
        "field_ok": len(field_rows) > 0,
        "mandant_ok": mandant_count > 0,
        "sap_key_col": sap_key_col,
        "mapping_rows": len(col_map),
        "match_count": match_count,
        "already_flagged": already_flagged,
        "missing_sap": missing_sap,
        "col_map": [
            {"mandant_column": mc, "sap_column": sc, "condition": cond} for mc, (sc, cond) in col_map.items()
        ],
    }


async def run_overwrite(db: AsyncSession, project_id: uuid.UUID, reset_flag: bool = False) -> dict:
    sap_result = await db.execute(select(SapStammdaten).where(SapStammdaten.project_id == project_id))
    sap_rows = {r.sap_key: r.data for r in sap_result.scalars().all()}
    if not sap_rows:
        raise ValueError("No SAP-Allgemeine Stammdaten uploaded yet.")

    field_result = await db.execute(select(FieldMapping).where(FieldMapping.project_id == project_id))
    col_map = _build_col_map(list(field_result.scalars().all()))
    if not col_map:
        raise ValueError("No usable rows in Field-Mapping (need both a Mandanten and a SAP column per row).")

    mandant_result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = list(mandant_result.scalars().all())
    if not mandanten:
        raise ValueError("No Mandanten loaded yet.")

    if reset_flag:
        for m in mandanten:
            m.SapOverridden = False

    flagged = 0
    for m in mandanten:
        sap_row = sap_rows.get(str(m.IDParty).strip())
        if sap_row is None:
            continue
        is_org = (m.IsOrganisation or "").strip()
        changed = False
        for mand_col, (sap_col, condition) in col_map.items():
            if sap_col not in sap_row:
                continue
            if condition is not None and is_org != condition:
                continue
            sap_val = sap_row[sap_col]
            if mand_col in _WRITABLE_MANDANT_COLUMNS:
                setattr(m, mand_col, sap_val)
            else:
                m.extra = {**m.extra, mand_col: sap_val}
            changed = True
        if changed:
            m.SapOverridden = True
            flagged += 1

    await db.commit()
    return {"flagged": flagged, "sap_rows": len(sap_rows), "reset_flag": reset_flag}


# ─────────────────────────────────────────────────────────────────────────
# Step 2: CompanyName -> Name 1-4 (SAP export slots, kept in `extra` - see
# module docstring)
# ─────────────────────────────────────────────────────────────────────────

_NAME_SLOTS = ["Name 1", "Name 2", "Name 3", "Name 4"]


async def get_name_distribution_status(db: AsyncSession, project_id: uuid.UUID) -> dict:
    affected = (
        await db.execute(
            select(func.count())
            .select_from(Mandant)
            .where(
                Mandant.project_id == project_id,
                Mandant.IsOrganisation == "1",
                Mandant.CompanyName.is_not(None),
                func.trim(Mandant.CompanyName) != "",
            )
        )
    ).scalar_one()
    already_split = (
        await db.execute(
            select(func.count())
            .select_from(Mandant)
            .where(
                Mandant.project_id == project_id,
                Mandant.extra["Name 1"].astext.is_not(None),
                func.trim(Mandant.extra["Name 1"].astext) != "",
            )
        )
    ).scalar_one()
    return {"affected_rows": affected, "already_split": already_split}


async def run_name_distribution(db: AsyncSession, project_id: uuid.UUID, chunk_size: int = 40) -> dict:
    chunk_size = max(1, int(chunk_size or 40))
    result = await db.execute(
        select(Mandant).where(Mandant.project_id == project_id, Mandant.IsOrganisation == "1")
    )
    mandanten = list(result.scalars().all())

    affected = 0
    for m in mandanten:
        name = (m.CompanyName or "").strip()
        if not name:
            continue
        words = textwrap.wrap(name, width=chunk_size)
        slots = {
            "Name 1": words[0] if len(words) > 0 else "",
            "Name 2": words[1] if len(words) > 1 else "",
            "Name 3": words[2] if len(words) > 2 else "",
            "Name 4": " ".join(words[3:]) if len(words) > 3 else "",
        }
        m.extra = {**m.extra, **slots}
        affected += 1

    await db.commit()
    return {"affected": affected, "chunk_size": chunk_size}


# ─────────────────────────────────────────────────────────────────────────
# Step 3: Name Splitting (nameparser + Claude Haiku fallback for 3+-token
# names) - writes Mandant.FirstName/LastName
# ─────────────────────────────────────────────────────────────────────────


def _name_needs_llm(company_name: str) -> str | None:
    name = company_name.strip()
    if not name or "," in name:
        return None
    n = HumanName(name)
    if n.title:
        return None
    tokens = [t for t in " ".join(filter(None, [n.first, n.middle, n.last])).split() if t]
    return " ".join(tokens) if len(tokens) >= 3 else None


def _split_name(company_name: str, llm_cache: dict[str, dict] | None = None) -> dict:
    llm_cache = llm_cache or {}
    name = company_name.strip()
    if not name:
        return {"first_name": "", "last_name": "", "method": "unklar"}

    if "," in name:
        n = HumanName(name)
        given = " ".join(filter(None, [n.first, n.middle])).strip()
        return {"first_name": given, "last_name": n.last, "method": "komma"}

    n = HumanName(name)
    tokens = [t for t in " ".join(filter(None, [n.first, n.middle, n.last])).split() if t]
    if not tokens:
        return {"first_name": "", "last_name": "", "method": "unklar"}
    if len(tokens) == 1:
        return {"first_name": "", "last_name": tokens[0], "method": "unklar"}

    had_title = bool(n.title)
    if not had_title and len(tokens) >= 3:
        token_name = " ".join(tokens)
        if token_name in llm_cache:
            return llm_cache[token_name]
        # No LLM result available (not configured, or this call failed) -
        # same first-token/rest fallback the original app uses on an LLM error.
        return {"first_name": tokens[0], "last_name": " ".join(tokens[1:]), "method": "unklar"}

    method = "nameparser-titel" if had_title else "2-token"
    return {"first_name": " ".join(tokens[:-1]), "last_name": tokens[-1], "method": method}


async def _llm_split_batch(client: AsyncAnthropic, names: list[str]) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    chunks = [names[i : i + _BATCH_SIZE] for i in range(0, len(names), _BATCH_SIZE)]
    for chunk in chunks:
        numbered = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(chunk))
        prompt = (
            "Trenne diese deutschen Namen in Vorname und Nachname.\n"
            "Antworte NUR mit nummerierten Zeilen im Format: N. VORNAME|NACHNAME\n"
            "Keine weiteren Erklärungen.\n\n" + numbered
        )
        try:
            msg = await client.messages.create(
                model=_NAME_MODEL,
                max_tokens=_BATCH_SIZE * 25,
                messages=[{"role": "user", "content": prompt}],
            )
            text = next((b.text for b in msg.content if b.type == "text"), "")
            for line in text.strip().splitlines():
                line = line.strip()
                dot_pos = line.find(". ")
                if dot_pos == -1:
                    continue
                try:
                    idx = int(line[:dot_pos]) - 1
                except ValueError:
                    continue
                if idx < 0 or idx >= len(chunk):
                    continue
                rest = line[dot_pos + 2 :]
                if "|" in rest:
                    vorname, nachname = rest.split("|", 1)
                    cache[chunk[idx]] = {"first_name": vorname.strip(), "last_name": nachname.strip(), "method": "llm"}
        except Exception:
            pass  # Falls through to _split_name's per-name "unklar" fallback.
    return cache


def _name_split_candidates_stmt(project_id: uuid.UUID):
    return select(Mandant).where(
        Mandant.project_id == project_id,
        Mandant.IsOrganisation == "0",
        Mandant.SapOverridden.is_(False),
        or_(Mandant.FirstName.is_(None), func.trim(Mandant.FirstName) == ""),
        or_(Mandant.LastName.is_(None), func.trim(Mandant.LastName) == ""),
        Mandant.CompanyName.is_not(None),
        func.trim(Mandant.CompanyName) != "",
    )


async def get_name_split_status(db: AsyncSession, project_id: uuid.UUID) -> dict:
    candidate_count = (
        await db.execute(select(func.count()).select_from(_name_split_candidates_stmt(project_id).subquery()))
    ).scalar_one()
    cleanup_count = (
        await db.execute(
            select(func.count())
            .select_from(Mandant)
            .where(
                Mandant.project_id == project_id,
                Mandant.IsOrganisation == "0",
                Mandant.FirstName.is_not(None),
                func.trim(Mandant.FirstName) != "",
                Mandant.LastName.is_not(None),
                func.trim(Mandant.LastName) != "",
                Mandant.CompanyName.is_not(None),
                func.trim(Mandant.CompanyName) != "",
            )
        )
    ).scalar_one()
    return {"candidate_count": candidate_count, "cleanup_count": cleanup_count}


async def preview_name_split(db: AsyncSession, project_id: uuid.UUID) -> list[dict]:
    result = await db.execute(_name_split_candidates_stmt(project_id))
    candidates = list(result.scalars().all())

    llm_names = []
    for m in candidates:
        token_name = _name_needs_llm((m.CompanyName or "").strip())
        if token_name:
            llm_names.append(token_name)

    llm_cache: dict[str, dict] = {}
    settings = get_settings()
    if llm_names and settings.anthropic_api_key:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        llm_cache = await _llm_split_batch(client, list(set(llm_names)))

    results = []
    for m in candidates:
        company_name = (m.CompanyName or "").strip()
        split = _split_name(company_name, llm_cache)
        results.append(
            {
                "id_party": m.IDParty,
                "company_name": company_name,
                "first_name": split["first_name"],
                "last_name": split["last_name"],
                "method": split["method"],
            }
        )
    return results


async def apply_name_split(db: AsyncSession, project_id: uuid.UUID, entries: list[dict]) -> dict:
    if not entries:
        return {"written": 0}

    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    by_id = {m.IDParty: m for m in result.scalars().all()}

    written = 0
    for e in entries:
        m = by_id.get(str(e["id_party"]).strip())
        if m is None:
            continue
        m.FirstName = e["first_name"]
        m.LastName = e["last_name"]
        written += 1

    await db.commit()
    return {"written": written}


async def clear_redundant_company_names(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Empty CompanyName where FirstName+LastName are already filled in -
    the Name Splitting tab's own cleanup action."""
    result = await db.execute(
        select(Mandant).where(
            Mandant.project_id == project_id,
            Mandant.IsOrganisation == "0",
            Mandant.FirstName.is_not(None),
            func.trim(Mandant.FirstName) != "",
            Mandant.LastName.is_not(None),
            func.trim(Mandant.LastName) != "",
            Mandant.CompanyName.is_not(None),
            func.trim(Mandant.CompanyName) != "",
        )
    )
    rows = list(result.scalars().all())
    for m in rows:
        m.CompanyName = ""
    await db.commit()
    return {"cleared": len(rows)}
