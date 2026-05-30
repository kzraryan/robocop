import pytest

from robocop.text2sql import SQLValidationError, validate_sql


def test_passes_simple_select_and_adds_limit():
    out = validate_sql("SELECT * FROM DEMOGRAPHIC")
    assert out.lower().startswith("select")
    assert "limit" in out.lower()


def test_keeps_existing_limit():
    out = validate_sql("SELECT 1 LIMIT 5")
    assert out.lower().count("limit") == 1
    assert out.strip().lower().endswith("limit 5")


def test_strips_markdown_fences():
    out = validate_sql("```sql\nSELECT 1\n```")
    assert "```" not in out
    assert out.lower().startswith("select")


def test_allows_with_cte():
    out = validate_sql("WITH x AS (SELECT 1 AS n) SELECT n FROM x")
    assert out.lower().startswith("with")


@pytest.mark.parametrize(
    "bad",
    [
        "DELETE FROM DEMOGRAPHIC",
        "DROP TABLE DEMOGRAPHIC",
        "UPDATE DEMOGRAPHIC SET SEX='M'",
        "INSERT INTO X VALUES (1)",
        "ATTACH 'evil.db'",
        "COPY DEMOGRAPHIC TO 'x.csv'",
        "PRAGMA database_list",
    ],
)
def test_rejects_non_select(bad):
    with pytest.raises(SQLValidationError):
        validate_sql(bad)


def test_rejects_multiple_statements():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT 1; SELECT 2")


def test_rejects_empty():
    with pytest.raises(SQLValidationError):
        validate_sql("   ")


def test_offset_keyword_not_confused_with_set():
    # 'offset' contains 'set' — must not be flagged by the forbidden matcher.
    out = validate_sql("SELECT n FROM t ORDER BY n LIMIT 5 OFFSET 2")
    assert "offset" in out.lower()
