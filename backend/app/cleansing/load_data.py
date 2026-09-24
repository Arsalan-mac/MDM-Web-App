"""Load Data stage: file parsing, column standardization, cell cleaning.

Ported from the original app's data_upload_module.py
(load_and_harmonize_data, _standardize_columns) and mdm_shared.py
(clean_illegal_chars_df, standardize_columns) - stripped of every Streamlit
call so it can run in an API request or a background job. Currently covers
only the Mandanten (client master data) file; the other reference tables
the original app also loads (Auftraege, Rollen, Klammertabelle,
Verbundene_Parteien, Branchen, Mandant_Gegner, Lieferanten, UserCode) are
ported alongside the pipeline stages that actually consume them, in Phase 2.
"""

import io
import re

import numpy as np
import pandas as pd

from app.cleansing.constants import MANDANT_INTEGER_COLS

_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]")

_NA_VALUES = [
    "", "#N/A", "#NA", "N/A", "NA", "NULL", "Null", "null", "NaN",
    "nan", "none", "<NA>", "NUL", " ",
]

# Maps a standardized column name to every alternate spelling seen in real
# source files - unchanged from the original app's _standardize_columns.
COLUMN_ALIASES: dict[str, list[str]] = {
    "IDParty": ["ID", "IDParty", "Mandantennummer", "PartyID", "﻿IDParty"],
    "CompanyName": ["CompanyName", "Company Name", "Firma", "Name", "Company"],
    "CountryCode": ["CountryCode", "Country", "Land", "Country_Code", "Länderkürzel"],
    "Address": ["Address", "Strasse", "Street", "Address_Line_1", "Adress"],
    "City": ["City", "Town", "Ort", "Stadt"],
    "ZipCode": ["ZipCode", "Zip_Code", "PLZ", "PostalCode", "Postal_Code"],
    "VATNumber": ["VATNumber", "VAT", "USt-IdNr", "UStID", "VatNumber"],
    "IsOrganisation": ["IsOrganisation", "IsOrg", "Is_Organisation"],
    "IsIndividual": ["IsIndividual", "Is_Individual", "IsPerson"],
    "FiscalCode": ["FiscalCode", "Steuernummer", "TaxID", "TIN", "Fiscal_Code"],
    "Email": ["Email", "E-Mail", "Mail", "ContactEmail"],
    "WebSite": ["WebSite", "Website", "Homepage", "URL", "Web"],
    "PhoneNumber": ["PhoneNumber", "Phone", "Telefon", "Mobile", "Tel"],
    "FaxNumber": ["FaxNumber", "Fax", "Telefax"],
    "DateFounded": ["DateFounded", "Founded", "EstablishmentDate"],
    "LiquidationDate": ["LiquidationDate", "Liquidation"],
    "RegisterCourtDate": ["RegisterCourtDate", "RegistrationDate"],
}


class UnsupportedFileType(ValueError):
    pass


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known alternate column spellings to their standard name."""
    rename_map: dict[str, str] = {}
    for standard_name, aliases in COLUMN_ALIASES.items():
        if standard_name in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = standard_name
                break
    return df.rename(columns=rename_map) if rename_map else df


def parse_uploaded_file(filename: str, content: bytes) -> pd.DataFrame:
    """Parse a Mandanten upload (.csv/.txt/.xlsx) into a raw, all-string DataFrame."""
    name = filename.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(
                io.BytesIO(content), dtype=str, sep=None, na_values=_NA_VALUES,
                keep_default_na=True, encoding="utf-8-sig", on_bad_lines="skip",
                quoting=3, engine="python",
            )
        if name.endswith(".txt"):
            return pd.read_csv(
                io.BytesIO(content), dtype=str, sep="\t", na_values=_NA_VALUES,
                keep_default_na=True, encoding="utf-8-sig", on_bad_lines="skip",
                quoting=3, engine="python",
            )
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(io.BytesIO(content), dtype=str, na_values=_NA_VALUES)
    except Exception as exc:
        raise ValueError(f"Could not read '{filename}': {exc}") from exc
    raise UnsupportedFileType(f"Unsupported file type: '{filename}' (expected .csv, .txt or .xlsx)")


def harmonize_reference_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Light cleaning for generic reference tables (Auftraege, VERBUNDENE_
    PARTEIEN, MANDANT_GEGNER, ...) - mirrors the original app's
    load_generic_file, which is deliberately simpler than
    load_and_harmonize_data (below): only strips whitespace from column
    names, never mangles them (no dot/dash/space-to-underscore rewrite).
    That mangling is fine for Mandanten's alias-mapped columns, but these
    tables' column names are fixed source-system field names some of which
    contain meaningful punctuation - e.g. MANDANT_GEGNER's "Client - IDParty"
    would become "Client_IDParty" and silently stop matching its model
    column if run through the Mandanten path instead.
    """
    if df.empty:
        return df

    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]

    for col in df.columns:
        series = df[col].replace(np.nan, "").astype(str).str.strip()
        series = series.replace(["nan", "None", "<NA>"], "")
        series = series.str.replace(_ILLEGAL_CHARS_RE, "", regex=True)
        df[col] = series

    return df


def harmonize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean cell values and standardize column names.

    Mirrors data_upload_module.load_and_harmonize_data: strip BOM/whitespace
    from column names, blank out NA-like strings, strip control characters,
    and drop trailing ".0" on integer-like columns.

    Column standardization runs *before* the integer-column check (the
    original app ran it after, so a column reaching it under an alias like
    "ID" instead of the canonical "IDParty" - both map to the same field -
    silently skipped the ".0" cleanup for that column; MANDANT_INTEGER_COLS
    only lists canonical names, so standardizing first fixes that instead of
    reproducing it).
    """
    if df.empty:
        return df

    df = df.copy()
    df.columns = [col.replace("﻿", "") for col in df.columns]
    df.columns = [
        re.sub(r"\s+", "_", col.replace(".", "_").replace("-", "_").strip())
        for col in df.columns
    ]
    df = standardize_columns(df)

    for col in df.columns:
        series = df[col].replace(np.nan, "").astype(str).str.strip()
        series = series.replace(["nan", "None", "<NA>", ""], pd.NA)
        series = series.str.replace(_ILLEGAL_CHARS_RE, "", regex=True)
        if col in MANDANT_INTEGER_COLS:
            series = series.astype(str).str.replace(r"\.0$", "", regex=True)
        df[col] = series

    return df
