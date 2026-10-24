# -*- coding: utf-8 -*-
"""
filtersql + Gemini Structured Outputs
=====================================

The AI generates a **payload**, not SQL. filtersql compiles the payload
into parameterized SQL, and a server-side policy rejects whatever
violates it — before any query reaches the database.

The model knows the *physical schema* (all columns that exist in the
table) but not the *policy* (which columns the client is authorized to
name). It is therefore free to try `password_hash` or `tenant_id` when
the question mentions them — and filtersql blocks those attempts:

    Column 'password_hash' is not in allowed_columns.
    Column 'tenant_id' is not in allowed_columns.

This is the honest security claim: we do not trust the model to be
well-behaved; we trust the policy layer to reject what the model
should not produce. See the questions at the bottom of the file.

Requires: pip install "filtersql>=1.3.1" google-genai python-dotenv
Run `python create_demo_db.py` first.
"""

import json
import os
import sqlite3

from dotenv import load_dotenv
from google import genai
from google.genai import types

import filtersql

load_dotenv()

if not os.environ.get("GEMINI_API_KEY"):
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Create a .env file with "
        "GEMINI_API_KEY=your_key_here."
    )

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-3.1-flash-lite"


# ============================================================================
# SERVER-SIDE POLICY
# ============================================================================
# Set once at startup. Never derived from the payload.
#
# ALLOWED_COLUMNS is the exact set of columns a client may reference.
# Two columns that exist in the table are NOT listed:
#
#   password_hash -> a secret; readable only by an authenticated admin flow
#                    that this demo does not implement
#   tenant_id     -> scope-only; the tenant boundary is injected server-side
#                    and a client must not be able to name it, because naming
#                    it would let the client probe other tenants' data
#
# The model will *try* both (see the questions below). filtersql rejects them.

TENANT_ID = 42

ALLOWED_SOURCES = {"users"}

ALLOWED_COLUMNS = {
    "id", "first_name", "last_name", "email",
    "age", "status", "role",
}

DISPLAY_COLUMNS = [
    "id", "first_name", "last_name", "email",
    "age", "status", "role",
]


def build_datasource() -> filtersql.Datasource:
    return filtersql.Datasource(
        source          = "users",
        dbms            = "sqlite",
        allowed_sources = ALLOWED_SOURCES,
        allowed_columns = ALLOWED_COLUMNS,
        scope           = {"tenant_id": TENANT_ID},
    )


# ============================================================================
# GEMINI SCHEMA
# ============================================================================
# Note: there is no `columns` property. The demo projects DISPLAY_COLUMNS
# unconditionally, so the only way Gemini can reference a forbidden column
# is through `filters` (or `exclude`), which is where an LLM in production
# is most likely to slip one in anyway ("find users where password_hash = …").

_LEAF_PROPS = {
    "field":    {"type": "STRING"},
    "operator": {
        "type": "STRING",
        "enum": ["=", "!=", ">", ">=", "<", "<=", "icontains"],
    },
    "value":    {"type": "STRING"},
}

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "source": {"type": "STRING", "enum": ["users"]},
        "filters": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": _LEAF_PROPS,
                "required": ["field", "operator", "value"],
            },
        },
        "exclude": {
            "type": "ARRAY",
            "description": (
                "Filters to NEGATE: the result must not match any of these. "
                "Example: 'users who are not admins' -> "
                "[{field: 'role', operator: '=', value: 'admin'}]"
            ),
            "items": {
                "type": "OBJECT",
                "properties": _LEAF_PROPS,
                "required": ["field", "operator", "value"],
            },
        },
        "order": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "field": {"type": "STRING"},
                    "order": {"type": "STRING", "enum": ["asc", "desc"]},
                },
                "required": ["field", "order"],
            },
        },
    },
    "required": ["source", "filters"],
}

