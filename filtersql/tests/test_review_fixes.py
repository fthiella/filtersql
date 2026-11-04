# -*- coding: utf-8 -*-
"""Regression tests for the review fixes: fail-closed policy arguments,
FilterSQLError hierarchy, and parseDatatableArgs robustness."""
import pytest

import filtersql
from filtersql import Datasource, ValidationError, InvalidIdentifierError, FilterSQLError
from filtersql.utils import parseDatatableArgs

SEL = {"action": "select", "source": "users", "columns": ["id"]}


# 1. policy arguments are keyword-only and misspellings are errors ----------

@pytest.mark.parametrize("bad", [
    {"allowed_column": {"id"}},
    {"allowed_source": {"users"}},
    {"scopes": {"tenant_id": 1}},
    {"allow_raw_field": True},
])
def test_misspelled_policy_argument_raises(bad):
    with pytest.raises(TypeError):
        filtersql.filtersql(SEL, dbms="sqlite", **bad)


def test_payload_fields_as_kwargs_are_rejected():
    with pytest.raises(TypeError):
        filtersql.filtersql({"action": "select", "source": "u", "columns": ["id"]},
                            dbms="pg", cursor={"id": 1}, direction="next")


def test_splat_of_client_keys_raises():
    with pytest.raises(TypeError):
        filtersql.filtersql(dbms="sqlite", **SEL)


def test_payload_is_required_and_must_be_dict():
    with pytest.raises(TypeError):
        filtersql.filtersql(dbms="sqlite")
    with pytest.raises(ValidationError):
        filtersql.filtersql(None, dbms="sqlite")


def test_dbms_is_required():
    with pytest.raises(TypeError):
        filtersql.filtersql(SEL)


def test_dbms_is_keyword_only():
    with pytest.raises(TypeError):
        filtersql.filtersql(SEL, "sqlite")


def test_payload_policy_keys_still_rejected():
    with pytest.raises(ValidationError):
        filtersql.filtersql({**SEL, "scope": {"a": 1}}, dbms="sqlite")


def test_valid_call_unchanged():
    q, v = filtersql.filtersql(SEL, dbms="sqlite", allowed_columns={"id"},
                               scope={"tenant_id": 1})
    assert '"tenant_id" = ?' in q and v == [1]


# 2. non-string identifiers -> FilterSQLError, never TypeError --------------

def test_invalid_identifier_is_validation_error():
    assert issubclass(InvalidIdentifierError, ValidationError)
    assert issubclass(InvalidIdentifierError, FilterSQLError)


@pytest.mark.parametrize("allowed", [None, {"a"}])
@pytest.mark.parametrize("bad", [["a"], {"x": 1}, 5, None])
def test_order_field_non_string(allowed, bad):
    ds = Datasource(source="u", dbms="sqlite", allowed_columns=allowed)
    with pytest.raises(FilterSQLError):
        ds.select(columns=["a"], order=[{"field": bad}])


@pytest.mark.parametrize("allowed", [None, {"a"}])
@pytest.mark.parametrize("bad", [["a"], {"x": 1}, 5])
def test_group_by_non_string(allowed, bad):
    ds = Datasource(source="u", dbms="sqlite", allowed_columns=allowed)
    with pytest.raises(FilterSQLError):
        ds.select(columns=["a"], group_by=[bad])


@pytest.mark.parametrize("bad", [["a"], {"x": 1}, 5])
def test_filter_field_non_string(bad):
    ds = Datasource(source="u", dbms="sqlite")
    with pytest.raises(InvalidIdentifierError, match="must be a string"):
        ds.select(filters=[{"field": bad, "operator": "=", "value": 1}])
    with pytest.raises(InvalidIdentifierError, match="must be a string"):
        ds.select(columns=[{"field": bad}])


def test_write_keys_non_string():
    ds = Datasource(source="u", dbms="sqlite")
    with pytest.raises(FilterSQLError):
        ds.update(id={5: 1}, values={"a": 1})


