"""Pure VAT-number cleaning/validation helpers and the per-country pattern
table, ported verbatim from tax_cleansing_module.py. No DB/Streamlit
dependency, so these are unit-testable in isolation and reusable by a
future Migration Preparation phase, same reasoning as register_checks.py.
"""

import re


def clean_swiss_vat(raw_vat: str) -> str:
    """Pre-process a Swiss VAT/UID into canonical CHE + 9-digit + optional
    suffix. Examples: 'CHE-123.456.789 MWST' -> 'CHE123456789MWST';
    '123.456.789' -> 'CHE123456789'; 'CHE123456789TVA' -> unchanged."""
    cleaned = re.sub(r"[^A-Z0-9]", "", raw_vat.upper())
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) == 9:
        for suffix in ("MWST", "TVA", "IVA"):
            if cleaned.endswith(suffix):
                return "CHE" + digits_only + suffix
        return "CHE" + digits_only
    return cleaned


def clean_norwegian_vat(raw: str) -> str:
    """Adds the NO prefix if missing, and the MVA suffix for a bare 9-digit
    number - same logic used for both analysis and the future migration."""
    v = re.sub(r"[^A-Z0-9]", "", str(raw).strip().upper())
    if not v.startswith("NO"):
        v = "NO" + v
    core = v[2:]
    if re.match(r"^\d{9}$", core):
        v = "NO" + core + "MVA"
    return v


def clean_tax_number(value: str, country: str = "") -> str:
    """Strip whitespace, dots and hyphens. For Russia (RU) the forward slash
    is preserved so split_russian_tax_number can use it; other special
    characters (e.g. Ñ, & for MX) are left intact."""
    v = str(value).strip().upper()
    v = v.replace(".", "").replace("-", "")
    if country.upper() != "RU":
        v = v.replace(" ", "")
    else:
        v = re.sub(r"\s*/\s*", " / ", v)
        v = re.sub(r"(?<![/ ])\s+(?![/ ])", "", v)
    return v


def split_russian_tax_number(raw: str) -> tuple[str, str | None, int]:
    """Splits a Russian tax number into (INN, KPP | None, slash_count).

    - 0 slashes -> INN only (KPP = None)
    - 1 slash   -> part 1 = INN, part 2 = KPP
    - 2+ slashes -> not splittable; INN holds the cleaned whole value, the
      caller decides (VAT analysis: junk)
    """
    cleaned = clean_tax_number(str(raw).strip(), country="RU")
    slash_count = cleaned.count("/")
    if slash_count == 1:
        p1, p2 = (p.strip() for p in cleaned.split("/"))
        return (re.sub(r"(?i)INN", "", p1).strip(), re.sub(r"(?i)KPP", "", p2).strip(), 1)
    return (re.sub(r"(?i)INN", "", cleaned).strip(), None, slash_count)


VAT_RULES: dict[str, str] = {
    "AT": r"^ATU\d{8}$", "BE": r"^BE[01]\d{9}$", "BG": r"^BG\d{9,10}$",
    "CH": r"^CHE[0-9]{9}(MWST|TVA|IVA)?$", "CY": r"^CY\d{8}[A-Z]$", "CZ": r"^CZ\d{8,10}$",
    "DE": r"^DE\d{9}$", "DK": r"^DK\d{8}$", "EE": r"^EE\d{9}$",
    "EL": r"^EL\d{9}$", "GR": r"^EL\d{9}$", "ES": r"^ES[A-Z0-9]\d{7}[A-Z0-9]$",
    "FI": r"^FI\d{8}$", "FR": r"^FR[A-Z0-9]{2}\d{9}$",
    "GB": r"^GB(\d{9}|\d{12}|(GD|HA)\d{3})$", "HR": r"^HR\d{11}$", "HU": r"^HU\d{8}$",
    "IE": r"^IE(\d[A-Z0-9]\d{5}[A-Z]|\d{7}[A-W][A-I])$", "IS": r"^IS\d{5,6}$", "IT": r"^IT\d{11}$",
    "LI": r"^LI\d{5}$", "LT": r"^LT(\d{9}|\d{12})$", "LU": r"^LU\d{8}$",
    "LV": r"^LV\d{11}$", "MC": r"^MC[A-Z0-9]{2}\d{9}$", "MK": r"^MK\d{13}$",
    "MT": r"^MT\d{8}$", "NL": r"^NL\d{9}B\d{2}$", "NO": r"^NO\d{9}MVA$",
    "PL": r"^PL\d{10}$", "PT": r"^PT\d{9}$", "RO": r"^RO[1-9]\d{1,9}$", "RS": r"^RS\d{9}$",
    "SE": r"^SE\d{10}01$", "SI": r"^SI\d{8}$", "SK": r"^SK\d{10}$", "SM": r"^SM\d{5}$",
    "TR": r"^TR\d{10}$", "UA": r"^UA\d{12}$", "AU": r"^AU\d{11}$",
    "CN": r"^CN[A-Z0-9]{18}$", "ID": r"^ID\d{15,16}$", "IL": r"^IL\d{9}$",
    "IN": r"^IN\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1}$", "JP": r"^JP\d{13}$",
    "KZ": r"^KZ\d{12}$", "NZ": r"^NZ\d{9}$", "PH": r"^PH\d{12}$", "SA": r"^SA\d{15}$",
    "TW": r"^TW\d{8}$", "UZ": r"^UZ\d{9}$", "AR": r"^AR\d{11}$", "BO": r"^BO\d{7,}$",
    "BR": r"^BR(\d{11}|\d{14})$", "BZ": r"^BZ\d{6}$", "CA": r"^CA[0-9]{9}(R[A-Z][0-9]{4})?$",
    "CL": r"^CL\d{8,9}$", "CO": r"^CO\d{10}$", "CR": r"^CR\d{9,12}$",
    "DO": r"^DO(\d{9}|\d{11})$", "EC": r"^EC\d{13}$", "GT": r"^GT\d{8}$",
    "MX": r"^MX[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$", "NI": r"^NI\d{13}[A-Z]$",
    "PA": r"^PA[A-Z0-9\-\s]+$", "PE": r"^PE\d{11}$", "PY": r"^PY\d{6,9}$",
    "SV": r"^SV\d{14}$", "US": r"^US\d{9}$", "UY": r"^UY\d{12}$",
    "VE": r"^VE[JGVEC]\d{9}$", "AL": r"^AL[J-M]\d{8}[A-Z]$",
    "BY": r"^BY\d{9}$", "NG": r"^NG\d{12}$", "RU": r"^RU(\d{10}|\d{12})$",
}
