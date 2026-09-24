import pandas as pd

from app.cleansing.load_data import harmonize_dataframe, parse_uploaded_file, standardize_columns


def test_standardize_columns_renames_known_aliases():
    df = pd.DataFrame({"ID": ["1"], "Firma": ["Acme"], "PLZ": ["12345"]})
    result = standardize_columns(df)
    assert list(result.columns) == ["IDParty", "CompanyName", "ZipCode"]


def test_standardize_columns_prefers_existing_standard_name():
    df = pd.DataFrame({"IDParty": ["1"], "ID": ["2"]})
    result = standardize_columns(df)
    # IDParty already present - the alias "ID" is left alone, not overwritten.
    assert "ID" in result.columns
    assert result["IDParty"].iloc[0] == "1"


def test_parse_uploaded_file_csv():
    content = "ID,Firma,PLZ\n1,Acme GmbH,10115\n2,Beta AG,80331\n".encode("utf-8-sig")
    df = parse_uploaded_file("mandanten.csv", content)
    assert len(df) == 2
    assert list(df.columns) == ["ID", "Firma", "PLZ"]


def test_harmonize_dataframe_cleans_and_standardizes():
    df = pd.DataFrame({
        "ID": ["1.0", "2.0"],
        "Firma": [" Acme GmbH ", "Beta AG\x00"],
        "PLZ": ["10115", "nan"],
    })
    result = harmonize_dataframe(df)
    assert list(result.columns) == ["IDParty", "CompanyName", "ZipCode"]
    assert result["IDParty"].iloc[0] == "1"  # trailing .0 stripped (int-like column)
    assert result["CompanyName"].iloc[0] == "Acme GmbH"  # whitespace trimmed
    assert result["CompanyName"].iloc[1] == "Beta AG"  # illegal control char stripped
    assert pd.isna(result["ZipCode"].iloc[1])  # "nan" string normalized to NA
