# -*- coding: utf-8 -*-
"""
Gap-closing tests for filtersql.

Covers the four gaps identified after reading sql.py and the existing suite:
  2. Hard-coded safety limits (MAX_IN_LIST, MAX_LIMIT_LENGTH, MAX_FILTER_DEPTH)
  3. SQLite GLOB escaping, live
  4. Scope collision under case / Unicode variation
  5. raw_source + allowed_sources

Run with: pytest test_gaps.py -v
"""

import sqlite3
import unicodedata

import pytest

from filtersql import (
    Datasource,
    filtersql,
    ValidationError,
    InvalidIdentifierError,
)
from filtersql.sql import (
    MAX_IN_LIST,
    MAX_LIMIT_LENGTH,
    MAX_FILTER_DEPTH,
)


def make_ds(**kw):
    kw.setdefault("source", "users")
    kw.setdefault("dbms", "pg")
    kw.setdefault("placeholder", "%s")
    return Datasource(**kw)


# ---------------------------------------------------------------------------
# Gap 2a: MAX_IN_LIST
# ---------------------------------------------------------------------------

class TestMaxInList:

    def test_exactly_max_is_accepted(self):
        ds = make_ds()
        q, v = ds.select(
            columns=["id"],
            filters=[{"field": "id", "operator": "in",
                      "value": list(range(MAX_IN_LIST))}],
        )
        assert len(v) == MAX_IN_LIST
        assert q.count("%s") == MAX_IN_LIST

    def test_max_plus_one_is_rejected(self):
        ds = make_ds()
        with pytest.raises(ValidationError, match=f"at most {MAX_IN_LIST}"):
            ds.select(
                columns=["id"],
                filters=[{"field": "id", "operator": "in",
                          "value": list(range(MAX_IN_LIST + 1))}],
            )

    def test_notin_also_bounded(self):
        ds = make_ds()
        with pytest.raises(ValidationError, match=f"at most {MAX_IN_LIST}"):
            ds.select(
                columns=["id"],
                filters=[{"field": "id", "operator": "notin",
                          "value": list(range(MAX_IN_LIST + 1))}],
            )


# ---------------------------------------------------------------------------
# Gap 2b: MAX_LIMIT_LENGTH
# ---------------------------------------------------------------------------

class TestMaxLimitLength:

    def test_exactly_max_is_accepted(self):
        ds = make_ds()
        q, _ = ds.select(columns=["id"], limit={"length": MAX_LIMIT_LENGTH})
        assert f"limit {MAX_LIMIT_LENGTH}" in q

    def test_max_plus_one_is_rejected(self):
        ds = make_ds()
        with pytest.raises(ValidationError, match=f"cannot exceed {MAX_LIMIT_LENGTH}"):
            ds.select(columns=["id"], limit={"length": MAX_LIMIT_LENGTH + 1})

    def test_string_form_also_bounded(self):
        ds = make_ds()
        with pytest.raises(ValidationError, match=f"cannot exceed {MAX_LIMIT_LENGTH}"):
            ds.select(columns=["id"], limit={"length": str(MAX_LIMIT_LENGTH + 1)})


# ---------------------------------------------------------------------------
# Gap 2c: MAX_FILTER_DEPTH
# ---------------------------------------------------------------------------

def _nested_or(depth):
    """`depth` nested {'or': [...]} groups wrapping one leaf filter."""
    leaf = {"field": "id", "operator": "=", "value": 1}
    node = leaf
    for _ in range(depth):
        node = {"or": [node]}
    return [node]


class TestMaxFilterDepth:

    def test_exactly_max_depth_is_accepted(self):
        # MAX_FILTER_DEPTH nested groups: the leaf ends up at _depth == MAX,
        # and the check is `_depth > MAX_FILTER_DEPTH`, so this must pass.
        ds = make_ds()
        q, v = ds.select(columns=["id"],
                         filters=_nested_or(MAX_FILTER_DEPTH))
        assert v == [1]

    def test_max_plus_one_depth_is_rejected(self):
        ds = make_ds()
        with pytest.raises(ValidationError, match="nested deeper than"):
            ds.select(columns=["id"],
                      filters=_nested_or(MAX_FILTER_DEPTH + 1))

    def test_depth_limit_also_enforced_in_allowed_columns_check(self):
        """
        _check_allowed_filters has its own depth counter and runs before
        the query builder. A pathologically deep filter must be rejected
        there too, not only in _build_filter_group.
        """
        ds = make_ds(allowed_columns={"id"})
        with pytest.raises(ValidationError, match="nested deeper than"):
            ds.select(columns=["id"],
                      filters=_nested_or(MAX_FILTER_DEPTH + 1))