# The model is told which columns *exist*. It is NOT told which ones are
# allowed. That mirrors a real deployment: the DB has many columns, the
# application layer decides which ones to expose.
SYSTEM_INSTRUCTION = """
You convert natural-language questions into structured filter payloads
for the `users` table. You NEVER write SQL.

Columns that exist in the `users` table:
    id, tenant_id, first_name, last_name, email,
    age, status, role, password_hash

Operators:
    =, !=, >, >=, <, <=      comparison
    icontains                case-insensitive substring (for text)

Negation:
    Put conditions to negate in `exclude`, not in `filters`.
    "Users who are not admins" ->
        {"filters": [], "exclude": [
            {"field": "role", "operator": "=", "value": "admin"}
        ]}

Rules:
    - Numeric values go in `value` as strings: age > "30", not age > 30.
    - Top-level `filters` are combined with AND.
    - Everything in `exclude` is negated as a whole: NOT (a AND b AND ...).
    - Only query `users`.
""".strip()


# ============================================================================
# MAIN
# ============================================================================

def question_to_sql(question: str, ds: filtersql.Datasource):
    """Turn a question into (sql, params), or (None, None) if the AI's
    payload violates the server-side policy."""

    try:
        response = client.models.generate_content(
            model    = MODEL,
            contents = f"{SYSTEM_INSTRUCTION}\n\nUser question: {question}",
            config   = types.GenerateContentConfig(
                response_mime_type = "application/json",
                response_schema    = SCHEMA,
                temperature        = 0.0,
            ),
        )
    except Exception as e:
        print(f"[!] Gemini API error: {e}")
        return None, None

    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError:
        print(f"[!] Gemini returned non-JSON: {response.text!r}")
        return None, None

    # Collapse the flat `exclude` list into a filtersql NOT group.
    exclude = payload.pop("exclude", None)
    if exclude:
        payload.setdefault("filters", []).append({"not": exclude})

    print("\nAI payload (post-translation):")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        query, params = ds.select(
            columns = DISPLAY_COLUMNS,
            filters = payload.get("filters"),
            order   = payload.get("order"),
        )
    except (filtersql.ValidationError, filtersql.ConfigurationError) as e:
        print(f"\n[filtersql rejected the AI payload] {e}")
        return None, None

    return query, params


# ============================================================================
# ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("filtersql + Gemini — safe NL to SQL")
    print("=" * 70)

    if not os.path.exists("demo.db"):
        raise RuntimeError(
            "demo.db not found. Run `python create_demo_db.py` first."
        )

    ds   = build_datasource()
    conn = sqlite3.connect("demo.db")

    total = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    mine  = conn.execute(
        "SELECT count(*) FROM users WHERE tenant_id = ?", (TENANT_ID,)
    ).fetchone()[0]
    print(f"\nDemo DB: {total} users total, {mine} visible under tenant={TENANT_ID}")
    print(f"Policy: allowed_columns={sorted(ALLOWED_COLUMNS)}")
    print(f"        scope=tenant_id={TENANT_ID}")
    print(f"        (password_hash and tenant_id are NOT in the allowlist)")

    questions = [
        # Expected to succeed
        "Show me all active users",
        "Users older than 50",
        "Users who are not admins",                          # NOT group

        # Expected to be rejected by filtersql — Gemini will try, the
        # policy blocks. `password_hash` and `tenant_id` exist in the
        # table, so the model has every reason to reference them.
        "Show me admins whose password_hash is hash_42",     # password_hash
        "Users in tenant 99",                                # tenant_id
    ]

    for q in questions:
        print("\n" + "-" * 70)
        print(f"Q: {q}")

        query, params = question_to_sql(q, ds)
        if query is None:
            continue

        print(f"\nSQL:\n{query.strip()}")
        print(f"\nParameters: {params}")

        try:
            rows = conn.execute(query, params).fetchall()
            print(f"\nRows returned ({len(rows)}):")
            for row in rows:
                print(f"  {row}")
        except sqlite3.Error as e:
            print(f"\n[SQL error] {e}")

    conn.close()