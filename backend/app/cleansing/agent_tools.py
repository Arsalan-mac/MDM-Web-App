"""Curated, read-only tools for the "talk to your data" chat agent.

Security design (see docs/ARCHITECTURE.md): the model never gets a raw-SQL
tool and never supplies the tenant/project boundary itself. Each tool is a
closure built fresh per chat request, with `db` (already scoped to the
caller's tenant schema by app/api/deps.py::get_tenant_db) and `project_id`
(from the authenticated request's URL, not from model input) captured at
closure-creation time - the model can only pass the *other* arguments
(a search query, an IDParty), never override which tenant or project it's
looking at.

Every tool here is read-only. None of them write to `mandanten` or
`junk_address` - a chat agent that could silently apply a "fix" while
answering a question would undermine the same trust boundary the Nacharbeit
accept flow (app/cleansing/address_service.py) is built around. If a v2
adds a write-capable tool, it must return a *proposal* for the UI to confirm
explicitly, never write directly.
"""

import uuid

from anthropic import beta_async_tool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import JunkAddress, Mandant, Stage


def build_tools(db: AsyncSession, project_id: uuid.UUID) -> list:
    """Build the tool set for one chat request, bound to this request's
    tenant-scoped session and project - see module docstring.
    """

    @beta_async_tool
    async def get_pipeline_status() -> str:
        """Get the status of every stage in this migration project's pipeline
        (locked, in_progress, or done), in order.
        """
        result = await db.execute(
            select(Stage).where(Stage.project_id == project_id).order_by(Stage.position)
        )
        stages = result.scalars().all()
        if not stages:
            return "This project has no stages (it may not exist)."
        lines = [f"{s.position}. {s.label} ({s.key}): {s.status}" for s in stages]
        return "\n".join(lines)

    @beta_async_tool
    async def get_junk_address_summary() -> str:
        """Get a breakdown of the current Address Cleansing findings
        (JUNK_ADDRESS) for this project: how many findings per category and
        per confidence level. Use this before answering questions like "how
        many address problems are there" or "what kinds of issues do we have".
        """
        result = await db.execute(select(JunkAddress).where(JunkAddress.project_id == project_id))
        findings = result.scalars().all()
        if not findings:
            return "No open Address Cleansing findings for this project (run Adress-Analyse first if it hasn't been run yet)."
        by_category: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for f in findings:
            by_category[f.Kategorie] = by_category.get(f.Kategorie, 0) + 1
            conf = f.Confidence or "manuell (kein Vorschlag)"
            by_confidence[conf] = by_confidence.get(conf, 0) + 1
        lines = [f"Total open findings: {len(findings)}", "", "By category:"]
        lines += [f"  {k}: {v}" for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])]
        lines += ["", "By confidence:"]
        lines += [f"  {k}: {v}" for k, v in sorted(by_confidence.items(), key=lambda kv: -kv[1])]
        return "\n".join(lines)

    @beta_async_tool
    async def search_mandanten(query: str, limit: int = 20) -> str:
        """Search this project's client master data (Mandanten) by company
        name, city, address, or record ID. Case-insensitive substring match.
        Returns at most `limit` rows (default 20, max 100) - ask a more
        specific question rather than requesting a higher limit if there are
        too many matches to be useful.

        Args:
            query: Text to search for (e.g. a company name or city).
            limit: Maximum number of rows to return (default 20, max 100).
        """
        limit = max(1, min(limit, 100))
        like = f"%{query}%"
        result = await db.execute(
            select(Mandant)
            .where(
                Mandant.project_id == project_id,
                or_(
                    Mandant.IDParty.ilike(like),
                    Mandant.CompanyName.ilike(like),
                    Mandant.City.ilike(like),
                    Mandant.Address.ilike(like),
                ),
            )
            .limit(limit)
        )
        rows = result.scalars().all()
        if not rows:
            return f"No Mandanten match '{query}'."
        lines = [
            f"{m.IDParty} | {m.CompanyName or ''} | {m.Address or ''} | {m.City or ''} "
            f"{m.ZipCode or ''} {m.CountryCode or ''}".strip()
            for m in rows
        ]
        return "\n".join(lines)

    @beta_async_tool
    async def explain_address_finding(id_party: str) -> str:
        """Get the full detail of any open Address Cleansing findings for one
        specific client record, including why it was flagged and what (if
        any) automatic fix was proposed. Use this to answer "why is record X
        flagged" or "what's wrong with Y's address".

        Args:
            id_party: The client record's IDParty (as shown in search results
                or the findings list).
        """
        result = await db.execute(
            select(JunkAddress).where(JunkAddress.project_id == project_id, JunkAddress.IDParty == id_party)
        )
        findings = result.scalars().all()
        if not findings:
            return f"No open Address Cleansing findings for IDParty {id_party}."
        lines = []
        for f in findings:
            proposal = "no automatic fix (manual review needed)" if f.Aktion == "MANUELL" else (
                "clear the field" if f.Aktion == "LEEREN" else f"replace with: {f.Neu!r}"
            )
            lines.append(
                f"Field: {f.Feld}\nCurrent value: {f.Alt!r}\nReason: {f.Reason}\n"
                f"Category: {f.Kategorie}\nConfidence: {f.Confidence or 'n/a'}\nProposal: {proposal}"
            )
        return "\n\n".join(lines)

    @beta_async_tool
    async def get_mandanten_count() -> str:
        """Get the total number of client records (Mandanten) loaded for
        this project."""
        result = await db.execute(select(func.count()).select_from(Mandant).where(Mandant.project_id == project_id))
        return str(result.scalar_one())

    return [
        get_pipeline_status,
        get_junk_address_summary,
        search_mandanten,
        explain_address_finding,
        get_mandanten_count,
    ]
