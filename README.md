# filtersql

[![PyPI version](https://img.shields.io/pypi/v/filtersql)](https://pypi.org/project/filtersql/)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
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
with any Python DB driver (psycopg2, sqlite3, asyncpg, etc.).

Designed for three use cases:

- **DataTables** server-side backends
- **Cursor-based pagination** (Access-style, no OFFSET)
- **Deterministic LLM pipelines** - the LLM generates JSON, filtersql compiles it to safe SQL

Supports PostgreSQL, SQLite, MySQL, DuckDB and Oracle.

## Features

- **Python-native & Lightweight** - No ORM required. Works seamlessly with your favorite Python database driver
- **Secure by default** - Fully parameterized queries, protected against SQL injection
- **Multi-database support** - PostgreSQL, SQLite, MySQL, DuckDB and Oracle
- **Lightweight** - No ORM required. Works with any database driver (psycopg2, sqlite3, mysql-connector, cx_Oracle, etc.)
- **Language-agnostic** - Clean JSON protocol, perfect for REST APIs and frontend applications
- **High-performance pagination** - Keyset (cursor-based) pagination, avoiding slow `OFFSET` queries
- **AI/LLM friendly** - Designed for structured output from large language models

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
  "dbms":   "SQLite",
  "filters": [
    {
      "field": "name",
      "operator": "icontains",
      "value": "john"
    }
  ]
}
```

to SQL:

```SQL
select
  *
from
  "users"
where
  ("name" like '%' || ? || '%' escape '\')
```

with values:

```JSON
["john"]
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
    dbms='SQLite',
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
#   ("first_name" like '%' || ? || '%' escape '\' and "last_name" like '%' || ? || '%' escape '\')
# order by
#   "first_name" asc
# limit 0, 10

print(values)
# ['John', 'Smith']
```

---

## Filters

### Filter format

Every filter is a dict with three keys:

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

### OR groups

Wrap filters in a dict with key `'or'`:

```python
filters = [
    {'field': 'status', 'operator': '=', 'value': 'active'},
    {'or': [
        {'field': 'first_name', 'operator': 'icontains', 'value': 'john'},
        {'field': 'last_name',  'operator': 'icontains', 'value': 'john'},
    ]},
]
# → "status" = ? AND ("first_name" like '%'||?||'%' escape '\' OR "last_name" like '%'||?||'%' escape '\')
```

### Nesting

OR groups can contain AND groups and vice versa:

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

### scope

`scope` is a dict of fixed `field: value` pairs applied as `=` filters to every operation on the Datasource - select, where, update, delete, and insert.

```python
ds = filtersql.Datasource(
    source      = 'documents',
    dbms        = 'Pg',
    placeholder = '%s',
    scope       = {'tenant_id': 42},
)

# scope is always added
query, values = ds.select(columns=columns, filters=user_filters)
# → ... WHERE "tenant_id" = %s AND ...

query, values = ds.delete(id={'id': 99})
# → ... WHERE "id" = %s AND "tenant_id" = %s

query, values = ds.insert(values={'title': 'New doc'})
# → INSERT INTO "documents" ("title", "tenant_id") VALUES (%s, %s)
```

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
never pass untrusted input as field when set, and remember to set `allow_raw_filelds=True`
on the corresponding Datasource:

```python
ds = filtersql.Datasource(source='users', dbms='Pg', allow_raw_fields=True)

columns = [
    {'field': 'COUNT(*) as total', 'raw': True},
    {'field': 'MAX(age) as max_age', 'raw': True},
]
```

Note: `raw=True` bypasses quoting/escaping entirely — never pass untrusted input as field when set.
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
    dbms='Pg'
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
    dbms='Pg'
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

# insert with returning (PostgreSQL only)
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

---

## where() - just the WHERE clause

When you want to inject filters into your own handwritten query:

```python
ds = filtersql.Datasource(source='documents', dbms='Pg', placeholder='%s')

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

## Group By and Having

`filtersql` now supports `GROUP BY` and `HAVING` for aggregations and analytics.

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

---

## filtersql() - convenience function

Builds any query from a single payload dict. Useful for REST APIs and AI-generated actions:

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
    dbms        = 'Pg',
    placeholder = '%s',
)
```

Supported actions: `select`, `insert`, `update`, `delete`.

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
#   ("first_name" ilike chr(37) || 'John' || chr(37) escape '\')
```

> Disabled by default — set FILTERSQL_DEBUG=1 in your environment to enable, since this should never run in production

---

## Wildcard Escape in Pattern Matching

Operators like `contains`, `icontains`, `starts_with`, etc. use `like` (or, for
SQLite's case-sensitive variants, `glob`) patterns.

`filtersql` automatically escapes the wildcard characters that matter for
whichever mechanism is in play - `%` and `_` for `like`/`ilike`, or `*`, `?`
and `[` for SQLite's `glob` - so searching for `"100%"` finds the literal
string `"100%"`, not `"100"` followed by anything.

The escape is applied transparently. This only affects operators that use patterns (`contains`, `starts_with`, etc.). Other operators (`=`, `>`, `in`, etc.) are unchanged.

---

## AI / LLM pipelines

LLMs should never generate SQL directly. They should generate structured intent. `filtersql` validates that intent and compiles it into parameterized SQL.
The values are always parameterized - no SQL injection risk even if the model produces unexpected output.

```
user question → LLM → JSON → filtersql → parameterized SQL
```

```python
# DANGEROUS!
# the naive approach everyone starts with
query = f"SELECT * FROM users WHERE {llm_output}"  # SQL injection waiting to happen

# with filtersql
payload = json.loads(llm_response)
query, values = filtersql(payload, dbms='Pg', placeholder='%s')
cursor.execute(query, values)  # always parameterized, always safe
```

The simplest version without Pydantic:

> Note: the schema below restricts `value` to a plain string, so it only
> works with scalar operators (`=`, `icontains`, etc.). Operators that need
> a list (`in`, `between`) require widening `value`'s schema type accordingly.

```python
import json
from google import genai
from filtersql import filtersql

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "source": {"type": "STRING", "enum": ["users", "contracts"]},
        "filters": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "field":    {"type": "STRING"},
                    "operator": {"type": "STRING", "enum": ["=", "!=", ">", ">=", "<", "<=", "icontains", "in"]},
                    "value":    {"type": "STRING"}
                },
                "required": ["field", "operator", "value"]
            }
        }
    },
    "required": ["source", "filters"]
}

response = client.models.generate_content(
    model='gemini-flash',
    contents=user_question,
    config=genai.types.GenerateContentConfig(
        system_instruction="Convert user questions into SQL filter payloads.",
        response_mime_type="application/json",
        response_schema=SCHEMA,
        temperature=0.0,
    )
)

payload = json.loads(response.text)
query, values = filtersql(payload, action='select', dbms='SQLite', placeholder='?')
```

With Pydantic for stricter validation:

```python
from pydantic import BaseModel, Field
from typing import List, Literal

class SQLFilter(BaseModel):
    field: str
    operator: Literal[
        '=', '!=', '>', '>=', '<', '<=', 
        'contains', 'not_contains', 'icontains', 'not_icontains',
        'starts_with', 'not_starts_with', 'istarts_with', 'not_istarts_with',
        'ends_with', 'not_ends_with', 'iends_with', 'not_iends_with',
        'between', 'in', 'notin', 'regexp', 'iregexp', 'not_regexp', 'not_iregexp',
        'null', 'notnull', 'fts', 'fts_query', 'reverse_in'
    ]
    value: str

class QuerySchema(BaseModel):
    semantic_query: str
    sql_filters: List[SQLFilter]

parsed = QuerySchema.model_validate_json(response.text)
filters = [f.model_dump() for f in parsed.sql_filters]

ds = filtersql.Datasource(source='documents', dbms='Pg', placeholder='%s')
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

Without the cast, `'9' > '10'` as text gives wrong results for numeric ranges.

---

## Cursor-based pagination

Navigates large tables without OFFSET - no performance degradation.

```python
ds = filtersql.Datasource(
    source = 'documents',
    dbms   = 'Pg',
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
query, values = ds.select(
    columns   = columns,
    cursor    = {'first_name': last_first, 'last_name': last_last},
    direction = 'next',
)
```

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
| `null` / `notnull` | NULL checks - no value needed |
| `in` / `notin` | List membership |
| `reverse_in` | Value in a set of columns - `? IN (col1, col2)` |
| `regexp` / `not_regexp` | Case-sensitive regular expression / exclusion |
| `iregexp` / `not_iregexp`| Case-insensitive regexp / exclusion |
| `fts` | Full-text search on indexed column (Pg, MySQL) |
| `fts_query` | Full-text search on text column (Pg only) |

---

## Supported databases

| DBMS | `dbms` value | Default placeholder |
|---|---|---|
| PostgreSQL | `'Pg'` | `%s` |
| SQLite | `'SQLite'` | `?` |
| DuckDB | `'DuckDB'` | `?` |
| MySQL | `'mysql'` | `%s` |
| Oracle | `'Oracle'` | `?` |

Override with any placeholder your driver expects:

```python
ds = filtersql.Datasource(..., placeholder='%s')
ds = filtersql.Datasource(..., placeholder=':val')
```

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
