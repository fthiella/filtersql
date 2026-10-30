# -*- coding: utf-8 -*-
"""
filtersql + LangChain agent
===========================

The model never writes SQL. It calls a tool with *filters*, filtersql
compiles them into parameterized SQL, and a server-side policy rejects
whatever it should not see. The rejection goes back to the model as text,
so it can say "I can't do that" or try again with a different request.

What differs from the Gemini example: there the script makes one call and
stops at the first error. Here the model drives a loop (call tool, read the
result, answer) and sees the policy's error messages.

Setup
-----
    pip install "filtersql>=1.3.1" langchain langchain-google-genai

Any provider works: install its `langchain-<provider>` package and set
LANGCHAIN_MODEL to "<provider>:<model name>". This is not MODEL: the
Gemini example uses that name for a bare model id. Examples:

    LANGCHAIN_MODEL=google_genai:gemini-3.1-flash-lite   (needs GEMINI_API_KEY)
    LANGCHAIN_MODEL=anthropic:<model name>               (needs ANTHROPIC_API_KEY)
    LANGCHAIN_MODEL=openai:<model name>                  (needs OPENAI_API_KEY)

Run
---
    python langchain_agent.py

The demo database is built in memory, so there is nothing else to set up.
"""
import os
import sqlite3
from typing import Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from pydantic import BaseModel, Field

import filtersql

load_dotenv()

# ============================================================================
# DEMO DATABASE
# ============================================================================
# Two tenants, one secret column. In production this is your real database,
# opened with a read-only role.

TENANT_ID = 42


def build_demo_db() -> sqlite3.Connection:
    # check_same_thread=False: LangChain may run a tool on a worker thread.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(
        """
        create table users (
            id integer primary key, tenant_id integer,
            first_name text, last_name text, email text,
            age integer, status text, role text, password_hash text
        )
        """
    )
    conn.executemany(
        "insert into users values (?,?,?,?,?,?,?,?,?)",
        [
            (1, 42, "Ada",   "Lovelace", "ada@example.com",   36, "active",   "admin", "f38df63ba44dabaf"),
            (2, 42, "Alan",  "Turing",   "alan@example.com",  41, "active",   "user",  "h2"),
            (3, 42, "Grace", "Hopper",   "grace@example.com", 52, "inactive", "user",  "h3"),
            (4, 42, "Linus", "Torvalds", "linus@example.com", 55, "active",   "admin", "h4"),
            (5, 99, "Eve",   "Other",    "eve@other.com",     29, "active",   "user",  "h5"),
        ],
    )
    conn.commit()
    conn.execute("pragma query_only = on")  # the agent can read, never write
    return conn


conn = build_demo_db()


# ============================================================================
# SERVER-SIDE POLICY
# ============================================================================
# Set once at startup. The model cannot change any of it.
#
#   allowed_columns  what a client may name. `password_hash` and `tenant_id`
#                    exist in the table but are not listed.
#   scope            the tenant boundary, added with AND outside the model's
#                    filters, so no `or` / `not` can remove it.

ALLOWED_COLUMNS = ["id", "first_name", "last_name", "email", "age", "status", "role"]
MAX_ROWS = 20

ds = filtersql.Datasource(
    source="users",
    dbms="sqlite",
    allowed_sources={"users"},
    allowed_columns=set(ALLOWED_COLUMNS),
    scope={"tenant_id": TENANT_ID},
)


# ============================================================================
# THE TOOL
# ============================================================================
# The arguments are the model's whole vocabulary: filters, nothing else. It
# cannot pick the table, the action, or raw SQL. Numbers go in as strings
# ("50"); SQLite compares them numerically against an integer column.

class Filter(BaseModel):
    field: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "icontains"]
    value: str


@tool
def search_users(
    columns: list[str] = Field(
        default_factory=lambda: ["id", "first_name", "last_name", "email", "age", "status", "role"],
        description="Columns to return.",
    ),
    filters: list[Filter] = Field(default_factory=list),
    exclude: list[Filter] = Field(
        default_factory=list,
        description="Conditions to negate: rows matching ALL of them are left out.",
    ),
) -> list:
    """Search the users table. Conditions in `filters` are combined with AND.

    Table schema: id, tenant_id, first_name, last_name, email, age, status, role, password_hash.
    Operators: =, !=, >, >=, <, <=, and icontains (case-insensitive substring).
    Put conditions to negate in `exclude`. For "users who are not admins":
    filters=[], exclude=[{"field": "role", "operator": "=", "value": "admin"}].
    """
    payload = [f.model_dump() for f in filters]
    if exclude:
        payload.append({"not": [f.model_dump() for f in exclude]})

    try:
        query, params = ds.select(
            columns=columns,
            filters=payload,
            limit={"length": MAX_ROWS},
        )
    except (filtersql.ValidationError, filtersql.InvalidIdentifierError) as e:
        return [f"Rejected by policy: {e}"]

    rows = conn.execute(query, params).fetchall()
    return [dict(zip(columns, row)) for row in rows]


# ============================================================================
# THE AGENT
# ============================================================================

SYSTEM_PROMPT = (
    "You answer questions about users by calling `search_users`. "
    "You never write SQL. If the tool rejects a request, tell the user "
    "plainly that it is not allowed; do not try to work around it."
)


def build_agent(model):
    """`model` is a "<provider>:<name>" string or a LangChain chat model."""
    return create_agent(model, tools=[search_users], system_prompt=SYSTEM_PROMPT)


def ask(agent, question: str) -> str:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        # Each tool round-trip is a model call: bound the loop.
        config={"recursion_limit": 8},
    )

    for message in result["messages"]:
        if message.type == "ai" and message.tool_calls:
            for call in message.tool_calls:
                print(f"  tool call : {call['args']}")
        elif message.type == "tool":
            print(f"  tool reply: {str(message.content)[:200]}")

    return str(result["messages"][-1].text)


# ============================================================================
# ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    model = os.environ.get("LANGCHAIN_MODEL")
    if not model:
        raise SystemExit(
            "Set LANGCHAIN_MODEL, e.g. LANGCHAIN_MODEL=google_genai:gemini-3.1-flash-lite "
            "(not MODEL: that one is the bare id used by gemini_integration.py)."
        )

    agent = build_agent(model)

    questions = [
        # Expected to work
        "Which active users are older than 40?",
        "Show me the users who are not admins.",
        # Expected to be rejected by the policy, not by the model's good manners
        "Which user has password_hash equal to 'f38df63ba44dabaf'?",
        "List the users of tenant 99.",
    ]

    for q in questions:
        print("\n" + "-" * 70)
        print(f"Q: {q}")
        print(f"A: {ask(agent, q)}")
