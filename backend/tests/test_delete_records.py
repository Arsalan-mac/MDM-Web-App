import pytest

from app.cleansing.delete_records_service import InvalidTableOrColumn, _validated_table_and_columns, list_tables


def test_list_tables_excludes_system_tables():
    names = {t["table"] for t in list_tables()}
    assert "projects" not in names
    assert "stages" not in names


def test_list_tables_includes_mandanten():
    names = {t["table"] for t in list_tables()}
    assert "mandanten" in names


def test_mandanten_clearable_excludes_project_id_and_pk():
    mandant = next(t for t in list_tables() if t["table"] == "mandanten")
    assert "project_id" not in mandant["clearable_columns"]
    assert "IDParty" not in mandant["clearable_columns"]


def test_mandanten_all_columns_still_include_idparty():
    mandant = next(t for t in list_tables() if t["table"] == "mandanten")
    assert "IDParty" in mandant["columns"]


def test_mandanten_clearable_includes_ordinary_business_columns():
    mandant = next(t for t in list_tables() if t["table"] == "mandanten")
    assert "CompanyName" in mandant["clearable_columns"]
    assert "Address" in mandant["clearable_columns"]


def test_validate_rejects_unknown_table():
    with pytest.raises(InvalidTableOrColumn):
        _validated_table_and_columns("not_a_real_table", ["x"], for_clearing=True)


def test_validate_rejects_project_id_as_clearable():
    with pytest.raises(InvalidTableOrColumn):
        _validated_table_and_columns("mandanten", ["project_id"], for_clearing=True)


def test_validate_rejects_primary_key_as_clearable():
    with pytest.raises(InvalidTableOrColumn):
        _validated_table_and_columns("mandanten", ["IDParty"], for_clearing=True)


def test_validate_rejects_unknown_column():
    with pytest.raises(InvalidTableOrColumn):
        _validated_table_and_columns("mandanten", ["NotAColumn"], for_clearing=True)


def test_validate_accepts_ordinary_clearable_column():
    table = _validated_table_and_columns("mandanten", ["CompanyName"], for_clearing=True)
    assert table.name == "mandanten"


def test_validate_allows_primary_key_for_matching_not_clearing():
    # IDParty can't be cleared, but it's exactly what you'd match by for
    # the "clear by ID list" mode.
    table = _validated_table_and_columns("mandanten", ["IDParty"], for_clearing=False)
    assert table.name == "mandanten"
