"""RegisterNumber Cleansing: standardizes Mandant.RegisterNumber via a
two-stage pipeline (Stufe 2 deterministic, Stufe 3 Claude Haiku for special
forms), reviewed and applied as proposals - matches Zerlegung's and
Nacharbeit's own "propose, review, explicit accept" pattern.

Ported from register_cleansing_module.py. Stufe 1 (junk detection) already
lives in app/cleansing/register_checks.py, ported during Quality Analysis
and reused as-is here, matching the original's own "single source of
truth" comment. Deliberately NOT ported: the LLM result cache table (same
call already made for SAP-CARP's Name Splitting and Zerlegung - an
in-memory dedup per run is enough) and the value-level dedup+fan-out the
original uses purely for its 130k+-row scale; this app's per-project
datasets are far smaller, so `run_cleansing` classifies and proposes
per-Mandant directly rather than per-unique-value.

Scope difference from the original: `accept_cleansing` deletes the
accepted proposal rows (this app's Nacharbeit/Zerlegung precedent) rather
than leaving them in the list after they've been applied - a stale
already-applied row sitting there forever is more confusing than useful.
"""

import re
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.register_checks import register_number_issues
from app.config import get_settings
from app.models.tenant import Mandant, RegisterCleansingResult

CLS_JUNK, CLS_STANDARD, CLS_CANONICAL, CLS_LLM = "JUNK", "STANDARD", "CANONICAL", "LLM"
_REASON_ADDON = "Zusatztext/Gerichtsangabe"

CONF_HIGH, CONF_MED, CONF_LOW = "HIGH", "MEDIUM", "LOW"
STUFE_STANDARD, STUFE_LLM = "STANDARD", "LLM"

LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_BATCH_SIZE = 25

# ─────────────────────────────────────────────────────────────────────────
# Stufe 2: deterministic standardization (target shape "PREFIX NUMBER[suffix]")
# ─────────────────────────────────────────────────────────────────────────

_KNOWN_PREFIXES = {"HRA": "HRA", "HRB": "HRB", "GNR": "GnR", "VR": "VR", "PR": "PR", "PARTR": "PartR", "FN": "FN"}
_RE_STD = re.compile(r"^(HRA|HRB|GNR|VR|PR|PARTR|FN)\s*[.:‐-]?\s*(\d+)\s*([A-Za-z]?)$", re.IGNORECASE)
_RE_PURE_DIGITS = re.compile(r"^\d+$")
_RE_DIGITS_SUFFIX = re.compile(r"^\d+[A-Za-z]$")  # AT Firmenbuch without FN: 258099h
_RE_CC_DIGITS = re.compile(r"^[A-Z]{1,3}\s?-\s?\d+$")  # IT: BZ-207496, MI-1991413


def _norm_value(value) -> str:
    v = "" if value is None else str(value).strip()
    return "" if v.lower() in ("nan", "none", "<na>") else v


def standardize_register_number(value) -> tuple[str | None, str]:
    """Purely formatting standardization, no interpretation. Returns
    (new_value | None, reason) - None means no change needed/possible."""
    v = _norm_value(value)
    if not v:
        return None, ""
    m = _RE_STD.match(v)
    if m:
        prefix = _KNOWN_PREFIXES[m.group(1).upper()]
        neu = f"{prefix} {m.group(2)}{m.group(3)}"
        if neu != v:
            return neu, "Praefix-Format vereinheitlicht"
        return None, ""
    collapsed = re.sub(r"\s+", " ", v)
    if collapsed != v:
        return collapsed, "Leerzeichen bereinigt"
    return None, ""


def _is_canonical(v: str) -> bool:
    """Forms accepted unchanged (not an LLM candidate)."""
    return bool(_RE_PURE_DIGITS.match(v) or _RE_DIGITS_SUFFIX.match(v) or _RE_CC_DIGITS.match(v) or _RE_STD.match(v))


def classify_value(value: str) -> tuple[str, str | None, str]:
    """Classifies one non-empty, already-trimmed RegisterNumber value.
    Returns (class, std_neu, std_grund) - class is one of JUNK/STANDARD/
    CANONICAL/LLM. A value whose only issue is embedded court/addon text
    (the number itself is extractable) becomes an LLM candidate, not JUNK.
    """
    issues = register_number_issues(value)
    hard_junk = [r for r in issues if r != _REASON_ADDON]
    if hard_junk:
        return CLS_JUNK, None, ""
    if issues:  # only addon text -> number is extractable
        return CLS_LLM, None, ""
    std, grund = standardize_register_number(value)
    if std is not None:
        return CLS_STANDARD, std, grund
    if _is_canonical(value):
        return CLS_CANONICAL, None, ""
    return CLS_LLM, None, ""


