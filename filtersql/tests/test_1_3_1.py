import os
import pytest
import threading
from decimal import Decimal
from fractions import Fraction
from filtersql import (
    Datasource,
    filtersql,
    ValidationError,
    InvalidIdentifierError,
    ConfigurationError,
)


# ---------------------------------------------------------------------------
# 1. Logical NOT groups & deeply nested boolean trees
# ---------------------------------------------------------------------------

def test_not_group_with_single_dict():
    ds = Datasource(dbms="sqlite", source="users")
    sql, vals = ds.where(filters=[
        {"field": "active", "operator": "=", "value": 1},
        {"not": {"field": "role", "operator": "=", "value": "banned"}},
    ])
    assert sql == '("active" = ? and not ("role" = ?))'
    assert vals == [1, "banned"]


def test_not_group_with_list_implies_and():
    ds = Datasource(dbms="pg", source="users")
    sql, vals = ds.where(filters=[
        {"field": "status", "operator": "=", "value": "active"},
        {
            "not": [
                {"field": "role", "operator": "=", "value": "guest"},
                {"field": "locked", "operator": "=", "value": True},
            ]
        },
    ])
    assert sql == '("status" = %s and not ("role" = %s and "locked" = %s))'
    assert vals == ["active", "guest", True]


def test_or_not_and_nested_not_combinations():
    ds = Datasource(dbms="sqlite", source="orders")
    sql, vals = ds.where(filters=[
        {
            "or": [
                {"field": "priority", "operator": "=", "value": "high"},
                {
                    "not": [
                        {"field": "archived", "operator": "=", "value": 1},
                        {
                            "or": [
                                {"field": "amount", "operator": "<", "value": 10},
                                {"field": "status", "operator": "=", "value": "draft"},
                            ]
                        },
                    ]
                },
            ]
        }
    ])
    assert (
        sql
        == '(("priority" = ? or not ("archived" = ? and ("amount" < ? or "status" = ?))))'
    )
    assert vals == ["high", 1, 10, "draft"]


def test_not_group_rejects_invalid_type():
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="Expected dict or list for 'not' group"):
        ds.where(filters=[{"not": "invalid"}])


def test_hybrid_group_dict_is_rejected():
    """A filter dict cannot mix group keys ('not'/'and'/'or') with leaf keys or other group keys."""
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="single group key"):
        ds.where(filters=[
            {"not": [{"field": "a", "operator": "=", "value": 1}], "field": "b", "operator": "=", "value": 2}
        ])
    with pytest.raises(ValidationError, match="single group key"):
        ds.where(filters=[
            {"and": [{"field": "a", "operator": "=", "value": 1}], "or": [{"field": "b", "operator": "=", "value": 2}]}
        ])


# ---------------------------------------------------------------------------
# 2. Security: allowed_columns enforcement across nested NOT / AND / OR
# ---------------------------------------------------------------------------

def test_allowed_columns_blocks_unlisted_field_inside_not_dict():
    ds = Datasource(
        dbms="pg",
        source="users",
        allowed_columns={"id", "status"},
    )
    with pytest.raises(ValidationError, match="Column 'password_hash' is not in allowed_columns"):
        ds.select(
            columns=["id"],
            filters=[
                {"field": "status", "operator": "=", "value": "active"},
                {"not": {"field": "password_hash", "operator": "=", "value": "xyz"}},
            ],
        )


def test_allowed_columns_blocks_unlisted_field_deep_inside_nested_groups():
    ds = Datasource(
        dbms="pg",
        source="users",
        allowed_columns={"id", "status", "role"},
    )
    nested_filters = [
        {
            "and": [
                {"field": "status", "operator": "=", "value": "active"},
                {
                    "not": [
                        {"field": "role", "operator": "=", "value": "admin"},
                        {
                            "or": [
                                {"field": "secret_token", "operator": "notnull"}
                            ]
                        },
                    ]
                },
            ]
        }
    ]
    with pytest.raises(ValidationError, match="Column 'secret_token' is not in allowed_columns"):
        ds.select(columns=["id"], filters=nested_filters)

    with pytest.raises(ValidationError, match="Column 'secret_token' is not in allowed_columns"):
        ds.having(filters=nested_filters)


def test_allowed_columns_blocks_raw_inside_not_group():
    ds = Datasource(
        dbms="pg",
        source="users",
        allow_raw_fields=True,
        allowed_columns={"id"},
    )
    with pytest.raises(ValidationError, match="raw filters are not permitted when allowed_columns is set"):
        ds.select(
            columns=["id"],
            filters=[{"not": {"field": "1=1", "operator": "=", "value": 1, "raw": True}}],
        )


