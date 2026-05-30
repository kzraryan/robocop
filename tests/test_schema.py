from robocop.schema import parse_schema, schema_prompt


def test_parses_all_tables():
    tables = parse_schema()
    # 11 structured tables documented in column_descriptions.txt
    assert len(tables) == 11
    assert "CONDITION" in tables          # first block, guards against BOM regressions
    assert "OBS_CLIN_NICU_VENT" in tables


def test_demographic_columns():
    t = parse_schema()["DEMOGRAPHIC"]
    names = [c.name for c in t.columns]
    assert names == ["PATID", "RACE", "SEX", "BIRTH_DATE", "GESTATIONAL_AGE"]


def test_schema_prompt_includes_notes_and_note_table():
    p = schema_prompt()
    assert "GESTATIONAL_AGE" in p
    assert "NOTE:" in p          # model hints carried through
    assert "TABLE NOTE" in p     # synthetic NOTE table advertised
