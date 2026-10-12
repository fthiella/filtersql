# -*- coding: utf-8 -*-
"""
Live tests against a real MySQL or MariaDB.

The default ``%s`` placeholder is intentional. pymysql and mysqlclient
interpolate with ``query % params``; a literal ``'%'`` in the SQL text
raises ``ValueError: unsupported format character`` before the server
ever sees the query. Do not pass ``placeholder='?'``.

Connection, first match wins. A real environment variable beats ``.env``.

    MYSQL_URL=mysql://user:pass@127.0.0.1:3306/filtersql_test

or:

    MYSQL_HOST=127.0.0.1
    MYSQL_PORT=3306
    MYSQL_USER=root
    MYSQL_PASSWORD=
    MYSQL_DATABASE=filtersql_test

Skipped when neither form is set.
"""

import os
import unittest
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse
import pytest

pymysql = pytest.importorskip("pymysql")
pymysql.cursors

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


def mysql_kwargs():
    _load_dotenv()
    url = os.environ.get("MYSQL_URL") or os.environ.get("MYSQL_DSN")
    if url:
        parsed = urlparse(url)
        database = (parsed.path or "").lstrip("/") or None
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": database,
            "charset": "utf8mb4",
        }
    host = os.environ.get("MYSQL_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQL_DB"),
        "charset": "utf8mb4",
    }


class TestLiveMySQL(unittest.TestCase):

    def setUp(self):
        kwargs = mysql_kwargs()
        if kwargs is None:
            self.skipTest("Set MYSQL_URL or MYSQL_HOST to run live MySQL tests.")
        if not kwargs.get("database"):
            self.fail("MYSQL_URL / MYSQL_DATABASE must name a database.")

        self.conn = pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor,
            **kwargs,
        )
        self.cur = self.conn.cursor()
        self.table = "filtersql_live_" + uuid.uuid4().hex[:12]
        self.cur.execute(
            f"""
            CREATE TABLE `{self.table}` (
                id INT PRIMARY KEY,
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                age INT,
                status VARCHAR(32)
            ) CHARACTER SET utf8mb4
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
            self.cur.execute(f"DROP TABLE IF EXISTS `{self.table}`")
            self.conn.commit()
        finally:
            self.conn.close()

    def _compile(self, payload):
        # No placeholder override: pymysql must see %s.
        return filtersql(payload, dbms="mysql")

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
            f"SELECT COUNT(*) AS n FROM `{self.table}` WHERE first_name = %s",
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
            f"SELECT status, age FROM `{self.table}` WHERE id = 1"
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

        self.cur.execute(f"SELECT COUNT(*) AS n FROM `{self.table}`")
        self.assertEqual(self.cur.fetchone()["n"], 4)

    def test_wildcard_literal_percent_and_underscore(self):
        """'%' and '_' in the value must stay literal, and pymysql must not choke."""
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
        self.assertIn("like %s escape '\\\\'", query)
        self.assertEqual(values, ['%50\\%%'])
        self.assertNotIn("'%'", query)
        self.assertIn("%s", query)
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