# ---------------------------------------------------------------------------
# 3. Oracle dialect & numbered placeholders (:{n}) + _split_binds lexer
# ---------------------------------------------------------------------------

def test_oracle_select_with_where_having_and_limit():
    ds = Datasource(dbms="oracle", source="employees", scope={"tenant_id": 99})
    sql, vals = ds.select(
        columns=["dept", "salary"],
        filters=[
            {"field": "name", "operator": "icontains", "value": "rossi"},
            {"not": {"field": "status", "operator": "in", "value": ["terminated", "leave"]}},
        ],
        group_by=["dept", "salary"],
        having=[{"field": "salary", "operator": ">", "value": 3000}],
        order=[{"field": "salary", "order": "desc"}],
        limit={"start": 10, "length": 25},
    )
    assert 'upper("name") like upper(:2) escape \'\\\'' in sql
    assert 'not ("status" in (:3, :4))' in sql
    assert 'having\n  "salary" > :5' in sql
    assert "offset 10 rows fetch next 25 rows only" in sql
    assert vals == [99, "%rossi%", "terminated", "leave", 3000]


def test_oracle_update_continuous_bind_numbering():
    ds = Datasource(dbms="oracle", source="users", scope={"org_id": 7})
    sql, vals = ds.update(
        id={"id": 42},
        values={"name": "Mario", "role": "admin"},
    )
    assert '"name" = :1' in sql
    assert '"role" = :2' in sql
    assert '("org_id" = :3 and "id" = :4)' in sql
    assert vals == ["Mario", "admin", 7, 42]


def test_debug_lexer_with_oracle_and_fixed_placeholders(monkeypatch):
    monkeypatch.setenv("FILTERSQL_DEBUG", "1")

    # Oracle (:1, :2) ignoring ':1' inside string literal
    ds_ora = Datasource(dbms="oracle", source="users")
    q_ora, v_ora = ds_ora.select(
        filters=[
            {"field": "note", "operator": "=", "value": "literal :1 and :2"},
            {"field": "id", "operator": "=", "value": 10},
        ]
    )
    rendered_ora = ds_ora.debug(q_ora, v_ora)
    assert '"note" = \'literal :1 and :2\' and "id" = 10' in rendered_ora

    # Postgres (%s) and SQLite (?) must not raise IndexError in _split_binds
    for dbms in ("pg", "sqlite", "mysql", "duckdb"):
        ds = Datasource(dbms=dbms, source="users")
        q, v = ds.select(filters=[{"field": "name", "operator": "=", "value": "test"}])
        rendered = ds.debug(q, v)
        assert "'test'" in rendered


# ---------------------------------------------------------------------------
# 4. Bugfixes: boolean limit, dotted identifiers, aliases, returning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_limit", [
    {"start": True, "length": 10},
    {"start": 0, "length": False},
    {"start": False, "length": True},
])
def test_limit_rejects_booleans(bad_limit):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="integer"):
        ds.select(columns=["id"], limit=bad_limit)


@pytest.mark.parametrize("bad_limit", [
    {"length": 2.9},
    {"length": 0.5},
    {"length": -1.5},       # truncates to -1, but sign check fires too
    {"start": 1.5},
    {"start": 0.9, "length": 10},
    {"length": Decimal("2.9")},
    {"start": Fraction(3, 2)},
])
def test_limit_rejects_non_integral_numbers(bad_limit):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="must be an integer"):
        ds.select(columns=["id"], limit=bad_limit)


@pytest.mark.parametrize("ok_limit", [
    {"length": 3.0},
    {"start": 0.0, "length": 10.0},
    {"length": Decimal("3")},
    {"start": Fraction(0, 1), "length": Fraction(10, 1)},
    {"length": "10"},
    {"start": "0", "length": "50"},
])
def test_limit_accepts_integer_like_values(ok_limit):
    ds = Datasource(dbms="sqlite", source="users")
    sql, params = ds.select(columns=["id"], limit=ok_limit)
    assert "limit" in sql.lower()

def test_limit_non_numeric_string_rejected():
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="must be an integer"):
        ds.select(columns=["id"], limit={"length": "two"})

