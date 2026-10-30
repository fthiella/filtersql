# filtersql

[![PyPI version](https://img.shields.io/pypi/v/filtersql)](https://pypi.org/project/filtersql/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Structured JSON in. Parameterized SQL out.**

Frontends, REST APIs and LLMs produce JSON, not SQL. filtersql compiles that JSON into a query string and a values list. It is not an ORM and it does not talk to the database: you keep your driver.

```bash
pip install filtersql
```

```json
{
  "action": "select",
  "source": "users",
  "filters": [{ "field": "name", "operator": "icontains", "value": "john" }]
}
```

```sql
select
  *
from
  "users"
where
  ("name" like ? escape '\')
```

```python
["%john%"]
```

The value is bound. The `%` wildcards are in the parameter, not in the SQL text. Works on PostgreSQL, SQLite, MySQL, DuckDB and Oracle. The name is `pg`, not `postgres`.

## Use it

```python
import filtersql

ds = filtersql.Datasource(source="users", dbms="sqlite")

query, values = ds.select(
    columns=["id", "first_name", "last_name"],
    filters=[
        {"field": "first_name", "operator": "icontains", "value": "John"},
        {"field": "last_name", "operator": "icontains", "value": "Smith"},
    ],
    order=[{"field": "first_name", "order": "asc"}],
    limit={"start": 0, "length": 10},
)

cursor.execute(query, values)
```

Same call from a payload, which is what a DataTables backend or a model should hand you. `dbms` is required and is not read from the payload:

```python
query, values = filtersql.filtersql(payload, dbms="pg", placeholder="%s")
```

`filtersql(**payload)` is not the same call. A client dict splatted into keyword arguments can set `scope`, `allowed_columns` or `raw_source`. Pass the payload as the first argument and the policy as named arguments.

## Don't let the model write SQL

```python
# this is how the incident starts
query = f"SELECT * FROM users WHERE {llm_output}"

# this is the replacement
payload = json.loads(llm_response)
query, values = filtersql.filtersql(
    payload,
    dbms="pg",
    allowed_sources={"users"},
    allowed_columns={"id", "first_name", "last_name", "status"},
    scope={"tenant_id": current_tenant},
)
cursor.execute(query, values)
```

A value cannot break out of a placeholder. A model can still name a table or a column you did not mean to expose, or pick `delete`. The three named arguments above are how you stop that. They cannot be set from the payload.

That is the whole product: the client describes the query, your code decides what is allowed.

## The rule

The payload chooses the intent. These are server configuration, passed as named arguments or to `Datasource`, never read from the body:

| You set | It stops |
|---|---|
| `allowed_sources` | `{"source": "pg_catalog.pg_class"}`. A raw source is checked too: the whole string must be listed |
| `allowed_columns` | a column, filter, sort, group, cursor, `returning` or write key you did not list. `SELECT *` and `raw` are refused, even if `allow_raw_fields=True`. An empty set allows nothing; `None` means no list |
| `scope` | rows outside the predicate. Folded in with `AND` by `select()`, `where()`, `update()`, `delete()` and `insert()`, so no `or` / `not` in the payload can drop it |
| leaving `raw` off | a client expression spliced into the SQL |

```python
ds = filtersql.Datasource(
    source="users",
    dbms="pg",
    scope={"tenant_id": 42, "owner_id": user_id},
    allowed_columns={"id", "name", "status", "created_at"},
    allowed_sources={"users"},
)
```

What that configuration actually guarantees:

- Values are bound. They are never concatenated into the SQL text.
- Identifiers are validated and quoted, with embedded quotes doubled.
- The few strings that must be literals (a JSONB key, the FTS language) are escaped, and a backslash in them is rejected where it cannot be escaped portably.
- When the placeholder is `%s`, a literal `%` in an identifier or a JSONB key is written `%%`, so psycopg2 and PyMySQL do not count an extra bind.

What it does not guarantee:

- **`scope` is not authorization.** `{"tenant_id": 42}` lets anyone in that tenant read and write every row. If a row has an owner, put the owner in the scope.
- **Without the two allowlists, the payload chooses the table, the columns and the action.** The database role is then your only boundary.
- **Reads and writes share one allowlist.** A column the client may filter on is a column it may `SET`. Use a second Datasource, with a shorter `allowed_columns`, for writes.
- **It does not cap resources.** There is no limit on the total number of filter nodes (depth is capped at 32 levels and `in` lists at 1 000 values, but a flat list can hold thousands of conditions), on `limit.start`, or on the length of a `regexp`. Put a statement timeout in front (`statement_timeout` on Postgres, `max_execution_time` on MySQL).
- **`raw` and `raw_source` are your SQL.** They are not escaped. With a `%s` driver a literal percent sign in them must be written `%%`.

Match is exact. `Name`, `name` and `users.name` are different strings. An output `alias` is not a column reference and is not checked. List a JSONB path as the client sends it: `attributes->>amount`. Scope columns do not have to be listed: a client cannot name them unless you list them, and can never set them (`insert` and `update` raise `ValidationError`).

Call `ds.select(...)` or `ds.delete(...)` yourself. If `action` comes from the body, the client picks the verb.

Before a client can reach a Datasource:

1. Set `allowed_sources` and `allowed_columns`. `scope` alone is not enough.
2. Fix the action per endpoint. Do not read `action` from the body.
3. Never call `filtersql(**request.json)`.
4. Leave `allow_raw_fields`, `allow_raw_source` and `raw_source` off.
5. Make `scope` the whole predicate (tenant and owner), not only the tenant.
6. Build statements with `select()` or `where()`. `having()` on its own does not add `scope`.
7. Use a least-privilege role and a statement timeout.
8. Log rejected payloads. They are usually the first sign of probing.

## Columns

A column is a string, or a dict. filtersql reads `field`, `alias` and `raw`; any other key is ignored, which is how a DataTables column list goes straight through:

```python
columns = [
    {"field": "id", "label": "ID", "visible": True, "editable": False},
    {"field": "first_name", "label": "First Name", "visible": True},
]
# or just
columns = ["id", "first_name", "last_name"]
```

`{"field": "count(*)", "raw": True, "alias": "total"}` is a literal expression. It needs `allow_raw_fields=True`, and it is refused while `allowed_columns` is set: a raw string is SQL, not a name you can allowlist. Aggregate through a view, or write that query yourself.

## Operators

A filter is `{"field", "operator", "value"}`. A list of them is `AND`. `{"or": [...]}`, `{"and": [...]}` and `{"not": ...}` nest, up to 32 levels. A group dict has exactly one of those keys. `not` takes one filter or a list, and a list means `NOT (a AND b)`. Empty groups are dropped.

```python
filters = [
    {"field": "status", "operator": "=", "value": "active"},
    {"or": [
        {"field": "role", "operator": "=", "value": "admin"},
        {"field": "age", "operator": ">=", "value": 60},
    ]},
    {"not": [
        {"field": "role", "operator": "=", "value": "guest"},
        {"field": "status", "operator": "=", "value": "banned"},
    ]},
]
```

```sql
where ("status" = ? and ("role" = ? or "age" >= ?) and not ("role" = ? and "status" = ?))
```

| You write | You get |
|---|---|
| `=`, `!=`, `>`, `>=`, `<`, `<=` | comparison, value bound |
| `in`, `notin`, `between` | a list of scalars. Empty `in` is `1 = 0`. Empty `notin` is `1 = 1`, which inside an `or` wipes the group. At most 1 000 values |
| `contains`, `starts_with`, `ends_with` and the `i*` / `not_*` forms | a bound pattern. Searching for `100%` binds `'%100\%%'`, not a wildcard |
| `null` / `notnull` | the only way to test NULL. Every other operator rejects `None` |
| `regexp` / `iregexp` | the native operator. On SQLite `iregexp` is just `regexp`: there is no case-insensitive mode |
| `fts` / `fts_query` | below. Anywhere else, `ValidationError` |

The other names (`not_contains`, `istarts_with`, …) and the per-dialect SQL are in [SPECS.md](https://github.com/fthiella/filtersql/blob/main/SPECS.md).

JSONB on Postgres, cast included. The key is a SQL literal, not a parameter, so a backslash in it is rejected: doubling `\` would change the key on a modern Postgres.

```python
{"field": "attributes->>amount", "operator": ">=", "value": "10000", "value_type": "numeric"}
# ("attributes"->>'amount')::numeric >= %s::numeric
```

Full text. On Postgres, `fts` searches a `tsvector` column and `fts_query` builds one from text. `fts_language` defaults to `english`. On MySQL the two operators are the same `MATCH ... AGAINST`, and the column needs a `FULLTEXT` index.

```python
ds = filtersql.Datasource(source="documents", dbms="pg", fts_language="italian")

{"field": "tsv_content", "operator": "fts", "value": "ossigeno"}
# "tsv_content" @@ websearch_to_tsquery('italian', %s)

{"field": "description", "operator": "fts_query", "value": "ossigeno"}
# to_tsvector('italian', coalesce("description", '')) @@ websearch_to_tsquery('italian', %s)

# mysql
{"field": "content", "operator": "fts", "value": "ossigeno"}
# match(`content`) against(%s in boolean mode)
```

## Your own SQL

`where()` returns only the parenthesized predicate, scope included, for a query you are writing by hand:

```python
ds = filtersql.Datasource(source="documents", dbms="pg", scope={"tenant_id": tenant})

where_clause, values = ds.where(filters=[
    {"field": "doc_type", "operator": "=", "value": "CONTRACT"},
    {"field": "doc_date", "operator": ">=", "value": "2025-01-01"},
])
# ('("tenant_id" = %s and "doc_type" = %s and "doc_date" >= %s)',
#  [tenant, "CONTRACT", "2025-01-01"])

query = f"""
    select v.chunk, m.doc_type
    from file_vectors v
    join file_metadata m on v.sha256 = m.sha256
    where v.model_name = %s
      and {where_clause}
    order by v.embedding <=> %s
"""
cursor.execute(query, [model_name, *values, query_embedding])
```

On Oracle, or any placeholder with `{n}`, `where()` numbers from `:1`. Binds you already wrote in the surrounding SQL will collide. Build the whole statement with `select()`, or use named binds in your own text.

## Pagination without OFFSET

```python
query, values = ds.select(
    columns=columns,
    order=[{"field": "id", "order": "asc"}],
    cursor={"id": last_seen_id},
    direction="next",
)
```

| `direction` | Predicate | |
|---|---|---|
| `next` | `id > last` | next page. The `ORDER BY` follows `order` |
| `prev` | `id < last` | previous page. The `ORDER BY` is flipped: reverse the rows in the app |
| `seek` | `id = value` | jump to a row |

`next` and `prev` require every cursor field in `order` and every order field in the cursor. Cursor values are scalars: `None` is rejected, because `id > NULL` matches nothing and the page would come back empty. The same field cannot appear twice in `order`. An unknown `direction` is an error even when there is no cursor.

`limit={"start": 0, "length": 10}` still works. `length` is at most 10 000, default 100. `limit={}` means that default. Leave `limit` out and there is no `LIMIT` clause. `2.9`, `True` and `NaN` are rejected.

## Writes

```python
ds.insert(values={"first_name": "John"}, returning="id")  # pg, sqlite, duckdb
ds.update(id={"id": 42}, values={"status": "active"})     # values: SET, then WHERE
ds.delete(id={"id": 42})
```

`returning` on MySQL or Oracle raises `ValidationError`. Keys in `values` and `id` are plain column names: a dot, a JSONB path, or a different spelling of a scope column is rejected. Scope is applied on all three, so an update cannot move a row to another tenant and a delete only sees the tenant you set. To filter a read by a path, use `filters`, not `id`.

## Grouping

```python
query, values = ds.select(
    columns=[
        {"field": "status"},
        {"field": "count(*)", "raw": True, "alias": "total"},
    ],
    filters=[{"field": "age", "operator": ">=", "value": 18}],
    group_by=["status"],
    having=[{"field": "count(*)", "raw": True, "operator": ">", "value": 5}],
)
```

`select()` adds `scope`. `having()` called on its own returns only the `HAVING` fragment and does not. `raw` is incompatible with `allowed_columns`, so an allowlisted Datasource cannot host this query: use a view, or write it by hand.

## A raw source

`source` is quoted. A subquery is not an identifier, so it takes two flags, on purpose: one of them cannot be turned on by accident.

```python
ds = filtersql.Datasource(
    source="(select * from users where active) as active_users",
    raw_source=True,
    allow_raw_source=True,
    dbms="pg",
)
```

The string is inserted unquoted. Hardcode it.

```python
# this is an identifier injection
ds = filtersql.Datasource(
    source=request.GET.get("table"),
    raw_source=True,
    allow_raw_source=True,
    dbms="pg",
)
```

## Dialects

| | `dbms` | Placeholder |
|---|---|---|
| PostgreSQL | `pg` | `%s` |
| SQLite | `sqlite` | `?` |
| DuckDB | `duckdb` | `?` |
| MySQL | `mysql` | `%s` |
| Oracle | `oracle` | `:1`, `:2`, … |

The value is case-insensitive. `postgres` is not a dialect and raises `ConfigurationError`. Oracle numbers its binds for you; you do not set `placeholder` for it. A custom marker may contain `{n}` once (`${n}` yields `$1`, `$2`). Without `{n}` it is repeated as-is (`$` yields `$`, `$`).

## Seeing the SQL

`debug()` substitutes the values for a log line. It is off unless `FILTERSQL_DEBUG=1` (also `true`, `yes`, `on`). Never execute what it returns.

```python
print(ds.debug(query, values))
# select "id" from "users" where ("first_name" ilike '%John%' escape '\')
```

Substitution skips text inside quotes, so a value like `what?` does not collide with a `?` placeholder.

## Examples

- [`examples/datatables/`](https://github.com/fthiella/filtersql/tree/master/examples/datatables) — Flask, DataTables server-side, per-column filters and a global search
- [`examples/pagination/`](https://github.com/fthiella/filtersql/tree/master/examples/pagination) — keyset pagination, with a separate allowlist for insert, update and delete
- [`examples/ai/`](https://github.com/fthiella/filtersql/tree/master/examples/ai) — model output → filtersql → SQLite
- [`examples/langchain/`](https://github.com/fthiella/filtersql/tree/master/examples/langchain) — a LangChain agent whose only tool takes filters; the policy's rejections go back to the model
- [`examples/pandas_duckdb/`](https://github.com/fthiella/filtersql/tree/master/examples/pandas_duckdb) — DataFrames through DuckDB

The payload, independent of Python, is specified in [SPECS.md](https://github.com/fthiella/filtersql/blob/master/SPECS.md). Release history is in [CHANGELOG.md](https://github.com/fthiella/filtersql/blob/master/CHANGELOG.md).

## License

MIT