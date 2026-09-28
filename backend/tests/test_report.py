from app.models.tenant import Mandant


def _typed_attrs():
    # Mirrors report_service.export_mandanten_csv's own computation -
    # exercised directly here since it's the exact thing that broke: using
    # a Column's key (the DB name, "Name 1") instead of the mapper
    # attribute's key (the Python name, "Name1") in getattr() raises
    # AttributeError for every Mandant row, since Python instances only
    # ever have the attribute name, never the DB column name, as an
    # attribute - see app/cleansing/report_service.py.
    return [
        (attr.key, attr.columns[0].name)
        for attr in Mandant.__mapper__.column_attrs
        if attr.key not in ("project_id", "extra")
    ]


def test_typed_attrs_maps_db_name_to_python_attr_for_spaced_columns():
    pairs = dict(_typed_attrs())
    assert pairs["Name1"] == "Name 1"
    assert pairs["Name2"] == "Name 2"


def test_typed_attrs_uses_same_key_for_ordinary_columns():
    pairs = dict(_typed_attrs())
    assert pairs["CompanyName"] == "CompanyName"
    assert pairs["IDParty"] == "IDParty"


def test_typed_attrs_excludes_project_id_and_extra():
    keys = {attr_key for attr_key, _ in _typed_attrs()}
    assert "project_id" not in keys
    assert "extra" not in keys


def test_typed_attrs_getattr_roundtrip_on_a_real_instance():
    # The actual failure mode: getattr(mandant, <db column name>) raises,
    # getattr(mandant, <attr key>) doesn't.
    mandant = Mandant(project_id=None, IDParty="P-1")
    mandant.Name1 = "Test GmbH"
    for attr_key, _ in _typed_attrs():
        getattr(mandant, attr_key)  # must not raise for any typed column