@pytest.mark.parametrize("bad_ident", [
    "users..name",
    ".users",
    "users.",
    "a.b.c",
])
def test_quote_rejects_malformed_dotted_identifiers(bad_ident):
    ds = Datasource(dbms="pg", source="users")
    with pytest.raises(InvalidIdentifierError):
        ds.select(columns=[bad_ident])


def test_select_alias_rejects_dots_and_jsonb():
    ds = Datasource(dbms="pg", source="users")
    with pytest.raises(InvalidIdentifierError):
        ds.select(columns=[{"field": "name", "alias": "table.alias"}])
    with pytest.raises(InvalidIdentifierError):
        ds.select(columns=[{"field": "name", "alias": "data->>key"}])


@pytest.mark.parametrize("dbms", ["pg", "sqlite", "duckdb"])
def test_insert_returning_supported_dialects(dbms):
    ds = Datasource(dbms=dbms, source="users")
    sql, vals = ds.insert(values={"name": "Alice"}, returning="id")
    assert sql.endswith('returning "id"')
    assert vals == ["Alice"]


def test_datasource_missing_source_raises_configuration_error():
    ds = Datasource(dbms="pg")
    with pytest.raises(ConfigurationError, match="non-empty string 'source'"):
        ds.select()

# ---------------------------------------------------------------------------
# Cursor value validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("direction", ["next", "prev", "seek"])
def test_cursor_rejects_none_value(direction):
    ds = Datasource(
        dbms="sqlite",
        source="users",
        order=[{"field": "id", "order": "asc"}],
    )
    with pytest.raises(ValidationError, match="cannot be None"):
        ds.select(
            columns=["id"],
            cursor={"id": None},
            direction=direction,
        )


def test_cursor_rejects_none_in_multi_column():
    ds = Datasource(
        dbms="sqlite",
        source="users",
        order=[
            {"field": "last_name",  "order": "asc"},
            {"field": "first_name", "order": "asc"},
        ],
    )
    with pytest.raises(ValidationError, match="cannot be None"):
        ds.select(
            columns=["id"],
            cursor={"last_name": "Smith", "first_name": None},
            direction="next",
        )


@pytest.mark.parametrize("bad_value", [[], [1, 2], {}, (1,), {"a": 1}])
def test_cursor_rejects_non_scalar_value(bad_value):
    ds = Datasource(
        dbms="sqlite",
        source="users",
        order=[{"field": "id", "order": "asc"}],
    )
    with pytest.raises(ValidationError, match="must be a scalar"):
        ds.select(
            columns=["id"],
            cursor={"id": bad_value},
            direction="next",
        )


def test_cursor_accepts_normal_scalars():
    """Sanity: valid scalar cursor values still work."""
    ds = Datasource(
        dbms="sqlite",
        source="users",
        order=[{"field": "id", "order": "asc"}],
    )
    sql, params = ds.select(
        columns=["id"],
        cursor={"id": 42},
        direction="next",
    )
    assert '"id" > ?' in sql
    assert params == [42]

def test_direction_validated_without_cursor():
    """Regression: direction='garbage' with no cursor used to be a silent no-op."""
    ds = Datasource(
        dbms="sqlite",
        source="users",
        order=[{"field": "id", "order": "asc"}],
    )
    with pytest.raises(ValidationError, match="Invalid direction"):
        ds.select(columns=["id"], direction="garbage")
    with pytest.raises(ValidationError, match="Invalid direction"):
        ds.select(columns=["id"], cursor={"id": 5}, direction="garbage")

# ---------------------------------------------------------------------------
# in / notin / between — non-scalar elements
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op", ["in", "notin"])
@pytest.mark.parametrize("bad_value", [
    [{}],
    [{"a": 1}],
    [[1, 2]],
    [(1,)],
    [1, {}],
])
def test_in_operators_reject_container_elements(op, bad_value):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="expects scalar values"):
        ds.select(
            columns=["id"],
            filters=[{"field": "id", "operator": op, "value": bad_value}],
        )


@pytest.mark.parametrize("op", ["in", "notin"])
@pytest.mark.parametrize("bad_value", [{}, {"a": 1}, set(), {1, 2}])
def test_in_operators_reject_dict_or_set_as_value(op, bad_value):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="expects a scalar or a list"):
        ds.select(
            columns=["id"],
            filters=[{"field": "id", "operator": op, "value": bad_value}],
        )