# ─────────────────────────────────────────────────────────────────────────
# Stufe 3: Claude Haiku cleanup for special forms (batch, validated)
# ─────────────────────────────────────────────────────────────────────────

_RE_DIGIT_RUN = re.compile(r"\d+")

_LLM_PROMPT_HEADER = (
    "Du bereinigst Handelsregisternummern aus einem Legacy-System "
    "(Laenderkennung in eckigen Klammern).\n"
    "Antworte NUR mit nummerierten Zeilen im Format:\n"
    "N. CLEANED|CONFIDENCE|REASON\n\n"
    "Regeln:\n"
    "- Zielformat: 'PRAEFIX NUMMER' bzw. 'PRAEFIX NUMMERsuffix' "
    "(z. B. 'HRB 227565', 'FN 200147i') oder die im Land uebliche Kurzform.\n"
    "- 'HRN' ist eine Legacy-Bezeichnung fuer Handelsregisternummer: "
    "'HRN 227565 B' -> 'HRB 227565' (nachgestelltes B/A = Abteilung des "
    "Handelsregisters -> Praefix HRB/HRA).\n"
    "- Gerichts-/Ortsangaben entfernen: 'HRB 71290 Amtsgericht Frankfurt' -> 'HRB 71290'.\n"
    "- Praefix- und Trennzeichen-Varianten vereinheitlichen (HRB-Nr. 123 -> HRB 123).\n"
    "- NIEMALS Ziffern erfinden, aendern oder ergaenzen - nur Text aus dem "
    "Originalwert verwenden.\n"
    "- CONFIDENCE: HIGH (eindeutig), MEDIUM (plausibel), LOW (unsicher).\n"
    "- Wenn keine sinnvolle Bereinigung moeglich ist: Originalwert unveraendert "
    "zurueckgeben mit CONFIDENCE LOW.\n"
    "- REASON: ein kurzer deutscher Satz, was geaendert wurde und warum.\n\n"
)


def _validate_llm_cleaned(original: str, cleaned: str) -> bool:
    """Guard against hallucination: every digit run in the proposal must
    appear in the original (reordering/trimming allowed, inventing not)."""
    if not cleaned:
        return False
    return all(d in original for d in _RE_DIGIT_RUN.findall(cleaned))


