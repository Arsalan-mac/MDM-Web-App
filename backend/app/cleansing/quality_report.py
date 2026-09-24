"""Shared 2-row (Organisation / Natuerliche Person) quality summary used by
several of Quality Analysis's checks. Ported from mdm_shared.py's
compute_quality_report - pure Python here instead of pandas, matching this
backend's service-layer convention of working with plain rows/ORM objects.
"""

_TRUE_STRINGS = {"1", "1.0", "true", "True"}


def compute_quality_report(
    rows: list[dict],
    junk_ids: set[str],
    empty_ids: set[str],
    *,
    optional_field: bool = False,
) -> list[dict]:
    """rows: dicts with at least IDParty, IsOrganisation, IsIndividual.

    optional_field=True: % Valid and % Junk are computed against
    (Total Valid + Total Junk) only - empty records are excluded from that
    denominator. Use for optional fields (VAT, Email, Website, Phone, Fax,
    RegisterNumber). Invariant: Total Valid + Total Junk + Total Empty ==
    Total Clients.
    """
    report = []
    for label, flag_key in [("Organisation", "IsOrganisation"), ("Natuerliche Person", "IsIndividual")]:
        sub = [r for r in rows if str(r.get(flag_key)) in _TRUE_STRINGS]
        total = len(sub)
        if total == 0:
            continue
        ids = {str(r["IDParty"]) for r in sub}

        total_junk = len(ids & junk_ids)
        total_empty = len(ids & empty_ids)
        total_valid = max(total - total_junk - total_empty, 0)

        filled = total_valid + total_junk
        pct_denom = filled if (optional_field and filled > 0) else total

        report.append(
            {
                "type": label,
                "total_clients": total,
                "total_valid": total_valid,
                "total_junk": total_junk,
                "total_empty": total_empty,
                "pct_valid": round(total_valid / pct_denom * 100, 2) if pct_denom else 0,
                "pct_junk": round(total_junk / pct_denom * 100, 2) if pct_denom else 0,
                "pct_empty": round(total_empty / total * 100, 2) if total else 0,
            }
        )
    return report
