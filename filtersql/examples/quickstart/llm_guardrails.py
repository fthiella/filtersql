"""
Let a model describe a query without letting it write SQL.

No API key, no server: the model is a stub that returns what a real one
might, including the answers you do not want. Run it with:

    pip install filtersql
    python llm_guardrails.py
"""
import json
import sqlite3

import filtersql

# -- a tiny database: two tenants, one secret column -------------------------
db = sqlite3.connect(":memory:")
db.execute("create table users (id integer primary key, first_name text,"
           " status text, password_hash text, tenant_id integer)")
db.executemany("insert into users values (?, ?, ?, ?, ?)", [
    (1, "Ada",   "active",   "x1", 42),
    (2, "Alan",  "inactive", "x2", 42),
    (3, "Grace", "active",   "x3", 42),
    (4, "Linus", "active",   "x4", 7),   # another tenant
])

# -- the model: replace this with a real call --------------------------------
ANSWERS = {
    "active users":          {"action": "select", "source": "users",
                              "columns": ["id", "first_name"],
                              "filters": [{"field": "status", "operator": "=", "value": "active"}]},
    "everyone's passwords":  {"action": "select", "source": "users",
                              "columns": ["first_name", "password_hash"]},
    "users of tenant 7":     {"action": "select", "source": "users",
                              "columns": ["first_name"],
                              "filters": [{"field": "tenant_id", "operator": "=", "value": 7}]},
    "drop the inactive ones": {"action": "delete", "source": "users",
                               "id": {"status": "inactive"}},
}

# -- your policy: the model cannot change any of this ------------------------
POLICY = dict(
    dbms="sqlite",
    allowed_sources={"users"},
    allowed_columns={"id", "first_name", "status"},   # no password_hash
    scope={"tenant_id": 42},                          # always ANDed
)


def ask(question):
    payload = ANSWERS[question]                       # json.loads(llm_response)
    print(f"\n> {question}")
    if payload.get("action") != "select":             # read-only tool: your rule
        print("  refused: this tool only reads")
        return
    try:
        query, values = filtersql.filtersql(payload, **POLICY)
    except filtersql.ValidationError as e:
        print(f"  refused: {e}")
        return
    print("  " + " ".join(query.split()), values)
    print("  ->", db.execute(query, values).fetchall())


for q in ANSWERS:
    ask(q)
