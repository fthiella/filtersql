# filtersql

[![PyPI version](https://img.shields.io/pypi/v/filtersql)](https://pypi.org/project/filtersql/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A lightweight Python library that translates structured JSON into safe, parameterized SQL.**

Frontends, REST APIs and LLMs naturally produce structured JSON - not SQL.
`filtersql` is a Python package that defines a declarative JSON query language and compiles it
into safe, parameterized SQL.

```
JSON payload (or Python dicts) → filtersql → SQL string + values list
```

It is intentionally not an ORM or a connection manager. It builds the query and returns it.
Query execution remains the responsibility of the caller, making filtersql compatible
with any Python DB driver (psycopg2, sqlite3, asyncpg, oracledb, etc.).

Designed for three use cases:

- **DataTables** server-side backends
- **Cursor-based pagination** (Access-style, no OFFSET)
- **Deterministic LLM pipelines** - the LLM generates JSON, filtersql compiles it to safe SQL

Supports PostgreSQL, SQLite, MySQL, DuckDB and Oracle.

## What's new in 1.3.1

- **NOT groups.** `{"not": <filter or list>}` is now a first-class group key alongside `or` / `and`, in both `filters` and `having`. A single dict is negated directly; a list is joined with `AND` and negated as a whole. See [NOT groups](#not-groups).
- **Oracle numbered binds (`:{n}`).** The default Oracle placeholder is now `:1`, `:2`, … instead of `?`. Numbering is continuous across compound statements (`update()` numbers SET before WHERE; `select()` numbers WHERE before HAVING).
- **`returning` on SQLite and DuckDB.** `insert(returning=...)` now works on `sqlite` and `duckdb` in addition to `pg`.
- **`debug()` respects string literals.** Placeholder substitution skips text inside `'…'`, `"…"` and `` `…` ``, so a value that contains the placeholder character or a marker like `:1` does not confuse it.
- **Stricter validation** (payloads that used to be silently misread now raise `ValidationError` / `InvalidIdentifierError`):
  - group dicts mixing keys (`{"or": [...], "field": "x"}`);
  - `in` / `notin` / `between` with nested lists, dicts or sets as elements;
  - `cursor` values that are `None`, lists, dicts or sets;
  - duplicate fields in `order`;
  - an invalid `direction`, even when no `cursor` is given;
  - `limit.start` / `limit.length` that are `bool` or non-integral numbers (`2.9`); `limit={}` now applies the defaults instead of disabling the limit;
  - malformed dotted identifiers (`users..name`, `.users`, `users.`) and column aliases containing dots or JSONB operators;
  - `columns=0` / `False` / `""`;
  - a `Datasource` without `source` raises `ConfigurationError` at the first query build.

**Upgrading from 1.3.0:** Oracle users will see `:1, :2, …` instead of `?` (same driver, same values). Well-formed payloads are otherwise unaffected. Upgrading from an older release? Read the 1.3.0 notes in [CHANGELOG.md](CHANGELOG.md) first: `reverse_in` was removed and `None` is no longer accepted as a filter value.

## Why filtersql?

`filtersql` is intentionally:

- stateless
- deterministic
- driver agnostic
- parameterized
- declarative
- portable
- JSON-first
- LLM friendly

Applications describe what they want. `filtersql` decides how to express it in SQL.

## Example

From JSON:

```JSON
{
  "action": "select",
  "source": "users",
  "filters": [
    {
      "field": "name",
      "operator": "icontains",
      "value": "john"
    }
  ]
}
```

to SQL (SQLite dialect, `?` placeholders):

```SQL
select
  *
from
  "users"
where
  ("name" like ? escape '\')
```

with values:

```JSON
["%john%"]
```

---

## Install

```bash
pip install filtersql
```

---

## Quick start

```python
import filtersql

ds = filtersql.Datasource(
    source='users',
    dbms='sqlite',
    placeholder='?',
)

query, values = ds.select(
    columns=['id', 'first_name', 'last_name'],
    filters=[
        {'field': 'first_name', 'operator': 'icontains', 'value': 'John'},
        {'field': 'last_name',  'operator': 'icontains', 'value': 'Smith'},
    ],
    order=[{'field': 'first_name', 'order': 'asc'}],
    limit={'start': 0, 'length': 10},
)

print(query)
# select
#   "id",
#   "first_name",
#   "last_name"
# from
#   "users"
# where
#   ("first_name" like ? escape '\' and "last_name" like ? escape '\')
# order by
#   "first_name" asc
# limit 0, 10

print(values)
# ['%John%', '%Smith%']
```

---

## Allowlists (`allowed_columns`, `allowed_sources`)

> New in 1.3. The strongest guardrail filtersql offers for multi-tenant or untrusted-input deployments.

`scope` protects *rows*; allowlists protect *what a client may name*. Both are set server-side when you build the `Datasource` and cannot be supplied via the payload:

```python
ds = filtersql.Datasource(
    source          = 'users',
    dbms            = 'pg',
    scope           = {'tenant_id': 42},
    allowed_columns = {'id', 'name', 'status', 'created_at'},
    allowed_sources = {'users', 'orders'},
)
```

With `allowed_columns` set, **every column a client can reference is checked against it**:
`columns`, `filters` and `having` (including nested `and` / `or` / `not` groups),
`order`, `group_by`, `cursor`, `returning`, and the keys of `values` and `id`.
A name that is not listed raises `ValidationError`.

Behavior details:

- **Exact match, nothing is normalized.** `Name`, `name `, `users.name` and a Unicode look-alike are all different strings, and none of them matches `name`. List a column exactly as the client will send it, including a JSONB path like `attributes->>amount`.
- **`SELECT *` is refused**: `columns` must be given explicitly.
- **`raw` columns and filters are refused**, even with `allow_raw_fields=True`: a raw string is SQL, not a column name, so it cannot be allowlisted.
- **`scope` columns do not have to be listed.** Scope is added by the server after the check, so a client that is not allowed to name `tenant_id` can neither filter on it nor set it.
- An `alias` is an output label, not a column reference, and is not checked.
- `None` (the default) keeps the old behaviour. An **empty** collection is not "no restriction": it allows nothing.

`allowed_sources` is checked the same way against `source` on every action, and applies to a raw source too (the whole string must be listed). Neither parameter can be supplied in the payload of `filtersql()`.

Use the allowlist as the primary control; identifier validation (no dots, quotes, JSONB paths in write keys) stays underneath it as a safety net for callers that forget to set one.

---

## Filters

### Filter format

Every filter is a dict with a `field`, an `operator` and (for most operators) a `value`:

```python
{'field': 'status', 'operator': '=', 'value': 'active'}
```

- `field` - column name, JSONB path (`attributes->>amount`), or schema-prefixed (`m.doc_type`)
- `operator` - the comparison operator (see table below)
- `value` - the value to compare against

A flat list of filters is joined with AND:

```python
filters = [
    {'field': 'status',   'operator': '=',         'value': 'active'},
    {'field': 'doc_date', 'operator': '>=',        'value': '2025-01-01'},
    {'field': 'title',    'operator': 'icontains', 'value': 'oxygen'},
]
```

Some operators don't need a value:

```python
{'field': 'deleted_at', 'operator': 'null'}
{'field': 'deleted_at', 'operator': 'notnull'}
```

Some operators take a list:

```python
{'field': 'status',   'operator': 'in',      'value': ['active', 'pending']}
{'field': 'doc_date', 'operator': 'between', 'value': ['2025-01-01', '2025-12-31']}
```

### OR / AND groups

Wrap filters in a dict with key `'or'` or `'and'`:

```python
filters = [
    {'field': 'status', 'operator': '=', 'value': 'active'},
    {'or': [
        {'field': 'first_name', 'operator': 'icontains', 'value': 'john'},
        {'field': 'last_name',  'operator': 'icontains', 'value': 'john'},
    ]},
]
# → "status" = ? AND ("first_name" like ? escape '\' OR "last_name" like ? escape '\')
```

### NOT groups

`not` takes a single filter dict, or a list of them (joined with `AND`, then negated as a whole):

```python
filters = [
    {'field': 'active', 'operator': '=', 'value': 1},
    {'not': {'field': 'role', 'operator': '=', 'value': 'banned'}},
]
# → ("active" = ? AND NOT ("role" = ?))

filters = [
    {'not': [
        {'field': 'role',   'operator': '=', 'value': 'guest'},
        {'field': 'locked', 'operator': '=', 'value': True},
    ]},
]
# → NOT ("role" = ? AND "locked" = ?)
```

A group dict must contain **exactly one** of `'or'`, `'and'`, `'not'`. Mixing keys — `{'or': [...], 'field': 'x'}` or `{'and': [...], 'or': [...]}` — raises `ValidationError`.

### Nesting

Groups can contain groups:

```python
filters = [
    {'or': [
        {'field': 'doc_type', 'operator': '=', 'value': 'CONTRACT'},
        {'and': [
            {'field': 'doc_type', 'operator': '=',  'value': 'ORDER'},
            {'field': 'amount',   'operator': '>=', 'value': '10000'},
        ]},
    ]},
]
# → ("doc_type" = ? OR ("doc_type" = ? AND "amount" >= ?))
```

Nesting depth is capped at 32.

### scope

`scope` is a dict of fixed `field: value` pairs applied as `=` filters to every operation on the Datasource - select, where, update, delete, and insert.

```python
ds = filtersql.Datasource(
    source      = 'documents',
    dbms        = 'pg',
    placeholder = '%s',
    scope       = {'tenant_id': 42},
)

query, values = ds.select(columns=columns, filters=user_filters)
# → ... WHERE "tenant_id" = %s AND ...

query, values = ds.delete(id={'id': 99})
# → ... WHERE "tenant_id" = %s AND "id" = %s

query, values = ds.insert(values={'title': 'New doc'})
# → INSERT INTO "documents" ("title", "tenant_id") VALUES (%s, %s)
```

**Note on column names**: the keys of `values` (in `insert` and `update`) and
of `id` (in `update` and `delete`) must be plain column names - no dots, no
JSONB paths, no quoting. This is what makes the `scope` collision check
reliable across dialects: a client can't reference a scoped column under a
different spelling (e.g. `users.tenant_id`, or `tenant_id` with trailing
whitespace) and slip past the check.

---

## Columns

Columns are passed per call to `select()`, not at construction time - they can be computed at runtime.

Each column is a dict with a `field` key. Any extra keys (`label`, `visible`, `editable` etc.) are ignored by filtersql and can be used by your frontend layer:

```python
columns = [
    {'field': 'id',         'label': 'ID',         'visible': True,  'editable': False},
    {'field': 'first_name', 'label': 'First Name', 'visible': True,  'editable': True},
    {'field': 'last_name',  'label': 'Last Name',  'visible': True,  'editable': True},
]
```

Plain strings also work:

```python
columns = ['id', 'first_name', 'last_name']
```

Raw expressions with `raw=True`, but since this bypasses quoting/escaping entirely
never pass untrusted input as `field` when set, and remember to set `allow_raw_fields=True`
on the corresponding Datasource:

```python
ds = filtersql.Datasource(source='users', dbms='pg', allow_raw_fields=True)

columns = [
    {'field': 'COUNT(*) as total', 'raw': True},
    {'field': 'MAX(age) as max_age', 'raw': True},
]
```

`raw=True` is refused when `allowed_columns` is set — a raw string is SQL, not a column name, and cannot be allowlisted.

---

## Raw source (`raw_source`)

By default, `source` is always treated as an identifier and quoted
accordingly. If you need to pass a subquery instead of a plain table name
(e.g. `"(SELECT * FROM users WHERE active = true) AS active_users"`), set
`raw_source=True` — this tells filtersql to use the `source` string
directly in the SQL, unquoted.

Because `raw_source=True` disables quoting entirely, it also requires an
explicit `allow_raw_source=True` on the `Datasource` — this two-flag
requirement exists specifically so this feature can't be turned on by
accident or by a value that came from user input.

```python
ds = filtersql.Datasource(
    source="(SELECT * FROM users WHERE active = true) AS active_users",
    raw_source=True,
    allow_raw_source=True,
    dbms='pg'
)
```

**Note:** `raw_source=True` bypasses quoting entirely — only use it with
trusted, hardcoded values. Never build `source` from user input:

```python
# UNSAFE — never do this
ds = filtersql.Datasource(
    source=request.GET.get('table'),
    raw_source=True,
    allow_raw_source=True,
    dbms='pg'
)
```

---

## Insert, update, delete

All three return `(query, values)` like `select()`.

```python
# insert
query, values = ds.insert(
    values = {'first_name': 'John', 'last_name': 'Smith'},
)

# insert with returning (PostgreSQL, SQLite, DuckDB)
query, values = ds.insert(
    values    = {'first_name': 'John'},
    returning = 'id',
)

# update - id can be single or composite key
query, values = ds.update(
    id     = {'id': 42},
    values = {'first_name': 'John', 'status': 'active'},
)
# values order: SET values first, then WHERE values
# → ['John', 'active', 42]

# delete
query, values = ds.delete(id={'id': 42})
```

Keys in `values` and `id` must be plain column names. Qualified names
(`users.id`) and JSONB paths (`data->>x`) are rejected — use `filters`
in `select()` for non-key filtering.

---

## where() - just the WHERE clause

When you want to inject filters into your own handwritten query:

```python
ds = filtersql.Datasource(source='documents', dbms='pg', placeholder='%s')

where_clause, values = ds.where(filters=[
    {'field': 'doc_type', 'operator': '=',  'value': 'CONTRACT'},
    {'field': 'doc_date', 'operator': '>=', 'value': '2025-01-01'},
])
# → '("doc_type" = %s and "doc_date" >= %s)'
# → ['CONTRACT', '2025-01-01']

query = f"""
    SELECT v.chunk, m.doc_type
    FROM file_vectors v
    JOIN file_metadata m ON v.sha256 = m.sha256
    WHERE v.model_name = %s
    AND {where_clause}
    ORDER BY v.embedding <=> %s
"""
```

> **Numbered placeholders (Oracle, or a custom `{n}` placeholder):** `where()` always numbers from `:1`. If your handwritten query already has its own binds, they will collide, so build the whole statement with `select()` instead, or use named binds in your own SQL.

---

## Group By and Having

`filtersql` supports `GROUP BY` and `HAVING` for aggregations and analytics.

```python
query, values = ds.select(
    columns=[
        {'field': 'status'},
        {'field': 'count(*)', 'raw': True, 'alias': 'total'}
    ],
    filters=[{'field': 'age', 'operator': '>=', 'value': 18}],
    group_by=['status'],
    having=[{'field': 'count(*)', 'raw': True, 'operator': '>', 'value': 5}],
    order=[{'field': 'total', 'order': 'desc'}]
)
```

Note: `having` needs `raw: True` on aggregate expressions like `count(*)` (same reason as columns). With `allowed_columns` set, `raw` is refused, so an allowlist is incompatible with aggregate HAVING — use a SQL view or a handwritten query instead.

---

## filtersql() - convenience function

Builds any query from a single payload dict. `dbms` is a **required** server-side parameter.

```python
from filtersql import filtersql

query, values = filtersql(
    payload = {
        'action':  'select',
        'source':  'users',
        'columns': [{'field': 'id'}, {'field': 'first_name'}],
        'filters': [{'field': 'status', 'operator': '=', 'value': 'active'}],
        'order':   [{'field': 'id', 'order': 'asc'}],
        'limit':   {'start': 0, 'length': 10},
    },
    dbms        = 'pg',
    placeholder = '%s',
)
```

Supported actions: `select`, `insert`, `update`, `delete`.

Server-side configuration parameters (`dbms`, `scope`, `placeholder`, `fts_language`, `allowed_columns`, `allowed_sources`, `allow_raw_fields`, `allow_raw_source`, `raw_source`) must be passed as **named arguments** to `filtersql()`. Passing any of them inside the payload or via `**kwargs` raises `ValidationError`.

---

## debug()

Replaces placeholders with actual values for logging. For security reasons, never use the output as real SQL.

```python
query, values = ds.select(columns=columns, filters=filters)
print(ds.debug(query, values))
# select
#   "id",
#   "first_name"
# from
#   "users"
# where
#   ("first_name" ilike '%John%' escape '\')
```

> Disabled by default — set `FILTERSQL_DEBUG=1` in your environment to enable, since this should never run in production.

Placeholder substitution ignores text inside string literals, so a value that happens to contain the placeholder character (e.g. `"what?"` with `placeholder='?'`) does not confuse the substitution.

---

## Wildcard Escape in Pattern Matching

`filtersql` automatically escapes the wildcard characters that matter for
whichever mechanism is in play - `%` and `_` for `like`/`ilike`, or `*`, `?`
and `[` for SQLite's `glob` - so searching for `"100%"` finds the literal
string `"100%"`, not `"100"` followed by anything.

The escaping is applied to the value before it is bound: the generated
SQL contains no wildcard markers, and the pattern itself (e.g.
`'%100\%%'`) is what the driver binds. This only affects operators that
use patterns (`contains`, `starts_with`, etc.). Other operators
(`=`, `>`, `in`, ...) are unchanged.

---

## Limits

`filtersql` enforces a small set of limits, all raising `ValidationError` when exceeded:

| Limit | Value |
|---|---|
| `limit.length` (per query) | 10 000 |
| Values per `in` / `notin` | 1 000 |
| Nesting depth of `or` / `and` / `not` | 32 |

`limit.start` must be `>= 0`; `limit.length` must be `>= 1`. Both must be integers (or strings / integral numbers that convert exactly, like `"10"` or `3.0`); `2.9`, `True` and `NaN` are rejected. `limit={}` applies the defaults (`start=0`, `length=100`); only `None` means "no limit".

---

## AI / LLM pipelines

LLMs should never generate SQL directly. They should generate structured intent. `filtersql` validates that intent and compiles it into parameterized SQL.

```
user question → LLM → JSON → filtersql → parameterized SQL
```

Values are always bound as parameters, so a model cannot inject SQL through a value. What a model *can* still do is name columns and tables you did not intend to expose. Close that with the server-side guardrails, which the payload cannot override:

- `allowed_columns` / `allowed_sources`: exact-match allowlists (see [Allowlists](#allowlists-allowed_columns-allowed_sources))
- `scope`: fixed row filters such as `tenant_id`
- `raw` columns/filters and `raw_source` stay off unless you enable them

```python
# DANGEROUS!
# the naive approach everyone starts with
query = f"SELECT * FROM users WHERE {llm_output}"  # SQL injection waiting to happen

# with filtersql
payload = json.loads(llm_response)
query, values = filtersql(
    payload,
    dbms            = 'pg',
    placeholder     = '%s',
    allowed_sources = {'users'},
    allowed_columns = {'id', 'first_name', 'last_name', 'status'},
    scope           = {'tenant_id': current_tenant},
)
cursor.execute(query, values)
```

The simplest version without Pydantic:

> Note: the schema below restricts `value` to a plain string, so it only
> works with scalar operators (`=`, `icontains`, etc.). Operators that need
> a list (`in`, `between`) require widening `value`'s schema type accordingly.
> `client` is a `genai.Client()` you create beforehand.

```python
import json
from google import genai
from filtersql import filtersql

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "action": {"type": "STRING", "enum": ["select"]},
        "source": {"type": "STRING", "enum": ["users", "contracts"]},
        "filters": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "field":    {"type": "STRING"},
                    "operator": {"type": "STRING", "enum": ["=", "!=", ">", ">=", "<", "<=", "icontains"]},
                    "value":    {"type": "STRING"}
                },
                "required": ["field", "operator", "value"]
            }
        }
    },
    "required": ["action", "source", "filters"]
}

response = client.models.generate_content(
    model='gemini-3.1-flash-lite',
    contents=user_question,
    config=genai.types.GenerateContentConfig(
        system_instruction="Convert user questions into SQL filter payloads.",
        response_mime_type="application/json",
        response_schema=SCHEMA,
        temperature=0.0,
    )
)

payload = json.loads(response.text)
query, values = filtersql(
    payload, dbms='sqlite', placeholder='?',
    allowed_sources = {'users', 'contracts'},
    allowed_columns = {'id', 'name', 'status', 'created_at'},
)
```

With Pydantic for stricter validation:

```python
from pydantic import BaseModel
from typing import List, Literal

class SQLFilter(BaseModel):
    field: str
    operator: Literal[
        '=', '!=', '>', '>=', '<', '<=',
        'contains', 'not_contains', 'icontains', 'not_icontains',
        'starts_with', 'not_starts_with', 'istarts_with', 'not_istarts_with',
        'ends_with', 'not_ends_with', 'iends_with', 'not_iends_with',
        'regexp', 'iregexp', 'not_regexp', 'not_iregexp',
        'null', 'notnull', 'fts', 'fts_query'
    ]
    value: str

class QuerySchema(BaseModel):
    semantic_query: str
    sql_filters: List[SQLFilter]

parsed = QuerySchema.model_validate_json(response.text)
filters = [f.model_dump() for f in parsed.sql_filters]

ds = filtersql.Datasource(
    source='documents', dbms='pg', placeholder='%s',
    allowed_columns={'title', 'doc_type', 'doc_date'},
)
where_clause, values = ds.where(filters=filters)
```

### Empty list handling (`in` / `notin`)

If a frontend or LLM passes an empty array as a filter value (e.g. unselected checkboxes), `filtersql` handles it gracefully without breaking SQL syntax:

```python
{'field': 'category_id', 'operator': 'in',    'value': []} # → 1 = 0
{'field': 'category_id', 'operator': 'notin', 'value': []} # → 1 = 1
```

### JSONB and value_type (PostgreSQL)

```python
{'field': 'attributes->>amount',  'operator': '>=', 'value': '10000',     'value_type': 'numeric'}
# → ("attributes"->>'amount')::numeric >= %s::numeric

{'field': 'attributes->>expiry',  'operator': '<=', 'value': '2025-12-31', 'value_type': 'date'}
# → ("attributes"->>'expiry')::date <= %s::date
```

Without the cast, `'9' > '10'` as text gives wrong results for numeric ranges. `value_type` is only honored on Pg JSONB paths; it is ignored on plain columns.

---

## Cursor-based pagination

Navigates large tables without OFFSET - no performance degradation.

```python
ds = filtersql.Datasource(
    source = 'documents',
    dbms   = 'pg',
    order  = [{'field': 'id', 'order': 'asc'}],
)

# forward
query, values = ds.select(
    columns   = columns,
    cursor    = {'id': last_seen_id},
    direction = 'next',
)

# backward
query, values = ds.select(
    columns   = columns,
    cursor    = {'id': last_seen_id},
    direction = 'prev',
)

# jump to specific record
query, values = ds.select(
    columns   = columns,
    cursor    = {'id': 42},
    direction = 'seek',
)
```

| `direction` | SQL | Use case |
|---|---|---|
| `'next'` | `field > last_value` | Forward navigation |
| `'prev'` | `field < last_value` | Backward navigation |
| `'seek'` | `field = value` | Jump to specific record |

Multi-column cursors work too:

```python
ds = filtersql.Datasource(
    source = 'documents',
    dbms   = 'pg',
    order  = [
        {'field': 'last_name',  'order': 'asc'},
        {'field': 'first_name', 'order': 'asc'},
    ],
)

query, values = ds.select(
    columns   = columns,
    cursor    = {'first_name': last_first, 'last_name': last_last},
    direction = 'next',
)
```

Every cursor key must appear in `order`, and every order field must appear in the cursor, for `next` / `prev`. Both violations raise `ValidationError`.

Cursor values must be scalars. `None`, lists, dicts and sets are rejected: `col > NULL` never matches, so a null cursor would silently return no rows. `order` may not list the same field twice, and `direction` must be one of `seek` / `next` / `prev` even when no `cursor` is given (`prev` alone just inverts the sort).

---

## Full-text search

### PostgreSQL

```python
# pre-built tsvector column
{'field': 'tsv_content', 'operator': 'fts', 'value': 'oxygen supply'}
# → "tsv_content" @@ websearch_to_tsquery('english', %s)

# on the fly from a text column
{'field': 'description', 'operator': 'fts_query', 'value': 'oxygen supply'}
# → to_tsvector('english', coalesce("description", '')) @@ websearch_to_tsquery('english', %s)

ds = filtersql.Datasource(..., fts_language='italian')
```

### MySQL

```python
{'field': 'content', 'operator': 'fts', 'value': 'oxygen supply'}
# → match("content") against(? in boolean mode)
```

On MySQL, `fts_query` is an alias of `fts` (both rely on `MATCH ... AGAINST`, which requires a `FULLTEXT` index). It does not vectorize on the fly like PostgreSQL's `fts_query`.

---

## Filter operators

| Operator | Description |
|---|---|
| `=`, `!=`, `>`, `>=`, `<`, `<=` | Comparison |
| `between` | Range - value must be `[low, high]` |
| `contains` / `not_contains` | Case-sensitive substring / exclusion |
| `starts_with` / `not_starts_with` | Case-sensitive prefix / exclusion |
| `ends_with` / `not_ends_with` | Case-sensitive suffix / exclusion |
| `icontains` / `not_icontains` | Case-insensitive substring / exclusion |
| `istarts_with` / `not_istarts_with` | Case-insensitive prefix / exclusion |
| `iends_with` / `not_iends_with` | Case-insensitive suffix / exclusion |
| `null` / `notnull` | NULL checks - no value needed. The only way to test for NULL: every other operator rejects a `None` value |
| `in` / `notin` | List membership |
| `regexp` / `not_regexp` | Case-sensitive regular expression / exclusion |
| `iregexp` / `not_iregexp`| Case-insensitive regexp / exclusion |
| `fts` | Full-text search on indexed column (Pg, MySQL) |
| `fts_query` | Full-text search on text column (Pg); alias of `fts` on MySQL |

---

## Supported databases

| DBMS | `dbms` value | Default placeholder |
|---|---|---|
| PostgreSQL | `'pg'` | `%s` |
| SQLite | `'sqlite'` | `?` |
| DuckDB | `'duckdb'` | `?` |
| MySQL | `'mysql'` | `%s` |
| Oracle | `'oracle'` | `:{n}` (numbered) |

`dbms` is case-insensitive - `'pg'`, `'PG'`, `'Pg'` are all equivalent. Unrecognized names (e.g. `'postgres'`) raise a `ConfigurationError` listing the valid names above.

`oracle` uses numbered binds (`:1`, `:2`, …) automatically. You do not need to set `placeholder` manually for Oracle.

Override with any placeholder your driver expects:

```python
ds = filtersql.Datasource(..., placeholder='%s')
ds = filtersql.Datasource(..., placeholder='${n}')  # numbered: $1, $2, …
```

A custom placeholder may contain `{n}` at most once. Without `{n}` the placeholder is used as-is for every value (`'$'` gives `$`, `$`, …, not `$1`, `$2`).

---

## Examples

Working examples are in the `/examples` folder:

- `examples/datatables/` - Flask + DataTables server-side with column filters and global search
- `examples/pagination/` - REST API gateway with security whitelist for insert/update/delete
- `examples/ai/` - Gemini structured output → filtersql → SQLite
- `examples/pandas_duckdb/` - Query Pandas DataFrames using DuckDB + filtersql

---

## License

MIT