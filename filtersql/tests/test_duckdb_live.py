# -*- coding: utf-8 -*-
"""
Live tests against an in-memory DuckDB database.
Population is done with filtersql INSERT statements.
"""

import unittest

try:
    import duckdb
except ImportError:
    duckdb = None

from filtersql import filtersql


@unittest.skipIf(duckdb is None, "duckdb is not installed")
class TestLiveDuckDB(unittest.TestCase):

    def setUp(self):
        # In-memory DuckDB
        self.conn = duckdb.connect(database=":memory:")

        # Create table
        self.conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                status TEXT
            )
        """)

        # Populate using filtersql INSERT
        seed_data = [
            {"id": 1, "first_name": "John",  "last_name": "Smith",  "age": 32, "status": "active"},
            {"id": 2, "first_name": "Jane",  "last_name": "Doe",    "age": 28, "status": "active"},
            {"id": 3, "first_name": "Bob",   "last_name": "Smith",  "age": 45, "status": "inactive"},
            {"id": 4, "first_name": "Alice", "last_name": "Wonder", "age": 22, "status": "active"},
            {"id": 5, "first_name": "John",  "last_name": "Doe",    "age": 35, "status": "pending"},
        ]

        for row in seed_data:
            query, values = filtersql({
                "action": "insert",
                "source": "users",
                "values": row,
            }, dbms="DuckDB", placeholder="?")
            self.conn.execute(query, values)

    def tearDown(self):
        self.conn.close()

    def _run(self, payload, **kwargs):
        """Helper: generate SQL with filtersql and execute it."""
        query, values = filtersql(
            payload,
            dbms="DuckDB",
            placeholder="?",
            **kwargs
        )
        return self.conn.execute(query, values).fetchall()

    # ------------------------------------------------------------------
    # Basic SELECT
    # ------------------------------------------------------------------

    def test_select_all(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["id", "first_name", "last_name"],
        })
        self.assertEqual(len(rows), 5)

    def test_filter_eq(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["id", "first_name"],
            "filters": [{"field": "status", "operator": "=", "value": "active"}],
        })
        self.assertEqual(len(rows), 3)

    def test_filter_icontains(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["first_name", "last_name"],
            "filters": [{"field": "last_name", "operator": "icontains", "value": "smi"}],
        })
        self.assertEqual(len(rows), 2)

    def test_filter_between(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["id", "age"],
            "filters": [{"field": "age", "operator": "between", "value": [30, 40]}],
        })
        ages = sorted(r[1] for r in rows)  # age is second column
        self.assertEqual(ages, [32, 35])

    def test_filter_in(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["id", "status"],
            "filters": [{"field": "status", "operator": "in", "value": ["active", "pending"]}],
        })
        self.assertEqual(len(rows), 4)

    def test_or_group(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["first_name"],
            "filters": [{
                "or": [
                    {"field": "first_name", "operator": "=", "value": "John"},
                    {"field": "first_name", "operator": "=", "value": "Alice"},
                ]
            }],
        })
        names = {r[0] for r in rows}
        self.assertEqual(names, {"John", "Alice"})

    # ------------------------------------------------------------------
    # Order + Limit
    # ------------------------------------------------------------------

    def test_order_and_limit(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["id", "age"],
            "order": [{"field": "age", "order": "desc"}],
            "limit": {"start": 0, "length": 2},
        })
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], 45)  # age
        self.assertEqual(rows[1][1], 35)

    # ------------------------------------------------------------------
    # Cursor pagination
    # ------------------------------------------------------------------

    def test_cursor_next(self):
        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["id", "first_name"],
            "order": [{"field": "id", "order": "asc"}],
            "cursor": {"id": 2},
            "direction": "next",
            "limit": {"start": 0, "length": 10},
        })
        ids = [r[0] for r in rows]
        self.assertEqual(ids, [3, 4, 5])

    # ------------------------------------------------------------------
    # Insert / Update / Delete
    # ------------------------------------------------------------------

    def test_insert(self):
        query, values = filtersql({
            "action": "insert",
            "source": "users",
            "values": {
                "id": 6,
                "first_name": "Charlie",
                "last_name": "Brown",
                "age": 27,
                "status": "active",
            }
        }, dbms="DuckDB", placeholder="?")

        self.conn.execute(query, values)

        count = self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE first_name = ?", ["Charlie"]
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_update(self):
        query, values = filtersql({
            "action": "update",
            "source": "users",
            "id": {"id": 1},
            "values": {"status": "archived", "age": 33},
        }, dbms="DuckDB", placeholder="?")

        self.conn.execute(query, values)

        row = self.conn.execute(
            "SELECT status, age FROM users WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "archived")
        self.assertEqual(row[1], 33)

    def test_delete(self):
        query, values = filtersql({
            "action": "delete",
            "source": "users",
            "id": {"id": 5},
        }, dbms="DuckDB", placeholder="?")

        self.conn.execute(query, values)

        count = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(count, 4)

    # ------------------------------------------------------------------
    # Wildcard escaping
    # ------------------------------------------------------------------

    def test_wildcard_literal_percent(self):
        """Searching for literal '50%' must not treat % as wildcard."""
        query, values = filtersql({
            "action": "insert",
            "source": "users",
            "values": {
                "id": 7,
                "first_name": "Promo",
                "last_name": "50% off",
                "age": 0,
                "status": "active",
            }
        }, dbms="DuckDB", placeholder="?")
        self.conn.execute(query, values)

        rows = self._run({
            "action": "select",
            "source": "users",
            "columns": ["last_name"],
            "filters": [{"field": "last_name", "operator": "icontains", "value": "50%"}],
        })
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "50% off")


if __name__ == "__main__":
    unittest.main(verbosity=2)