# -*- coding: utf-8 -*-
"""
Live tests against a real Postgres.

Uses the default ``%s`` placeholder (psycopg2 / psycopg).

    PG_URL=postgresql://user:pass@127.0.0.1:5432/filtersql_test

or ``POSTGRES_URL``, or:

    PG_HOST=127.0.0.1
    PG_PORT=5432
    PG_USER=postgres
    PG_PASSWORD=
    PG_DATABASE=filtersql_test

Needs ``psycopg2`` or ``psycopg`` (v3). Skipped when no URL/host is set.
"""

import os
import unittest
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from filtersql import filtersql


def _load_dotenv():
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"]
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _connect():
    _load_dotenv()
    url = (
        os.environ.get("PG_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("DATABASE_URL")
    )
    host = os.environ.get("PG_HOST") or os.environ.get("POSTGRES_HOST")
    if not url and not host:
        return None

    if url:
        parsed = urlparse(url)
        conf = {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 5432,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "dbname": (parsed.path or "").lstrip("/") or None,
        }
    else:
        conf = {
            "host": host,
            "port": int(os.environ.get("PG_PORT") or os.environ.get("POSTGRES_PORT") or 5432),
            "user": os.environ.get("PG_USER") or os.environ.get("POSTGRES_USER") or "postgres",
            "password": os.environ.get("PG_PASSWORD") or os.environ.get("POSTGRES_PASSWORD") or "",
            "dbname": os.environ.get("PG_DATABASE") or os.environ.get("POSTGRES_DATABASE"),
        }
    if not conf.get("dbname"):
        raise unittest.SkipTest("PG_URL / PG_DATABASE must name a database.")

    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(**conf)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return conn, cur
    except ImportError:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(**conf)
        cur = conn.cursor(row_factory=dict_row)
        return conn, cur


class TestLivePostgres(unittest.TestCase):

    def setUp(self):
        connected = _connect()
        if connected is None:
            self.skipTest("Set PG_URL or PG_HOST to run live Postgres tests.")
        self.conn, self.cur = connected
        self.table = "filtersql_live_" + uuid.uuid4().hex[:12]
        self.cur.execute(
            f"""
            CREATE TABLE "{self.table}" (
                id integer PRIMARY KEY,
                first_name text,
                last_name text,
                age integer,
                status text
            )
            """
        )
        self.conn.commit()

        seed_data = [
            {"id": 1, "first_name": "John",  "last_name": "Smith",  "age": 32, "status": "active"},
            {"id": 2, "first_name": "Jane",  "last_name": "Doe",    "age": 28, "status": "active"},
            {"id": 3, "first_name": "Bob",   "last_name": "Smith",  "age": 45, "status": "inactive"},
            {"id": 4, "first_name": "Alice", "last_name": "Wonder", "age": 22, "status": "active"},
            {"id": 5, "first_name": "John",  "last_name": "Doe",    "age": 35, "status": "pending"},
        ]
        for row in seed_data:
            query, values = self._compile({
                "action": "insert",
                "source": self.table,
                "values": row,
            })
            self.cur.execute(query, values)
        self.conn.commit()

    def tearDown(self):
        conn = getattr(self, "conn", None)
        if conn is None:
            return
        try:
            self.cur.execute(f'DROP TABLE IF EXISTS "{self.table}"')
            self.conn.commit()
        finally:
            self.conn.close()

    def _compile(self, payload):
        return filtersql(payload, dbms="Pg")

    def _run(self, payload):
        query, values = self._compile(payload)
        self.cur.execute(query, values)
        return self.cur.fetchall()

    def test_select_all(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["id", "first_name", "last_name"],
        })
        self.assertEqual(len(rows), 5)

    def test_filter_eq(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["id", "first_name"],
            "filters": [{"field": "status", "operator": "=", "value": "active"}],
        })
        self.assertEqual(len(rows), 3)

    def test_filter_icontains(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["first_name", "last_name"],
            "filters": [{"field": "last_name", "operator": "icontains", "value": "smi"}],
        })
        self.assertEqual(len(rows), 2)

    def test_filter_between(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["id", "age"],
            "filters": [{"field": "age", "operator": "between", "value": [30, 40]}],
        })
        ages = sorted(r["age"] for r in rows)
        self.assertEqual(ages, [32, 35])

    def test_filter_in(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["id", "status"],
            "filters": [{"field": "status", "operator": "in", "value": ["active", "pending"]}],
        })
        self.assertEqual(len(rows), 4)

    def test_or_group(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["first_name"],
            "filters": [{
                "or": [
                    {"field": "first_name", "operator": "=", "value": "John"},
                    {"field": "first_name", "operator": "=", "value": "Alice"},
                ]
            }],
        })
        names = {r["first_name"] for r in rows}
        self.assertEqual(names, {"John", "Alice"})

    def test_order_and_limit(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["id", "age"],
            "order": [{"field": "age", "order": "desc"}],
            "limit": {"start": 0, "length": 2},
        })
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["age"], 45)
        self.assertEqual(rows[1]["age"], 35)

    def test_cursor_next(self):
        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["id", "first_name"],
            "order": [{"field": "id", "order": "asc"}],
            "cursor": {"id": 2},
            "direction": "next",
            "limit": {"start": 0, "length": 10},
        })
        ids = [r["id"] for r in rows]
        self.assertEqual(ids, [3, 4, 5])

    def test_insert(self):
        query, values = self._compile({
            "action": "insert",
            "source": self.table,
            "values": {
                "id": 6,
                "first_name": "Charlie",
                "last_name": "Brown",
                "age": 27,
                "status": "active",
            },
        })
        self.cur.execute(query, values)
        self.conn.commit()

        self.cur.execute(
            f'SELECT COUNT(*) AS n FROM "{self.table}" WHERE first_name = %s',
            ("Charlie",),
        )
        self.assertEqual(self.cur.fetchone()["n"], 1)

    def test_update(self):
        query, values = self._compile({
            "action": "update",
            "source": self.table,
            "id": {"id": 1},
            "values": {"status": "archived", "age": 33},
        })
        self.cur.execute(query, values)
        self.conn.commit()

        self.cur.execute(
            f'SELECT status, age FROM "{self.table}" WHERE id = 1'
        )
        row = self.cur.fetchone()
        self.assertEqual(row["status"], "archived")
        self.assertEqual(row["age"], 33)

    def test_delete(self):
        query, values = self._compile({
            "action": "delete",
            "source": self.table,
            "id": {"id": 5},
        })
        self.cur.execute(query, values)
        self.conn.commit()

        self.cur.execute(f'SELECT COUNT(*) AS n FROM "{self.table}"')
        self.assertEqual(self.cur.fetchone()["n"], 4)

    def test_wildcard_literal_percent_and_underscore(self):
        for row in (
            {"id": 7, "first_name": "Promo", "last_name": "50% off", "age": 0, "status": "active"},
            {"id": 8, "first_name": "Other", "last_name": "500 off", "age": 0, "status": "active"},
            {"id": 9, "first_name": "Under", "last_name": "a_b", "age": 0, "status": "active"},
            {"id": 10, "first_name": "Wild", "last_name": "axb", "age": 0, "status": "active"},
        ):
            query, values = self._compile({
                "action": "insert",
                "source": self.table,
                "values": row,
            })
            self.cur.execute(query, values)
        self.conn.commit()

        payload = {
            "action": "select",
            "source": self.table,
            "columns": ["last_name"],
            "filters": [{"field": "last_name", "operator": "icontains", "value": "50%"}],
        }
        query, values = self._compile(payload)
        self.assertIn("ilike %s escape '\\'", query)
        self.assertEqual(values, ['%50\\%%'])
        self.assertNotIn("'%'", query)
        self.cur.execute(query, values)
        rows = self.cur.fetchall()
        self.assertEqual([r["last_name"] for r in rows], ["50% off"])

        rows = self._run({
            "action": "select",
            "source": self.table,
            "columns": ["last_name"],
            "filters": [{"field": "last_name", "operator": "icontains", "value": "a_b"}],
        })
        self.assertEqual([r["last_name"] for r in rows], ["a_b"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
