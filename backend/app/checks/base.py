"""The Check Catalog: a registry of provider-agnostic data-quality checks a
user can pick and run against any Dataset, in any order, any subset -
replacing the old fixed 11-stage pipeline's locked sequence.

A Check never assumes a fixed column name. It declares the semantic
*roles* it needs (e.g. "email", "address") and reads a Dataset's actual
rows through that dataset's own `role_mapping` (role -> real column name,
or role -> list[real column name] for a check that wants several columns,
e.g. duplicate detection's match fields) - see app/models/dataset.py.

`rows` passed to a check's runner are always plain dicts of that dataset's
raw values (dataset_service.py builds them from DatasetRow.data). A
runner returns FindingDraft objects keyed by *row_index* (position in the
`rows` list it was given), not a dataset row_key - dataset_service.py
zips that back to the real row_key afterward, so a check never needs to
know or care what a dataset's primary key looks like.
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class FindingDraft:
    row_index: int
    field: str
    severity: str  # "error" | "warning" | "info"
    message: str
    proposed_value: str | None = None


CheckRunner = Callable[[list[dict], dict[str, "str | list[str]"]], list[FindingDraft]]


@dataclass(frozen=True)
class CheckDefinition:
    key: str
    label: str
    description: str
    required_roles: list[str]
    optional_roles: list[str] = field(default_factory=list)


_DEFINITIONS: dict[str, CheckDefinition] = {}
_RUNNERS: dict[str, CheckRunner] = {}


def register_check(definition: CheckDefinition, runner: CheckRunner) -> None:
    _DEFINITIONS[definition.key] = definition
    _RUNNERS[definition.key] = runner


def list_checks() -> list[CheckDefinition]:
    return sorted(_DEFINITIONS.values(), key=lambda c: c.label)


def get_check(key: str) -> CheckDefinition | None:
    return _DEFINITIONS.get(key)


def run_check(key: str, rows: list[dict], role_mapping: dict) -> list[FindingDraft]:
    runner = _RUNNERS.get(key)
    if runner is None:
        raise KeyError(f"Unknown check: {key!r}")
    return runner(rows, role_mapping)


def missing_roles(key: str, role_mapping: dict) -> list[str]:
    """Required roles this dataset's role_mapping doesn't cover yet - a
    check with a non-empty result here can't be run until the user (or the
    AI mapping assistant) maps them."""
    definition = _DEFINITIONS[key]
    return [r for r in definition.required_roles if not role_mapping.get(r)]
