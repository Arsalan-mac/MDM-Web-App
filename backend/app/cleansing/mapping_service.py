"""Mapping/Transform Studio - builds a new table out of one source Dataset
by mapping each output column to a source column, a constant, a
concatenation of several source columns, a value looked up through a
DatasetRelation on another dataset, or one half of a full name split into
first/last name (see app/models/dataset.py::MappingDefinition for the
field-spec shapes).

The AI-assisted `suggest_mapping` below proposes a first-guess "column" kind
for each target field name (by asking Claude Haiku to match target field
names to the source dataset's own column names) - the user still reviews and
saves the mapping themselves via create_mapping/update_mapping_fields, so a
wrong guess never silently becomes real data.
"""

import csv
import io
import uuid

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.name_split import llm_split_batch, name_needs_llm, split_name
from app.config import get_settings
from app.models.dataset import Dataset, DatasetRelation, DatasetRow, MappingDefinition

FIELD_KINDS = ["column", "constant", "concat", "relation_lookup", "name_split"]
_SUGGEST_MODEL = "claude-haiku-4-5-20251001"


class MappingError(ValueError):
    pass


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none", "<na>", "") else s


async def _get_dataset(db: AsyncSession, project_id: uuid.UUID, dataset_id: uuid.UUID) -> Dataset:
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise MappingError("Dataset not found.")
    return dataset


async def _rows(db: AsyncSession, dataset_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(DatasetRow).where(DatasetRow.dataset_id == dataset_id).order_by(DatasetRow.row_index)
    )
    return [row.data for row in result.scalars().all()]


async def _validate_field(db: AsyncSession, project_id: uuid.UUID, source: Dataset, field: dict) -> None:
    if "target" not in field or not str(field["target"]).strip():
        raise MappingError("Every field needs a non-empty 'target' name.")
    kind = field.get("kind")
    if kind not in FIELD_KINDS:
        raise MappingError(f"kind must be one of {FIELD_KINDS}, got {kind!r}.")
    config = field.get("config") or {}

    if kind == "column":
        if config.get("column") not in source.columns:
            raise MappingError(f"{config.get('column')!r} is not a column of {source.name!r}.")
    elif kind == "constant":
        if "value" not in config:
            raise MappingError("A constant field needs a 'value'.")
    elif kind == "concat":
        columns = config.get("columns") or []
        if not columns:
            raise MappingError("A concat field needs at least one source column.")
        for c in columns:
            if c not in source.columns:
                raise MappingError(f"{c!r} is not a column of {source.name!r}.")
    elif kind == "relation_lookup":
        relation_id = config.get("relation_id")
        relation = await db.get(DatasetRelation, uuid.UUID(relation_id)) if relation_id else None
        if relation is None or relation.project_id != project_id or relation.from_dataset_id != source.id:
            raise MappingError("relation_id must be a relation whose 'from' dataset is this mapping's source dataset.")
        to_dataset = await db.get(Dataset, relation.to_dataset_id)
        if config.get("column") not in (to_dataset.columns if to_dataset else []):
            raise MappingError(f"{config.get('column')!r} is not a column of the related dataset.")
    elif kind == "name_split":
        if config.get("column") not in source.columns:
            raise MappingError(f"{config.get('column')!r} is not a column of {source.name!r}.")
        if config.get("part") not in ("first", "last"):
            raise MappingError("A name_split field needs 'part' to be 'first' or 'last'.")


async def create_mapping(
    db: AsyncSession, project_id: uuid.UUID, name: str, source_dataset_id: uuid.UUID, fields: list[dict]
) -> MappingDefinition:
    source = await _get_dataset(db, project_id, source_dataset_id)
    for field in fields:
        await _validate_field(db, project_id, source, field)

    mapping = MappingDefinition(project_id=project_id, name=name, source_dataset_id=source_dataset_id, fields=fields)
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return mapping


async def list_mappings(db: AsyncSession, project_id: uuid.UUID) -> list[MappingDefinition]:
    result = await db.execute(
        select(MappingDefinition).where(MappingDefinition.project_id == project_id).order_by(MappingDefinition.created_at)
    )
    return list(result.scalars().all())


async def get_mapping(db: AsyncSession, project_id: uuid.UUID, mapping_id: uuid.UUID) -> MappingDefinition:
    result = await db.execute(
        select(MappingDefinition).where(MappingDefinition.id == mapping_id, MappingDefinition.project_id == project_id)
    )
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise MappingError("Mapping not found.")
    return mapping


async def update_mapping_fields(
    db: AsyncSession, project_id: uuid.UUID, mapping_id: uuid.UUID, fields: list[dict]
) -> MappingDefinition:
    mapping = await get_mapping(db, project_id, mapping_id)
    source = await _get_dataset(db, project_id, mapping.source_dataset_id)
    for field in fields:
        await _validate_field(db, project_id, source, field)
    mapping.fields = fields
    await db.commit()
    await db.refresh(mapping)
    return mapping


async def delete_mapping(db: AsyncSession, project_id: uuid.UUID, mapping_id: uuid.UUID) -> None:
    mapping = await get_mapping(db, project_id, mapping_id)
    await db.delete(mapping)
    await db.commit()