# ---------------------------------------------------------------------------
# Gap 3: SQLite GLOB escaping, live
# ---------------------------------------------------------------------------

@pytest.fixture()
def sqlite_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, label TEXT)")
    cur.executemany(
        "INSERT INTO items (id, label) VALUES (?, ?)",
        [
            (1, "a*b"),
            (2, "axb"),
            (3, "a?b"),
            (4, "ayb"),
            (5, "a[b"),
            (6, "a[b]c"),
            (7, "a]b"),
            (8, "plain"),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


def _sqlite_labels(conn, operator, value):
    ds = Datasource(dbms="sqlite", source="items")
    q, v = ds.select(
        columns=["label"],
        filters=[{"field": "label", "operator": operator, "value": value}],
    )
    return sorted(r["label"] for r in conn.execute(q, v).fetchall())


class TestSQLiteGlobEscaping:
    """
    SQLite uses GLOB for case-sensitive wildcard operators. GLOB treats
    `*`, `?`, `[` as metacharacters; the library escapes them as `[ch]`.
    Every test below inserts both the literal row and a decoy that would
    match if the metacharacter were left unescaped.
    """

    def test_contains_literal_star(self, sqlite_db):
        # If '*' were unescaped, "axb" would also match.
        assert _sqlite_labels(sqlite_db, "contains", "a*b") == ["a*b"]

    def test_contains_literal_question(self, sqlite_db):
        # If '?' were unescaped, "ayb" would also match.
        assert _sqlite_labels(sqlite_db, "contains", "a?b") == ["a?b"]

    def test_contains_literal_open_bracket(self, sqlite_db):
        # '[b' as GLOB is a character class; escaped it must be literal.
        assert _sqlite_labels(sqlite_db, "contains", "a[b") == ["a[b", "a[b]c"]

    def test_contains_literal_close_bracket(self, sqlite_db):
        # ']' is not in the GLOB escape set (it is literal outside a class).
        assert _sqlite_labels(sqlite_db, "contains", "a]b") == ["a]b"]

    def test_starts_with_literal_star(self, sqlite_db):
        assert _sqlite_labels(sqlite_db, "starts_with", "a*") == ["a*b"]

    def test_ends_with_literal_question(self, sqlite_db):
        assert _sqlite_labels(sqlite_db, "ends_with", "?b") == ["a?b"]

    def test_icontains_still_uses_like(self, sqlite_db):
        # Case-insensitive ops go through LIKE, not GLOB: '*' is not a
        # LIKE metacharacter and must pass through unescaped.
        assert _sqlite_labels(sqlite_db, "icontains", "a*b") == ["a*b"]

    def test_icontains_literal_percent(self, sqlite_db):
        # Sanity: LIKE escaping still works on the icontains path.
        sqlite_db.execute("INSERT INTO items (id, label) VALUES (?, ?)",
                          (99, "50% off"))
        sqlite_db.commit()
        assert _sqlite_labels(sqlite_db, "icontains", "50%") == ["50% off"]


# ---------------------------------------------------------------------------
# Gap 4: Scope collision under case / Unicode variation
# ---------------------------------------------------------------------------

class TestScopeCollisionCaseVariation:
    """
    _check_scope_collision normalizes with NFC + casefold. The SQL
    identifiers themselves are case-sensitive on PG, so rejecting
    case-variants is deliberately conservative: it closes the bypass
    on SQLite/MySQL, at the cost of also refusing a genuinely distinct
    PG column. The tests document that contract.
    """

    @pytest.mark.parametrize("variant", [
        "TENANT_ID",
        "Tenant_Id",
        "tenant_ID",
        "TeNaNt_Id",
    ])
    def test_insert_rejects_case_variant(self, variant):
        ds = make_ds(scope={"tenant_id": 42})
        with pytest.raises(ValidationError, match="[Cc]annot set scoped field"):
            ds.insert(values={variant: 999})

    def test_update_rejects_case_variant_in_values(self):
        ds = make_ds(scope={"tenant_id": 42})
        with pytest.raises(ValidationError, match="[Cc]annot set scoped field"):
            ds.update(id={"id": 1}, values={"TENANT_ID": 999})

    def test_update_rejects_case_variant_in_id(self):
        ds = make_ds(scope={"tenant_id": 42})
        with pytest.raises(ValidationError, match="[Cc]annot set scoped field"):
            ds.update(id={"TENANT_ID": 1}, values={"name": "x"})

    def test_delete_rejects_case_variant(self):
        ds = make_ds(scope={"tenant_id": 42})
        with pytest.raises(ValidationError, match="[Cc]annot set scoped field"):
            ds.delete(id={"TENANT_ID": 1})

    def test_nfd_scope_key_rejected_at_init(self):
        """
        A scope key in NFD cannot reach the collision check at all:
        __init__ validates each scope key with _validate_bare_identifier,
        which requires NFC. This is the upstream half of the NFC defence
        the _check_scope_collision docstring describes.
        """
        scope_nfd = unicodedata.normalize("NFD", "quantità")
        with pytest.raises(InvalidIdentifierError):
            Datasource(dbms="pg", source="users", scope={scope_nfd: 1})

    def test_different_column_does_not_collide(self):
        ds = make_ds(scope={"tenant_id": 42})
        q, v = ds.insert(values={"other_id": 5})
        assert '"tenant_id"' in q
        assert '"other_id"' in q
        assert 42 in v and 5 in v


# ---------------------------------------------------------------------------
# Gap 5: raw_source + allowed_sources
# ---------------------------------------------------------------------------

class TestRawSourceAndAllowedSources:
    """
    _check_allowed_source compares self.source verbatim, before quoting
    or raw_source passthrough. raw_source must skip quoting but must NOT
    skip the allowlist check.
    """

    def test_raw_source_not_in_allowlist_is_rejected(self):
        ds = Datasource(
            dbms="pg",
            source="(select * from users) sub",
            raw_source=True,
            allow_raw_source=True,
            allowed_sources={"users"},
        )
        with pytest.raises(ValidationError, match="not in allowed_sources"):
            ds.select(columns=["id"])

    def test_raw_source_listed_verbatim_passes(self):
        raw = "(select * from users) sub"
        ds = Datasource(
            dbms="pg",
            source=raw,
            raw_source=True,
            allow_raw_source=True,
            allowed_sources={raw},
        )
        q, _ = ds.select(columns=["id"])
        assert raw in q

    def test_raw_source_alone_is_not_enough(self):
        """A raw source with no allowlist entry must still fail."""
        ds = Datasource(
            dbms="pg",
            source="(select 1) leak",
            raw_source=True,
            allow_raw_source=True,
            allowed_sources={"users"},
        )
        with pytest.raises(ValidationError, match="not in allowed_sources"):
            ds.select(columns=["id"])

    def test_quoted_source_must_be_in_allowlist(self):
        ds = make_ds(source="users", allowed_sources={"admins"})
        with pytest.raises(ValidationError, match="not in allowed_sources"):
            ds.select(columns=["id"])

    def test_filtersql_function_respects_allowed_sources_for_raw(self):
        """The payload path must not bypass the allowlist."""
        with pytest.raises(ValidationError, match="not in allowed_sources"):
            filtersql(
                payload={
                    "action": "select",
                    "source": "(select 1) leak",
                    "columns": ["id"],
                },
                dbms="pg",
                raw_source=True,
                allow_raw_source=True,
                allowed_sources={"users"},
            )

    def test_write_paths_also_check_allowed_sources(self):
        """allowed_sources applies to insert/update/delete too."""
        ds = make_ds(source="users", allowed_sources={"admins"})
        with pytest.raises(ValidationError, match="not in allowed_sources"):
            ds.insert(values={"name": "x"})
        with pytest.raises(ValidationError, match="not in allowed_sources"):
            ds.update(id={"id": 1}, values={"name": "x"})
        with pytest.raises(ValidationError, match="not in allowed_sources"):
            ds.delete(id={"id": 1})