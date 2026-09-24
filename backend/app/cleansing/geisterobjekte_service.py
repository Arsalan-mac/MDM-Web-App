"""Geisterobjekte: find Mandanten with no connection to any Auftrag,
ConnectedParty, or MandantGegner, quarantine them, and restore them.

Ported from geisterobjekte_module.py's ghost query, quarantine/restore, and
a (deliberately small, extensible) version of its consistency check. See
app/models/tenant.py::GhostObject for what's deliberately not carried
forward (the separate ID-tracking table).
"""

import uuid

from sqlalchemy import delete, func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Auftrag, ConnectedParty, GhostObject, JunkAddress, Mandant, MandantGegner

# Result tables to scan for stale references to now-quarantined ghosts -
# grows as more pipeline stages are ported, exactly like the original app's
# manually-maintained _CONSISTENCY_REGISTRY (minus its auto-discovery of
# unregistered tables, which doesn't translate to typed Postgres models).
_CONSISTENCY_REGISTRY: list[tuple[str, str, type]] = [
    ("junk_address", "Re-run Adress-Cleansing -> Adress-Analyse", JunkAddress),
]


async def find_ghost_ids(db: AsyncSession, project_id: uuid.UUID) -> list[str]:
    """Mandanten with zero rows in Auftraege, ConnectedParty, or MandantGegner
    (checked symmetrically - either side of the latter two counts as a
    connection). Every subquery is project_id-scoped, not just the outer
    query: these reference tables can hold rows for several of a tenant's
    projects, and an unscoped join would treat another project's
    relationships as if they applied to this one.
    """
    auftrag_ids = (
        select(Auftrag.IDParty.label("id_party"))
        .where(Auftrag.project_id == project_id, Auftrag.IDParty.is_not(None))
        .distinct()
        .subquery()
    )

    vp_union = union(
        select(ConnectedParty.IDParty.label("related_id")).where(
            ConnectedParty.project_id == project_id, ConnectedParty.IDParty.is_not(None)
        ),
        select(ConnectedParty.IDParty_Related.label("related_id")).where(
            ConnectedParty.project_id == project_id, ConnectedParty.IDParty_Related.is_not(None)
        ),
    ).subquery()

    mg_union = union(
        select(MandantGegner.ClientIDParty.label("mg_id")).where(
            MandantGegner.project_id == project_id, MandantGegner.ClientIDParty.is_not(None)
        ),
        select(MandantGegner.OpponentIDParty.label("mg_id")).where(
            MandantGegner.project_id == project_id, MandantGegner.OpponentIDParty.is_not(None)
        ),
    ).subquery()

    stmt = (
        select(Mandant.IDParty)
        .outerjoin(auftrag_ids, auftrag_ids.c.id_party == Mandant.IDParty)
        .outerjoin(vp_union, vp_union.c.related_id == Mandant.IDParty)
        .outerjoin(mg_union, mg_union.c.mg_id == Mandant.IDParty)
        .where(
            Mandant.project_id == project_id,
            auftrag_ids.c.id_party.is_(None),
            vp_union.c.related_id.is_(None),
            mg_union.c.mg_id.is_(None),
        )
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def get_status(db: AsyncSession, project_id: uuid.UUID) -> dict:
    mandant_count = (
        await db.execute(select(func.count()).select_from(Mandant).where(Mandant.project_id == project_id))
    ).scalar_one()
    ghost_count = (
        await db.execute(select(func.count()).select_from(GhostObject).where(GhostObject.project_id == project_id))
    ).scalar_one()
    return {"mandant_count": mandant_count, "ghost_count": ghost_count}


async def quarantine_ghosts(db: AsyncSession, project_id: uuid.UUID) -> int:
    """Move every currently-detected ghost from `mandanten` to `geisterobjekte`.

    Idempotent: a ghost already quarantined in an earlier run is re-detected
    (it's no longer in `mandanten` to query in the first place) and simply
    isn't moved again; a ghost whose snapshot needs refreshing (e.g. it was
    restored and re-quarantined) gets its old GhostObject row replaced.
    """
    ghost_ids = await find_ghost_ids(db, project_id)
    if not ghost_ids:
        return 0

    result = await db.execute(
        select(Mandant).where(Mandant.project_id == project_id, Mandant.IDParty.in_(ghost_ids))
    )
    mandanten = result.scalars().all()

    await db.execute(
        delete(GhostObject).where(GhostObject.project_id == project_id, GhostObject.IDParty.in_(ghost_ids))
    )
    for m in mandanten:
        snapshot = {c.name: getattr(m, c.name) for c in Mandant.__table__.columns}
        db.add(GhostObject(**snapshot))
    await db.execute(delete(Mandant).where(Mandant.project_id == project_id, Mandant.IDParty.in_(ghost_ids)))
    await db.commit()
    return len(mandanten)


async def restore_ghosts(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Move every quarantined ghost back to `mandanten`.

    A ghost is skipped (not restored) if a Mandant with the same IDParty
    already exists - e.g. the file was re-uploaded via Load Data's Initial
    Load after quarantining, which doesn't touch `geisterobjekte`. Not in
    the original app (which had one workspace, so this couldn't happen);
    added here since restoring would otherwise violate the primary key.
    """
    result = await db.execute(select(GhostObject).where(GhostObject.project_id == project_id))
    ghosts = result.scalars().all()
    if not ghosts:
        return {"restored": 0, "skipped": 0}

    existing = await db.execute(select(Mandant.IDParty).where(Mandant.project_id == project_id))
    existing_ids = {row[0] for row in existing.all()}

    restored_ids = []
    for g in ghosts:
        if g.IDParty in existing_ids:
            continue
        snapshot = {c.name: getattr(g, c.name) for c in GhostObject.__table__.columns}
        db.add(Mandant(**snapshot))
        restored_ids.append(g.IDParty)

    if restored_ids:
        await db.execute(
            delete(GhostObject).where(GhostObject.project_id == project_id, GhostObject.IDParty.in_(restored_ids))
        )
    await db.commit()
    return {"restored": len(restored_ids), "skipped": len(ghosts) - len(restored_ids)}


async def run_consistency_check(db: AsyncSession, project_id: uuid.UUID) -> list[dict]:
    """Which result tables still reference now-quarantined ghost IDs - the
    analysis that built them ran before the quarantine and needs re-running.
    """
    ghost_ids_result = await db.execute(
        select(GhostObject.IDParty).where(GhostObject.project_id == project_id)
    )
    ghost_ids = {row[0] for row in ghost_ids_result.all()}
    if not ghost_ids:
        return []

    findings = []
    for table_name, hint, model in _CONSISTENCY_REGISTRY:
        count = (
            await db.execute(
                select(func.count())
                .select_from(model)
                .where(model.project_id == project_id, model.IDParty.in_(ghost_ids))
            )
        ).scalar_one()
        if count:
            findings.append({"table": table_name, "ghost_rows": count, "hint": hint})
    return findings
