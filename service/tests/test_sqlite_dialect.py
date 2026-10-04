"""The Postgres-to-SQLite statement translation, tested on its own.

Every construct the repositories use is asserted directly, so a failure points at the
translation rather than at an endpoint. The list is short because the query surface is short;
a repository that introduces something new — a window function, a `LATERAL`, a JSONB
operator — will fail here before it fails in production.
"""
from __future__ import annotations

from app.sqlite_backend import _translate


def test_scalar_placeholders_become_qmarks():
    sql, params = _translate("SELECT * FROM t WHERE a = %s AND b = %s", ["x", 1])
    assert sql == "SELECT * FROM t WHERE a = ? AND b = ?"
    assert params == ["x", 1]


def test_any_expands_a_list_into_an_in_list():
    sql, params = _translate("WHERE peptide_id = ANY(%s)", [[1, 2, 3]])
    assert sql == "WHERE peptide_id IN (?, ?, ?)"
    assert params == [1, 2, 3]


def test_any_with_a_scalar_stays_a_comparison():
    sql, params = _translate("WHERE id = ANY(%s)", [7])
    assert sql == "WHERE id = ?"
    assert params == [7]


def test_any_with_an_empty_list_matches_nothing():
    sql, params = _translate("WHERE id = ANY(%s)", [[]])
    assert sql == "WHERE id IN (NULL)"
    assert params == []


def test_two_any_clauses_expand_in_order():
    sql, params = _translate(
        "WHERE peptide_id = ANY(%s) AND tool = ANY(%s)", [[1, 2], ["toxinpred3"]]
    )
    assert sql == "WHERE peptide_id IN (?, ?) AND tool IN (?)"
    assert params == [1, 2, "toxinpred3"]


def test_a_scalar_before_an_any_clause_keeps_its_position():
    sql, params = _translate("WHERE a = %s AND b = ANY(%s)", ["x", [1, 2]])
    assert sql == "WHERE a = ? AND b IN (?, ?)"
    assert params == ["x", 1, 2]


def test_array_containment_becomes_a_json_lookup():
    sql, params = _translate(
        "SELECT id FROM scaffold_library WHERE route_ids @> ARRAY[%s]::text[] ORDER BY id",
        ["wound-dressing"],
    )
    assert "@>" not in sql
    assert "json_each(scaffold_library.route_ids)" in sql
    assert sql.endswith("ORDER BY id")
    assert params == ["wound-dressing"]


def test_text_casts_become_an_explicit_cast():
    # `linkers.id` is an integer column, so `id::text` is what makes the response carry a
    # string id. Dropping the cast would change the value.
    sql, _ = _translate(
        "SELECT id::text AS id, NULL::text AS band, 'linkers'::text AS source_table FROM linkers",
        [],
    )
    assert "::" not in sql
    assert sql == (
        "SELECT CAST(id AS TEXT) AS id, CAST(NULL AS TEXT) AS band, "
        "CAST('linkers' AS TEXT) AS source_table FROM linkers"
    )


def test_an_untranslatable_cast_is_refused():
    import pytest

    with pytest.raises(NotImplementedError):
        _translate("SELECT ARRAY['x']::text[] AS a", [])


def test_named_parameters_are_rejected_loudly():
    import pytest

    with pytest.raises(NotImplementedError):
        _translate("SELECT * FROM t WHERE a = %(value)s", {"value": 1})
