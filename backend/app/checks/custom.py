"""No-code custom checks: a small fixed set of generic rule interpreters a
user configures via params instead of writing a check in Python. See
app/models/dataset.py::CustomCheckDefinition for the shape of a rule.

Every interpreter here is a pure function over plain row dicts (and, for
`cross_dataset_exists`, another dataset's row dicts) returning the same
FindingDraft shape the built-in checks (app/checks/builtin.py) use, so
app/cleansing/dataset_service.py can run a custom check through the exact
same finding-storage/accept/dismiss machinery.
"""

import re

from app.checks.base import FindingDraft

RULE_TYPES = ["required", "regex", "in_list", "range", "unique", "cross_dataset_exists"]


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none", "<na>", "") else s


def run_required(rows: list[dict], params: dict, severity: str) -> list[FindingDraft]:
    col = params["column"]
    return [
        FindingDraft(row_index=i, field=col, severity=severity, message=f"{col!r} is required but empty")
        for i, row in enumerate(rows)
        if not _clean(row.get(col))
    ]


def run_regex(rows: list[dict], params: dict, severity: str) -> list[FindingDraft]:
    col = params["column"]
    pattern = re.compile(params["pattern"])
    out = []
    for i, row in enumerate(rows):
        val = _clean(row.get(col))
        if val and not pattern.search(val):
            out.append(
                FindingDraft(
                    row_index=i, field=col, severity=severity, message=f"{val!r} doesn't match the required pattern"
                )
            )
    return out


def run_in_list(rows: list[dict], params: dict, severity: str) -> list[FindingDraft]:
    col = params["column"]
    allowed = {str(v).strip() for v in params["values"]}
    out = []
    for i, row in enumerate(rows):
        val = _clean(row.get(col))
        if val and val not in allowed:
            out.append(
                FindingDraft(row_index=i, field=col, severity=severity, message=f"{val!r} is not one of the allowed values")
            )
    return out


def run_range(rows: list[dict], params: dict, severity: str) -> list[FindingDraft]:
    col = params["column"]
    min_v, max_v = params.get("min"), params.get("max")
    out = []
    for i, row in enumerate(rows):
        val = _clean(row.get(col))
        if not val:
            continue
        try:
            num = float(val)
        except ValueError:
            out.append(FindingDraft(row_index=i, field=col, severity=severity, message=f"{val!r} is not a number"))
            continue
        if (min_v is not None and num < min_v) or (max_v is not None and num > max_v):
            out.append(
                FindingDraft(
                    row_index=i,
                    field=col,
                    severity=severity,
                    message=f"{num} is outside the allowed range [{min_v}, {max_v}]",
                )
            )
    return out


def run_unique(rows: list[dict], params: dict, severity: str) -> list[FindingDraft]:
    col = params["column"]
    first_seen: dict[str, int] = {}
    out = []
    for i, row in enumerate(rows):
        val = _clean(row.get(col))
        if not val:
            continue
        if val in first_seen:
            out.append(
                FindingDraft(
                    row_index=i,
                    field=col,
                    severity=severity,
                    message=f"Duplicate value {val!r} (also in row {first_seen[val] + 1})",
                )
            )
        else:
            first_seen[val] = i
    return out


def run_cross_dataset_exists(
    rows: list[dict], params: dict, severity: str, related_rows: list[dict], from_column: str, to_column: str
) -> list[FindingDraft]:
    valid_values = {_clean(r.get(to_column)) for r in related_rows} - {""}
    out = []
    for i, row in enumerate(rows):
        val = _clean(row.get(from_column))
        if val and val not in valid_values:
            out.append(
                FindingDraft(
                    row_index=i,
                    field=from_column,
                    severity=severity,
                    message=f"No matching row found ({from_column}={val!r}) in the related dataset",
                )
            )
    return out