@pytest.mark.parametrize("bad_value", [
    [{}, 5],
    [5, {}],
    [[1, 2], 3],
    [None, 5],
    [5, None],
])
def test_between_rejects_container_or_none_elements(bad_value):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError):
        ds.select(
            columns=["id"],
            filters=[{"field": "id", "operator": "between", "value": bad_value}],
        )


@pytest.mark.parametrize("op", ["in", "notin"])
@pytest.mark.parametrize("good_value", [
    [1, 2, 3],
    (1, 2, 3),
    ["a", "b"],
    [1.5, 2.5],
    [True, False],
])
def test_in_operators_accept_scalar_lists(op, good_value):
    ds = Datasource(dbms="sqlite", source="users")
    sql, params = ds.select(
        columns=["id"],
        filters=[{"field": "id", "operator": op, "value": good_value}],
    )
    assert len(params) == len(good_value)


def test_between_accepts_tuple_of_two_scalars():
    ds = Datasource(dbms="sqlite", source="users")
    sql, params = ds.select(
        columns=["id"],
        filters=[{"field": "id", "operator": "between", "value": (10, 20)}],
    )
    assert params == [10, 20]

# --- limit={} ---
def test_limit_empty_dict_uses_defaults():
    ds = Datasource(dbms="sqlite", source="users")
    sql, _ = ds.select(columns=["id"], limit={})
    assert "limit 0, 100" in sql.lower()   # SQLite template: 'limit {start}, {length}'

def test_limit_none_still_emits_no_limit_clause():
    ds = Datasource(dbms="sqlite", source="users")
    sql, _ = ds.select(columns=["id"], limit=None)
    assert "limit" not in sql.lower()


# --- order duplicates ---
def test_order_rejects_duplicate_field():
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="Duplicate field"):
        ds.select(
            columns=["id"],
            order=[
                {"field": "id", "order": "asc"},
                {"field": "id", "order": "desc"},
            ],
        )

def test_order_allows_distinct_fields():
    ds = Datasource(dbms="sqlite", source="users")
    sql, _ = ds.select(
        columns=["id"],
        order=[
            {"field": "last_name", "order": "asc"},
            {"field": "first_name", "order": "asc"},
        ],
    )
    assert '"last_name" asc' in sql and '"first_name" asc' in sql


# --- scalar containers ---
@pytest.mark.parametrize("bad_value", [
    {1, 2},
    frozenset({1, 2}),
    {1},
])
def test_scalar_operator_rejects_set_value(bad_value):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="single scalar value"):
        ds.select(
            columns=["id"],
            filters=[{"field": "id", "operator": "=", "value": bad_value}],
        )


# --- columns falsy ---
@pytest.mark.parametrize("bad_columns", [0, False, ""])
def test_columns_rejects_falsy_non_none(bad_columns):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="Expected list as 'columns'"):
        ds.select(columns=bad_columns)


# --- OverflowError ---
@pytest.mark.parametrize("bad_length", [
    float("inf"),
    float("-inf"),
    Decimal("Infinity"),
    Decimal("-Infinity"),
])
def test_limit_rejects_infinite(bad_length):
    ds = Datasource(dbms="sqlite", source="users")
    with pytest.raises(ValidationError, match="must be an integer"):
        ds.select(columns=["id"], limit={"length": bad_length})

def test_oracle_bind_numbering_is_thread_safe():
    """
    Regression: with a shared Oracle Datasource, `_bind_n` was an
    instance attribute, so concurrent builds corrupted the :{n}
    numbering (e.g. :2, :3...:7 instead of :1, :2...:6).
    """
    ds = Datasource(
        dbms="oracle",
        source="users",
        scope={"tenant_id": 1},
    )

    N = 8
    results = [None] * N
    barrier = threading.Barrier(N)

    def worker(i: int) -> None:
        barrier.wait()
        results[i] = ds.select(
            columns=["id", "name"],
            filters=[
                {"field": "status", "operator": "=", "value": "active"},
                {"field": "age",    "operator": ">", "value": 30},
            ],
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    sqls = {sql for sql, _ in results}
    assert len(sqls) == 1, (
        f"Bind numbering not thread-safe: got {len(sqls)} distinct SQLs. "
        f"Samples: {sorted(sqls)[:2]}"
    )

    sql = next(iter(sqls))
    # Expected order: scope first (:1 = tenant_id), then client filters
    # (:2 = status, :3 = age).
    assert ":1" in sql and ":2" in sql and ":3" in sql
    assert ":4" not in sql
    for _, params in results:
        assert params == [1, "active", 30]
