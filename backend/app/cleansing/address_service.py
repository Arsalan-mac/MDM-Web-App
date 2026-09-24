"""Persistence for the Address Cleansing stage: run Adress-Analyse, apply
("Nacharbeit") a finding's proposal back into Mandanten, and Zerlegung
(SAP address decomposition).
"""

import datetime
import uuid

from anthropic import AsyncAnthropic
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.address_checks import ACTION_CLEAR, ACTION_REPLACE, CONF_HIGH, CONF_MED, check_addresses
from app.cleansing.address_decomposition import (
    ACTION_MANUAL as ZERLEGUNG_ACTION_MANUAL,
)
from app.cleansing.address_decomposition import (
    ACTION_REPLACE as ZERLEGUNG_ACTION_REPLACE,
)
from app.cleansing.address_decomposition import (
    CONF_MANUAL as ZERLEGUNG_CONF_MANUAL,
)
from app.cleansing.address_decomposition import llm_parse_batch, needs_llm, parse_address, spell_out_street
from app.config import get_settings
from app.models.tenant import AddressDecompositionResult, JunkAddress, Mandant

_ANALYZED_FIELD = "Address"


async def run_address_analysis(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Check every Mandant's Address field, replacing any prior findings for
    that field (a fresh run supersedes the last one - matches the original
    app's "Adress-Analyse" re-run behavior).
    """
    # Excludes SAP-overridden records - matches address_common.load_population
    # in the original app (Q10/Q14: everyone else is checked, inactive
    # records included, only SAP-overridden ones are skipped).
    result = await db.execute(
        select(Mandant).where(Mandant.project_id == project_id, Mandant.SapOverridden.is_(False))
    )
    mandanten = result.scalars().all()
    rows = [
        {
            "IDParty": m.IDParty,
            "UserCode_Added": m.UserCode_Added,
            "UserCode_Kummerer": m.UserCode_Kummerer,
            "CompanyName": m.CompanyName,
            "IsOrganisation": m.IsOrganisation,
            "IsIndividual": m.IsIndividual,
            "IsInactive": m.IsInactive,
            "Address": m.Address,
            "City": m.City,
            "ZipCode": m.ZipCode,
            "CountryCode": m.CountryCode,
        }
        for m in mandanten
    ]

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # No PLZ_RULES yet (see app/cleansing/address_checks.py docstring) - every
    # country rule lookup degrades gracefully to None.
    findings = check_addresses(rows, rules={}, ts=ts)

    await db.execute(
        delete(JunkAddress).where(JunkAddress.project_id == project_id, JunkAddress.Feld == _ANALYZED_FIELD)
    )
    for f in findings:
        db.add(JunkAddress(project_id=project_id, **f))
    await db.commit()

    by_category: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for f in findings:
        by_category[f["Kategorie"]] = by_category.get(f["Kategorie"], 0) + 1
        conf = f["Confidence"] or "manuell"
        by_confidence[conf] = by_confidence.get(conf, 0) + 1

    return {
        "rows_checked": len(rows),
        "findings": len(findings),
        "by_category": by_category,
        "by_confidence": by_confidence,
    }


class FindingNotAcceptable(ValueError):
    pass


async def accept_finding(db: AsyncSession, project_id: uuid.UUID, finding_id: uuid.UUID) -> None:
    """Apply one finding's proposal to the Mandant record, then remove the
    finding - mirrors address_common.apply_field_proposals's per-row logic,
    minus the old-value guard (no concurrent editors here yet) and the
    generic multi-field support (only Feld="Address" exists so far).
    """
    finding = await db.get(JunkAddress, finding_id)
    if finding is None or finding.project_id != project_id:
        raise FindingNotAcceptable("Finding not found.")
    if finding.Aktion not in (ACTION_REPLACE, ACTION_CLEAR):
        raise FindingNotAcceptable("This finding has no automatic proposal (Aktion=MANUELL).")
    if finding.Confidence not in (CONF_HIGH, CONF_MED):
        raise FindingNotAcceptable("Only Hoch/Mittel confidence findings can be accepted here.")

    mandant = await db.get(Mandant, {"project_id": project_id, "IDParty": finding.IDParty})
    if mandant is None:
        # The record was deleted since the analysis ran - drop the stale finding.
        await db.delete(finding)
        await db.commit()
        raise FindingNotAcceptable("The underlying Mandant record no longer exists.")

    new_value = None if finding.Aktion == ACTION_CLEAR else finding.Neu
    setattr(mandant, finding.Feld, new_value)
    await db.delete(finding)
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────
# Zerlegung: split Address into SAP's ADRC target fields
# ─────────────────────────────────────────────────────────────────────────


async def _decomposition_candidates(db: AsyncSession, project_id: uuid.UUID) -> list[Mandant]:
    """Every Mandant with a non-empty Address, not SAP-overridden, and
    without an OPEN manual JUNK_ADDRESS finding for that field (a finding
    with an automatic proposal disappears from the table once Nacharbeit
    accepts it, so it doesn't need excluding here) - matches the original's
    selection SQL exactly."""
    manual_ids_result = await db.execute(
        select(JunkAddress.IDParty).where(
            JunkAddress.project_id == project_id,
            JunkAddress.Feld == _ANALYZED_FIELD,
            JunkAddress.Aktion == "MANUELL",
        )
    )
    manual_ids = {row[0] for row in manual_ids_result.all()}

    result = await db.execute(
        select(Mandant).where(
            Mandant.project_id == project_id,
            Mandant.SapOverridden.is_(False),
            Mandant.Address.is_not(None),
            Mandant.Address != "",
        )
    )
    return [m for m in result.scalars().all() if m.IDParty not in manual_ids]


async def run_decomposition(db: AsyncSession, project_id: uuid.UUID, use_llm: bool = True) -> dict:
    """Zerlegung: parses every candidate's Address with the tiered regex
    parser, optionally sends unparsable/uncertain cases to Claude Haiku in
    a batch, and replaces this project's AddressDecompositionResult rows.
    """
    candidates = await _decomposition_candidates(db, project_id)

    regex_results = [parse_address(m.Address, m.CountryCode or "") for m in candidates]
    results = list(regex_results)

    n_llm = 0
    n_llm_ok = 0
    settings = get_settings()
    if use_llm and settings.anthropic_api_key:
        llm_idx = [i for i, r in enumerate(results) if needs_llm(r)]
        n_llm = len(llm_idx)
        if llm_idx:
            items = [(candidates[i].Address, candidates[i].CountryCode or "") for i in llm_idx]
            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            llm_map = await llm_parse_batch(client, items)
            for i in llm_idx:
                addr = candidates[i].Address
                if addr in llm_map:
                    results[i] = llm_map[addr]
                    n_llm_ok += 1

    await db.execute(delete(AddressDecompositionResult).where(AddressDecompositionResult.project_id == project_id))
    for m, r in zip(candidates, results):
        db.add(
            AddressDecompositionResult(
                project_id=project_id,
                IDParty=m.IDParty,
                CompanyName=m.CompanyName,
                CountryCode=m.CountryCode,
                Address=m.Address,
                STREET=r.street,
                HOUSE_NUM1=r.house_num,
                STR_SUPPL1=r.suppl1,
                STR_SUPPL2=r.suppl2,
                STR_SUPPL3=r.suppl3,
                BUILDING=r.building,
                StreetSpelledOut=spell_out_street(r.street, m.CountryCode or ""),
                ParseMethod=r.method,
                Confidence=r.confidence,
                Hinweis=r.hinweis,
                Aktion=ZERLEGUNG_ACTION_MANUAL if r.confidence == ZERLEGUNG_CONF_MANUAL else ZERLEGUNG_ACTION_REPLACE,
            )
        )
    await db.commit()

    by_method: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for r in results:
        by_method[r.method] = by_method.get(r.method, 0) + 1
        conf = r.confidence or "manuell"
        by_confidence[conf] = by_confidence.get(conf, 0) + 1

    return {
        "candidates": len(candidates),
        "sent_to_llm": n_llm,
        "llm_resolved": n_llm_ok,
        "by_method": by_method,
        "by_confidence": by_confidence,
    }


_ZERLEGUNG_TARGET_FIELDS = ["STREET", "HOUSE_NUM1", "STR_SUPPL1", "STR_SUPPL2", "STR_SUPPL3", "BUILDING"]


async def accept_decomposition(
    db: AsyncSession, project_id: uuid.UUID, confidences: list[str], spell_out: bool = False
) -> dict:
    """Applies every AddressDecompositionResult row whose Confidence is in
    `confidences` to its Mandant record, then removes those rows - matches
    the original's confidence-tiered "Übernahme" (minus the old-value guard,
    same call this app already made for Nacharbeit: no concurrent editors
    here yet). `spell_out` writes STREET in its spelled-out form ('Str.' ->
    'Straße'/'Strasse') when one was computed.
    """
    result = await db.execute(
        select(AddressDecompositionResult).where(
            AddressDecompositionResult.project_id == project_id,
            AddressDecompositionResult.Confidence.in_(confidences),
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
        mandant.STREET = r.StreetSpelledOut if (spell_out and r.StreetSpelledOut) else r.STREET
        mandant.HOUSE_NUM1 = r.HOUSE_NUM1
        mandant.STR_SUPPL1 = r.STR_SUPPL1
        mandant.STR_SUPPL2 = r.STR_SUPPL2
        mandant.STR_SUPPL3 = r.STR_SUPPL3
        mandant.BUILDING = r.BUILDING
        await db.delete(r)
        updated += 1

    await db.commit()
    return {"updated": updated}
