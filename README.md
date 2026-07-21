# filtersql

A Python library that compiles structured JSON into safe, parameterized SQL.

```
JSON payload (or Python dicts) → filtersql → SQL string + values list
```

It's not an ORM or a connection manager. It builds the query and returns it.
Execution is always the caller's responsibility, this makes it work with any
DB driver (psycopg2, sqlite3, cx_Oracle, mysql-connector) without any adapter code.

Designed for three use cases:

- **DataTables** server-side backends
- **Cursor-based pagination** (Access-style, no OFFSET)
- **AI/LLM filter pipelines** - the most interesting one

Supports PostgreSQL, SQLite, MySQL, and Oracle.

## Features

- **Secure by default** - Fully parameterized queries, protected against SQL injection
- **Multi-database support** - PostgreSQL, SQLite, MySQL, and Oracle
- **Lightweight** - No ORM required. Works with any database driver (psycopg2, sqlite3, mysql-connector, cx_Oracle, etc.)
- **Language-agnostic** - Clean JSON protocol, perfect for REST APIs and frontend applications
- **High-performance pagination** - Keyset (cursor-based) pagination, avoiding slow `OFFSET` queries
- **AI/LLM friendly** - Designed for structured output from large language models

## Comparison

| Tool                  | Query Builder | Multi-DB | JSON Payload | Keyset Pagination | AI/LLM Ready |
|-----------------------|---------------|----------|--------------|-------------------|--------------|
| **filtersql**         | Yes           | Yes      | Yes          | Yes               | Yes          |
| SQLAlchemy            | Yes           | Yes      | No           | Partial           | No           |
| PyPika                | Yes           | Yes      | No           | No                | No           |
| Django ORM            | Yes           | Yes      | No           | No                | No           |
| sqlalchemy-filterset  | Yes           | Yes      | Partial      | No                | No           |

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
    source      = 'users',
    dbms        = 'Pg',
    placeholder = '%s',
)

query, values = ds.select(
    columns = [
        {'field': 'id'},
        {'field': 'first_name'},
        {'field': 'last_name'},
    ],
    filters = [
        {'field': 'first_name', 'operator': 'icontains', 'value': 'John'},
        {'field': 'last_name',  'operator': 'icontains', 'value': 'Smith'},
    ],
    order = [{'field': 'first_name', 'order': 'asc'}],
    limit = {'start': 0, 'length': 10},
)

print(query)
# select
#   "id",
#   "first_name",
#   "last_name"
# from
#   "users"
# where
#   ("first_name" ilike '%' || %s || '%' and "last_name" ilike '%' || %s || '%')
# order by
#   "first_name" asc
# limit 10 offset 0

print(values)
# ['John', 'Smith']

cursor.execute(query, values)
rows = cursor.fetchall()
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
# → "status" = ? AND ("first_name" like '%'||?||'%' OR "last_name" like '%'||?||'%')
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

Raw expressions with `raw=True`:

```python
columns = [
    {'field': 'COUNT(*) as total', 'raw': True},
    {'field': 'MAX(age) as max_age', 'raw': True},
]
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

Replaces placeholders with actual values for logging. Never use the output as real SQL.

```python
query, values = ds.select(columns=columns, filters=filters)
print(ds.debug(query, values))
# select
#   "id",
#   "first_name"
# from
#   "users"
# where
#   ("first_name" ilike '%' || 'John' || '%')
```

---

## AI / LLM pipelines

The LLM generates a JSON payload. filtersql compiles it to SQL. The values are always parameterized - no SQL injection risk even if the model produces unexpected output.

```
user question → LLM → JSON → filtersql → parameterized SQL
```

The simplest version without Pydantic:

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
    field: Literal['doc_type', 'doc_date', 'author', 'title']
    operator: Literal['=', '!=', '>', '>=', '<', '<=', 'icontains', 'between', 'in', 'notin']
    value: str

class QuerySchema(BaseModel):
    semantic_query: str
    sql_filters: List[SQLFilter]

parsed = QuerySchema.model_validate_json(response.text)
filters = [f.model_dump() for f in parsed.sql_filters]

ds = filtersql.Datasource(source='documents', dbms='Pg', placeholder='%s')
where_clause, values = ds.where(filters=filters)
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
| `=` `!=` `>` `>=` `<` `<=` | Comparison |
| `between` | Range - value must be `[low, high]` |
| `contains` | Case-sensitive substring |
| `starts_with` | Case-sensitive prefix |
| `ends_with` | Case-sensitive suffix |
| `not_contains` | Case-sensitive substring exclusion |
| `not_starts_with` | Case-sensitive prefix exclusion |
| `icontains` | Case-insensitive substring |
| `istarts_with` | Case-insensitive prefix |
| `iends_with` | Case-insensitive suffix |
| `not_icontains` | Case-insensitive substring exclusion |
| `null` / `notnull` | NULL checks - no value needed |
| `in` / `notin` | List membership |
| `reverse_in` | Value in a set of columns - `? IN (col1, col2)` |
| `regexp` | Case-sensitive regular expression |
| `iregexp` | Case-insensitive regexp (Pg: `~*`, Oracle: `regexp_like` with `i`) |
| `fts` | Full-text search on indexed column (Pg, MySQL) |
| `fts_query` | Full-text search on text column (Pg only) |

---

## Supported databases

| DBMS | `dbms` value | Default placeholder |
|---|---|---|
| PostgreSQL | `'Pg'` | `?` |
| SQLite | `'SQLite'` | `?` |
| MySQL | `'mysql'` | `?` |
| Oracle | `'Oracle'` | `?` |

Override with any placeholder your driver expects:

```python
ds = filtersql.Datasource(..., placeholder='%s')   # psycopg2
ds = filtersql.Datasource(..., placeholder=':val')  # cx_Oracle named
```

---

## Examples

Working examples are in the `/examples` folder:

- `examples/datatables/` - Flask + DataTables server-side with column filters and global search
- `examples/pagination/` - REST API gateway with security whitelist for insert/update/delete
- `examples/ai/` - Gemini structured output → filtersql → SQLite

---

## License

MIT