async def llm_clean_batch(client, items: list[tuple[str, str]]) -> dict[str, tuple[str, str, str]]:
    """Sends special-form values to Claude in batches. items: [(value,
    country)]. Returns {value: (cleaned, confidence, reason)} - only for
    validated answers; everything else gets no proposal.
    """
    results: dict[str, tuple[str, str, str]] = {}
    seen: set[str] = set()
    todo: list[tuple[str, str]] = []
    for val, country in items:
        if val in seen:
            continue
        seen.add(val)
        todo.append((val, country))

    chunks = [todo[i : i + LLM_BATCH_SIZE] for i in range(0, len(todo), LLM_BATCH_SIZE)]
    for chunk in chunks:
        numbered = "\n".join(f"{i + 1}. [{c or '??'}] {v}" for i, (v, c) in enumerate(chunk))
        try:
            msg = await client.messages.create(
                model=LLM_MODEL,
                max_tokens=LLM_BATCH_SIZE * 60,
                messages=[{"role": "user", "content": _LLM_PROMPT_HEADER + numbered}],
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
                parts = [p.strip() for p in line[dot_pos + 2 :].split("|")]
                if not parts or not parts[0]:
                    continue
                parts += [""] * (3 - len(parts))
                cleaned, conf, reason = parts[0], parts[1].upper(), parts[2]
                if conf not in (CONF_HIGH, CONF_MED, CONF_LOW):
                    conf = CONF_LOW
                val = chunk[idx][0]
                if not _validate_llm_cleaned(val, cleaned):
                    conf = CONF_LOW  # guard: downgrade a suspicious answer
                results[val] = (cleaned, conf, reason)
        except Exception:
            pass  # batch failed -> affected values get no proposal
    return results


# ─────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────


async def run_cleansing(db: AsyncSession, project_id: uuid.UUID, use_llm: bool = True, llm_limit: int = 0) -> dict:
    """Runs Stufe 2+3 over every Mandant with a non-empty RegisterNumber,
    replacing this project's RegisterCleansingResult rows.
    """
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id))
    mandanten = [m for m in result.scalars().all() if _norm_value(m.RegisterNumber)]

    stats = {"filled": len(mandanten), "junk": 0, "canonical": 0, "std": 0, "llm_candidates": 0, "llm_done": 0}
    if not mandanten:
        await db.execute(delete(RegisterCleansingResult).where(RegisterCleansingResult.project_id == project_id))
        await db.commit()
        return stats

    class_cache: dict[str, tuple[str, str | None, str]] = {}

    def classify(value: str) -> tuple[str, str | None, str]:
        if value not in class_cache:
            class_cache[value] = classify_value(value)
        return class_cache[value]

    for m in mandanten:
        cls, _, _ = classify(_norm_value(m.RegisterNumber))
        if cls == CLS_JUNK:
            stats["junk"] += 1
        elif cls == CLS_CANONICAL:
            stats["canonical"] += 1

    llm_candidates = [m for m in mandanten if classify(_norm_value(m.RegisterNumber))[0] == CLS_LLM]
    stats["llm_candidates"] = len({_norm_value(m.RegisterNumber) for m in llm_candidates})

    llm_map: dict[str, tuple[str, str, str]] = {}
    settings = get_settings()
    if use_llm and llm_candidates and settings.anthropic_api_key:
        from anthropic import AsyncAnthropic

        items = [(_norm_value(m.RegisterNumber), m.CountryCode or "") for m in llm_candidates]
        unique_items = list({v: c for v, c in items}.items())
        if llm_limit and llm_limit > 0:
            unique_items = unique_items[:llm_limit]
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        llm_map = await llm_clean_batch(client, unique_items)
        stats["llm_done"] = len(llm_map)

    await db.execute(delete(RegisterCleansingResult).where(RegisterCleansingResult.project_id == project_id))

    for m in mandanten:
        value = _norm_value(m.RegisterNumber)
        cls, std_neu, std_grund = classify(value)
        if cls == CLS_STANDARD:
            db.add(
                RegisterCleansingResult(
                    project_id=project_id,
                    IDParty=m.IDParty,
                    CompanyName=m.CompanyName,
                    CountryCode=m.CountryCode,
                    RegisterCity=_norm_value(m.RegisterCity),
                    RegisterNumber_Alt=value,
                    RegisterNumber_Neu=std_neu,
                    Stufe=STUFE_STANDARD,
                    Confidence=CONF_HIGH,
                    Begruendung=std_grund,
                )
            )
            stats["std"] += 1
        elif cls == CLS_LLM and value in llm_map:
            cleaned, conf, reason = llm_map[value]
            if cleaned and cleaned != value:
                db.add(
                    RegisterCleansingResult(
                        project_id=project_id,
                        IDParty=m.IDParty,
                        CompanyName=m.CompanyName,
                        CountryCode=m.CountryCode,
                        RegisterCity=_norm_value(m.RegisterCity),
                        RegisterNumber_Alt=value,
                        RegisterNumber_Neu=cleaned,
                        Stufe=STUFE_LLM,
                        Confidence=conf,
                        Begruendung=reason,
                    )
                )

    await db.commit()
    return stats


async def accept_cleansing(db: AsyncSession, project_id: uuid.UUID, confidences: list[str]) -> dict:
    """Applies every proposal whose Confidence is in `confidences` to its
    Mandant.RegisterNumber, then removes those rows from the list.
    """
    result = await db.execute(
        select(RegisterCleansingResult).where(
            RegisterCleansingResult.project_id == project_id,
            RegisterCleansingResult.Confidence.in_(confidences),
        )
    )
    rows = list(result.scalars().all())
    if not rows:
        return {"updated": 0}

    mandanten = {
        m.IDParty: m
        for m in (
            await db.execute(
                select(Mandant).where(
                    Mandant.project_id == project_id, Mandant.IDParty.in_([r.IDParty for r in rows])
                )
            )
        )
        .scalars()
        .all()
    }

    updated = 0
    for r in rows:
        mandant = mandanten.get(r.IDParty)
        if mandant is None:
            await db.delete(r)
            continue
        mandant.RegisterNumber = r.RegisterNumber_Neu
        await db.delete(r)
        updated += 1

    await db.commit()
    return {"updated": updated}
