"""Persistence for the Address Cleansing stage: run Adress-Analyse, and
apply ("Nacharbeit") a finding's proposal back into Mandanten.
"""

import datetime
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.address_checks import ACTION_CLEAR, ACTION_REPLACE, CONF_HIGH, CONF_MED, check_addresses
from app.models.tenant import JunkAddress, Mandant

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