async def generate_mapping_rows(
    db: AsyncSession, project_id: uuid.UUID, mapping_id: uuid.UUID
) -> tuple[list[str], list[dict]]:
    """Returns (target column names in order, the generated rows)."""
    mapping = await get_mapping(db, project_id, mapping_id)
    source_rows = await _rows(db, mapping.source_dataset_id)

    # One related-rows lookup table per relation used, built once and reused
    # across every source row rather than re-querying per row.
    lookups: dict[str, dict[str, dict]] = {}
    for field in mapping.fields:
        if field["kind"] != "relation_lookup":
            continue
        relation_id = field["config"]["relation_id"]
        if relation_id in lookups:
            continue
        relation = await db.get(DatasetRelation, uuid.UUID(relation_id))
        related_rows = await _rows(db, relation.to_dataset_id)
        lookups[relation_id] = {_clean(r.get(relation.to_column)): r for r in related_rows if _clean(r.get(relation.to_column))}

    relation_from_column = {}
    for field in mapping.fields:
        if field["kind"] == "relation_lookup":
            relation_id = field["config"]["relation_id"]
            if relation_id not in relation_from_column:
                relation = await db.get(DatasetRelation, uuid.UUID(relation_id))
                relation_from_column[relation_id] = relation.from_column

    # One name-split pass per source column used this way, so first_name and
    # last_name fields off the same column share a single (possibly
    # LLM-batched) computation instead of splitting every name twice.
    name_splits: dict[str, list[dict]] = {}
    for field in mapping.fields:
        if field["kind"] != "name_split":
            continue
        column = field["config"]["column"]
        if column not in name_splits:
            name_splits[column] = await _split_column_names(source_rows, column)

    targets = [f["target"] for f in mapping.fields]
    out_rows = []
    for i, row in enumerate(source_rows):
        out = {}
        for field in mapping.fields:
            kind, config, target = field["kind"], field.get("config") or {}, field["target"]
            if kind == "column":
                out[target] = row.get(config["column"])
            elif kind == "constant":
                out[target] = config["value"]
            elif kind == "concat":
                sep = config.get("separator", " ")
                out[target] = sep.join(_clean(row.get(c)) for c in config["columns"] if _clean(row.get(c)))
            elif kind == "relation_lookup":
                relation_id = config["relation_id"]
                key = _clean(row.get(relation_from_column[relation_id]))
                related = lookups[relation_id].get(key)
                out[target] = related.get(config["column"]) if related else None
            elif kind == "name_split":
                split = name_splits[config["column"]][i]
                out[target] = split["first_name"] if config["part"] == "first" else split["last_name"]
        out_rows.append(out)

    return targets, out_rows


async def _split_column_names(rows: list[dict], column: str) -> list[dict]:
    """One name_split()-per-row pass over a source column's values, with a
    single batched Claude Haiku call up front for every distinct 3+-token
    name in the column (rather than one LLM call per row) - same batching
    shape as SAP-CARP's own preview_name_split."""
    values = [_clean(row.get(column)) for row in rows]

    llm_cache: dict[str, dict] = {}
    llm_names = {name_needs_llm(v) for v in values} - {None}
    settings = get_settings()
    if llm_names and settings.anthropic_api_key:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        llm_cache = await llm_split_batch(client, list(llm_names))

    return [split_name(v, llm_cache) for v in values]


async def mapping_to_csv(db: AsyncSession, project_id: uuid.UUID, mapping_id: uuid.UUID) -> str:
    targets, rows = await generate_mapping_rows(db, project_id, mapping_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=targets)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _parse_suggestions(text: str, targets: list[str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {t: None for t in targets}
    for line in text.strip().splitlines():
        line = line.strip()
        dot_pos = line.find(". ")
        if dot_pos == -1:
            continue
        try:
            idx = int(line[:dot_pos]) - 1
        except ValueError:
            continue
        if idx < 0 or idx >= len(targets):
            continue
        rest = line[dot_pos + 2 :].strip()
        out[targets[idx]] = None if rest.upper() == "NONE" else rest
    return out


async def suggest_mapping(
    db: AsyncSession, project_id: uuid.UUID, source_dataset_id: uuid.UUID, target_fields: list[str]
) -> dict[str, str | None]:
    """Best-guess {target_field: source_column_or_None} for each target
    field name, by asking Claude to match them against the source dataset's
    own column names. Falls back to all-None (nothing suggested) if no API
    key is configured or the call fails - the mapping still works, the user
    just picks columns manually instead of starting from a guess."""
    source = await _get_dataset(db, project_id, source_dataset_id)
    settings = get_settings()
    if not settings.anthropic_api_key or not target_fields:
        return {t: None for t in target_fields}

    numbered_targets = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(target_fields))
    columns_list = ", ".join(source.columns)
    prompt = (
        "You are matching target output field names to the best-fitting column from a source "
        "table, for a data migration mapping tool.\n\n"
        f"Source table columns: {columns_list}\n\n"
        "For each numbered target field below, answer with the single best-matching source column "
        "name, or NONE if nothing fits well.\n"
        "Respond ONLY with numbered lines in the exact format: N. COLUMN_NAME (or N. NONE)\n"
        "No other text.\n\n" + numbered_targets
    )
    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=_SUGGEST_MODEL,
            max_tokens=len(target_fields) * 30 + 50,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((b.text for b in msg.content if b.type == "text"), "")
        suggestions = _parse_suggestions(text, target_fields)
    except Exception:
        return {t: None for t in target_fields}

    # Never suggest a column the source dataset doesn't actually have -
    # trust nothing an LLM says without a boundary check.
    return {t: (col if col in source.columns else None) for t, col in suggestions.items()}