# 3. parseDatatableArgs ------------------------------------------------------

def test_dt_basic_nesting():
    r = parseDatatableArgs({
        "draw": "1", "start": "0", "length": "10",
        "columns[0][data]": "id",
        "columns[0][search][value]": "x",
        "order[0][column]": "0",
        "search[value]": "q",
    })
    assert r["draw"] == "1"
    assert r["columns"][0]["data"] == "id"
    assert r["columns"][0]["search"]["value"] == "x"
    assert r["order"][0]["column"] == "0"
    assert r["search"]["value"] == "q"


def test_dt_unicode_digit_does_not_crash():
    r = parseDatatableArgs({"columns[²][data]": "a", "columns[٣][data]": "b"})
    assert r["columns"]["²"]["data"] == "a"


def test_dt_conflicting_keys_do_not_crash():
    r = parseDatatableArgs({"columns[0][data]": "a", "columns[0][data][x]": "b"})
    assert r["columns"][0]["data"] == "a"
    r = parseDatatableArgs({"columns[0][data][x]": "b", "columns[0][data]": "a"})
    assert r["columns"][0]["data"] == {"x": "b"}


def test_dt_unmatched_keys_are_skipped_silently(capsys):
    assert parseDatatableArgs({"foo": "1", "a[": "2"}) == {}
    assert capsys.readouterr().out == ""


def test_dt_none_value_is_a_leaf_and_first_wins():
    class D(dict):
        pass
    r = parseDatatableArgs(D({"a[0][b]": None, "a[0][b][c]": "x"}))
    assert r["a"][0]["b"] is None


def test_dt_non_string_keys_are_skipped():
    assert parseDatatableArgs({5: "x", "draw": "1"}) == {"draw": "1"}


@pytest.mark.parametrize("bad", [None, 0, [], {}])
def test_falsy_non_string_fields_report_type(bad):
    ds = Datasource(source="u", dbms="sqlite")
    with pytest.raises(InvalidIdentifierError, match="must be a string"):
        ds.select(columns=["a"], order=[{"field": bad}])
    with pytest.raises(InvalidIdentifierError, match="must be a string"):
        ds.select(filters=[{"field": bad, "operator": "=", "value": 1}])
    with pytest.raises(InvalidIdentifierError, match="must be a string"):
        ds.select(columns=[{"field": bad}])


def test_missing_field_key_is_a_validation_error():
    ds = Datasource(source="u", dbms="sqlite")
    with pytest.raises(ValidationError, match="field"):
        ds.select(columns=["a"], order=[{"order": "asc"}])
    with pytest.raises(ValidationError, match="field"):
        ds.select(filters=[{"operator": "=", "value": 1}])
    with pytest.raises(ValidationError, match="field"):
        ds.select(columns=[{"alias": "x"}])


def test_columns_dict_field_empty_string_and_raw_unchanged():
    ds = Datasource(source="u", dbms="sqlite")
    with pytest.raises(InvalidIdentifierError, match="empty"):
        ds.select(columns=[{"field": ""}])
    raw = Datasource(source="u", dbms="sqlite", allow_raw_fields=True)
    q, _ = raw.select(columns=[{"field": "count(*)", "raw": True, "alias": "n"}])
    assert "count(*)" in q

@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("bad", [["a"], {"x": 1}, 5, None, 0, [], {}, ""])
def test_column_dict_field_non_string_or_empty(raw, bad):
    ds = Datasource(source="u", dbms="sqlite", allow_raw_fields=True)
    with pytest.raises(InvalidIdentifierError):
        ds.select(columns=[{"field": bad, "raw": raw}])


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("bad", [["a"], {"x": 1}, 5, None, 0, [], {}, ""])
def test_filter_field_non_string_or_empty(raw, bad):
    ds = Datasource(source="u", dbms="sqlite", allow_raw_fields=True)
    with pytest.raises(InvalidIdentifierError):
        ds.select(filters=[{"field": bad, "operator": "=", "value": 1, "raw": raw}])
