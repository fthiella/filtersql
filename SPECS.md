# filtersql JSON Payload Specification (v1.3.1)

**Version**: 1.3.1

This document defines the formal, language-agnostic JSON payload specification for **filtersql**. Any implementation of this protocol (whether written in Python, Node.js, Go, Rust, or any other language) must accept and validate payloads conforming to this standard.

The primary goal of this specification is to separate the client-side query intent from the database dialect, ensuring deterministic, secure, and parameterized SQL generation.

---

## 1. Core Structure

Every request payload must be a JSON object containing the top-level keys `action` and `source`. Additional keys depend on the specific operation being executed.

```
+-------------------------------------------------------------+
| JSON Payload                                                |
|   ├── action ("select" | "insert" | "update" | "delete")    |
|   ├── source (string: table, view, or raw subquery)         |
|   ├── columns (array of strings or structured objects)      |
|   ├── filters (array of standard or logically nested dicts) |
|   ├── group_by (array of strings)                           |
|   ├── having (array of standard or logically nested dicts)  |
|   ├── order (array of column-ordering definitions)          |
|   ├── limit (object: start, length)                         |
|   ├── cursor (object: multi-column context metrics)         |
|   ├── direction (string: "seek" | "next" | "prev")          |
|   ├── values (object, for insert/update)                    |
|   ├── id (object, for update/delete)                        |
|   └── returning (string, for insert)                        |
+-------------------------------------------------------------+
```

### Top-Level Properties

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `action` | `string` | **Yes** | The CRUD intent. Allowed values: `"select"`, `"insert"`, `"update"`, `"delete"`. Must be a string. |
| `source` | `string` | **Yes** | The destination identifier (e.g., table name, database view, or subquery expression). Non-empty. |
| `columns` | `array` | No | Defines the projection properties. Used exclusively by `"select"`. |
| `filters` | `array` | No | A flat or nested set of conditions mapping directly to a SQL `WHERE` clause. |
| `group_by` | `array of strings` | No | List of columns for `GROUP BY` |
| `having`   | `array of filters` | No | Same format as `filters`, applied as `HAVING` |
| `order` | `array` | No | A list defining the sorting hierarchy. |
| `limit` | `object` | No | Window configuration defining offset boundaries (`start` and `length`). |
| `cursor` | `object` | No | Coordinates containing field-value boundaries for keyset pagination. |
| `direction` | `string` | No | `"seek"`, `"next"`, `"prev"`. Required if `cursor` is provided. |
| `values` | `object` | No | Column → value pairs. Used by `"insert"` and `"update"`. |
| `id` | `object` | No | Column → value pairs identifying rows. Used by `"update"` and `"delete"`. |
| `returning` | `string` | No | Column to return from an `"insert"`. Not supported on `"mysql"`/`"oracle"`. |

---

## 2. Properties Specification

### 2.1 Columns Projection (`columns`)

The `columns` property defines the subset of attributes to retrieve. It is an array that can contain either **plain strings** or **structured objects**.

#### Structured Column Object Properties:
* `field` (`string`, **Required**): The name of the underlying database attribute or column.
* `alias` / `as` (`string`, Optional): A rename identifier mapped to the SQL `AS` operator. Must be a bare identifier: dots and JSONB operators (`t.x`, `data->>k`) raise `InvalidIdentifierError`.
* `raw` (`boolean`, Optional): If `true`, the `field` string is injected directly without automated quoting templates. Useful for aggregation primitives (`COUNT(*)`, `MAX(age)`).

```json
"columns": [
  "id",
  { "field": "doc_date", "alias": "created_at" },
  { "field": "COUNT(*)", "raw": true, "alias": "total_count" }
]
```

`value_type` is **not** honored on columns. Casting applies only to filter values on Pg JSONB paths (see §2.2).

---

### 2.2 Conditions Engine (`filters`)

The `filters` array serves as the collection point for constraints. By default, items placed at the root level of the `filters` array are evaluated using implicit `AND` logic.

#### Atomic Filter Object Properties:
* `field` (`string`, **Required**): The targeted column name, JSONB keypath (`attributes->>amount`), or schema-prefixed name (`m.author`).
* `operator` (`string`, **Required**): The evaluation token. There is no default — every filter must explicitly specify an operator.
* `value` (Any, Context-Dependent): The target criteria. Omitted for `null`/`notnull` operators. Must be an array for `in`, `notin`, and `between`.
* `value_type` (`string`, Optional): Instructs explicit datatype casting on evaluation. Honored only on Postgres JSONB paths (`col->>key`). Ignored elsewhere.

#### Supported Filter Operators:

| Operator | Description | Value Type | Expected SQL Match |
| :--- | :--- | :--- | :--- |
| `=`, `!=` | Equality checks | Primitive | `=` or `!=` |
| `>`, `>=`, `<`, `<=` | Range evaluations | Primitive | Comparisons (`>`, `<=`, etc.) |
| `between` | Boundary check | Array `[min, max]` | `BETWEEN ? AND ?` |
| `in`, `notin` | Enumerated list membership | Array of primitives (or scalar, treated as a 1-element list) | `IN (?, ?, ...)` |
| `contains`, `not_contains` | Substring match / exclusion (Case-Sensitive) | `string` | `LIKE` (or `GLOB`) with wildcards |
| `starts_with`, `not_starts_with`| Prefix match / exclusion (Case-Sensitive) | `string` | String prefix matching |
| `ends_with`, `not_ends_with` | Suffix match / exclusion (Case-Sensitive) | `string` | String suffix matching |
| `icontains`, `not_icontains` | Substring match / exclusion (Case-Insensitive) | `string` | `ILIKE` with wildcards |
| `istarts_with`, `not_istarts_with`| Prefix match / exclusion (Case-Insensitive)| `string` | String prefix matching |
| `iends_with`, `not_iends_with` | Suffix match / exclusion (Case-Insensitive) | `string` | String suffix matching |
| `null`, `notnull` | Emptiness evaluations | Omitted | `IS NULL` / `IS NOT NULL` |
| `regexp`, `not_regexp` | Regular expression / exclusion (Case-Sensitive) | `string` | Native Regex tokens (`~`, `!~`, `regexp_like`) |
| `iregexp`, `not_iregexp` | Regular expression / exclusion (Case-Insensitive) | `string` | Native Regex tokens (`~*`, `!~*`, etc.) |
| `fts`, `fts_query` | Full-Text Search processing | `string` | `@@ websearch_to_tsquery` or `MATCH AGAINST` |

**Pattern operators and bound values.** For `contains`, `starts_with`, `ends_with` and their `i*` / `not_*` variants, the wildcard markers are part of the bound value, not the SQL text. A payload `{"operator": "icontains", "value": "foo"}` produces a bound value of `"%foo%"` (with literal `%` / `_` in `foo` escaped). An implementation is free to generate the pattern differently in the SQL, but the value passed to the driver should follow this convention so that callers can reliably read, log, or replay the `values` list.

`in` / `notin` / `between` accept only **scalar** elements. A nested
list, tuple, dict, set, or `null` inside the value array — and a dict or
set as the value of `in` / `notin` — raises `ValidationError`. Values
that are scalar but not JSON-native (e.g. `date`, `Decimal`, `UUID`
when the payload is built in Python rather than parsed from JSON) are
accepted; they are bindable by the driver.

#### Null values

`col = NULL` is never true in SQL, so a `None`/`null` value is rejected (`ValidationError`) for every operator except `null` and `notnull`. This includes a missing `value` on an operator that needs one, and a `null` element inside the array of `in`, `notin` or `between`. Test for nullness with `{"operator": "null"}` / `{"operator": "notnull"}`.

#### Full-text search availability

`fts` is available on PostgreSQL and MySQL. `fts_query` is available on PostgreSQL and MySQL, but its semantics differ:

- On **PostgreSQL**, `fts_query` computes `to_tsvector('{lang}', coalesce(col, ''))` on the fly, so it works on any text column without a pre-built tsvector.
- On **MySQL**, `fts_query` is identical to `fts` and relies on `MATCH(col) AGAINST(...)`, which requires a `FULLTEXT` index on `col`. It does **not** vectorize on the fly.

On any other dialect, both raise `ValidationError`.

#### Empty List Handling for Set Operators (`in` / `notin`)

Passing an empty array (`"value": []`) to set evaluation operators is safely translated into deterministic SQL truths without throwing syntax errors:
* `"operator": "in"` with `[]` evaluates to `1 = 0` (Always FALSE).
* `"operator": "notin"` with `[]` evaluates to `1 = 1` (Always TRUE).

#### Set-size limit

`in` / `notin` accept at most **1000** values (`MAX_IN_LIST`). Larger arrays raise `ValidationError`.

#### Nested Logical Groups (`or` / `and` / `not`)

Complex trees are supported recursively. A group object contains **exactly one** group key — `"or"`, `"and"`, or `"not"` — and nothing else. Mixing a group key with a leaf (`{"or": [...], "field": "x"}`) or with another group key (`{"and": [...], "or": [...]}`) raises `ValidationError`.

* `"or"` / `"and"` take a list of filter definitions (atomic or nested). Items are joined with `OR` / `AND` respectively.
* `"not"` takes either a single filter definition (object) or a list of them. A list is implicitly joined with `AND`, then negated as a whole. So `{"not": [a, b]}` means `NOT (a AND b)`.

```json
"filters": [
  { "field": "status", "operator": "=", "value": "active" },
  {
    "or": [
      { "field": "first_name", "operator": "icontains", "value": "alex" },
      { "field": "last_name",  "operator": "icontains", "value": "alex" }
    ]
  },
  { "not": { "field": "role", "operator": "=", "value": "banned" } }
]
```

Nesting depth is capped at **32** (`MAX_FILTER_DEPTH`). Deeper trees raise `ValidationError`.

Empty groups (`{"or": []}`, `{"and": []}`, `{"not": []}`) are silently dropped from the generated clause.

---

### 2.3 Sorting Array (`order`)

The `order` property handles indexing sequences. It is an array of objects evaluated sequentially from index `0`.

#### Properties:
* `field` (`string`, **Required**): The sorting target attribute.
* `order` (`string`, Optional): Sort direction. Allowed values: `"asc"`, `"desc"`. Defaults to `"asc"`.

The same `field` may not appear twice in `order`: duplicates raise `ValidationError`.

```json
"order": [
  { "field": "doc_date", "order": "desc" },
  { "field": "id", "order": "asc" }
]
```

---

### 2.4 Keyset Pagination (`cursor` & `direction`)

To execute high-efficiency pagination over substantial dataset windows without resorting to performance-degrading `OFFSET` syntax, the payload implements **Keyset Pagination** via `cursor` and `direction`.

`direction` may be provided **without** `cursor`. In that case:

* `"prev"` inverts the `ORDER BY` (useful for a "prev page" navigation where the cursor isn't yet known).
* `"next"` and `"seek"` are no-ops on the `ORDER BY` (they only affect the `WHERE` clause, which is not generated without a cursor).

An invalid `direction` value is rejected whether or not a `cursor` is provided.

If `cursor` is provided, `direction` becomes **required** — a `cursor` without a direction is a `ValidationError`.

#### Properties:
* `cursor` (`object`): A flat dictionary mapping field tracking names to their last-seen tracking metric states. Supports single or multi-column coordinates.
* `direction` (`string`): Defines the trajectory vector relative to the cursor points.
    * `"next"`: Moves forward (`field > last_value`).
    * `"prev"`: Moves backward (`field < last_value`). Automatically handles internal sorting inversion during SQL construction.
    * `"seek"`: Pinpoints the specific coordinate matrix boundary (`field = value`).

```json
"cursor": {
  "doc_date": "2026-07-20",
  "id": 4192
},
"direction": "next"
```

For `"next"` / `"prev"`, every cursor key must appear in `order`, and every order field must appear in the cursor. Both violations are `ValidationError`.

Cursor values must be **scalars** (`string`, `number`, `boolean`, or a
Python-only bindable scalar such as `date`/`Decimal`). `null`, arrays,
and objects are rejected with `ValidationError`: SQL three-valued logic
makes `col <op> NULL` never match, so a `null` cursor value would
silently return zero rows on `next`/`prev`/`seek`.

---

### 2.5 Group By and Having

`group_by` accepts a list of column names (plain strings).

`having` uses the exact same filter format as `filters`. A `field` is quoted as an identifier by default. An aggregate expression like `COUNT(*)` is not an identifier, so mark it `"raw": true` and repeat the expression itself, rather than referencing the column's `alias`.

**Why not reference the alias?** PostgreSQL, Oracle, and SQL Server only expose SELECT-list aliases to `ORDER BY`/`GROUP BY`, not to `HAVING`. MySQL and SQLite are more permissive, but relying on that is non-portable. Repeating the expression works everywhere.

**Note on `raw`:** `raw: true` requires the server to opt in via a `Datasource(allow_raw_fields=True)` (or the equivalent in another implementation). A payload alone cannot enable raw mode — this is a security boundary, not an oversight. If raw is not enabled, the query build fails with a `ConfigurationError`.

```json
// WRONG - fails on PostgreSQL, Oracle, SQL Server
"having": [
  { "field": "total", "operator": ">", "value": 5 }
]

// CORRECT - repeat the expression, mark it raw
"having": [
  { "field": "COUNT(*)", "raw": true, "operator": ">", "value": 5 }
]
```

Full example:

```json
{
  "action": "select",
  "source": "users",
  "columns": [
    { "field": "status" },
    { "field": "COUNT(*)", "raw": true, "alias": "total" }
  ],
  "group_by": ["status"],
  "having": [
    { "field": "COUNT(*)", "raw": true, "operator": ">", "value": 5 }
  ]
}
```

---

### 2.6 Server-Side Configuration

The following parameters are **not** part of the payload. They are set by the application when constructing the `Datasource` (or equivalent) and must never be read from the payload.

| Parameter | Description |
| :--- | :--- |
| `dbms` | SQL dialect. Canonical values (lowercase): `'pg'`, `'sqlite'`, `'mysql'`, `'duckdb'`, `'oracle'`. Input is case-insensitive; `'PG'` resolves to `'pg'`. Unrecognized names (e.g. `'postgres'`) raise `ConfigurationError`. **Required** by `filtersql()`. |
| `placeholder` | Parameter marker used in generated SQL. Defaults per dialect (see below). |
| `scope` | Dict of `field: value` conditions applied to every operation. Used for multi-tenant filtering. Server-side only. |
| `fts_language` | Language name passed to `websearch_to_tsquery` (PostgreSQL only, default: `'english'`). |
| `allow_raw_fields` | If `false`, payloads containing `raw: true` raise `ConfigurationError`. |
| `allow_raw_source` / `raw_source` | Enable a raw subquery as `source`. Must be explicitly opted in. |
| `allowed_columns` | Exact-match allowlist of every column a client may reference (`columns`, `filters`, `having`, `order`, `group_by`, `cursor`, `returning`, keys of `values` and `id`). No normalization. While set, `SELECT *` and `raw` are refused. Scope columns need not be listed. `None` = unrestricted; an empty collection allows nothing. |
| `allowed_sources` | Exact-match allowlist for `source`, checked on every action (raw sources included). Same `None` / empty semantics. |

#### Default placeholders per dialect

| Dialect | Default placeholder |
| :--- | :--- |
| `pg` | `%s` |
| `sqlite` | `?` |
| `duckdb` | `?` |
| `mysql` | `%s` |
| `oracle` | `:{n}` (numbered, e.g. `:1`, `:2`) |

`oracle` uses numbered binds so a single statement can bind values in order. A custom `placeholder` may contain `{n}` at most once (e.g. `'${n}'` produces `$1`, `$2`, …). A placeholder without `{n}` is used verbatim for every value (`'$'` produces `$`, `$`, …).

The `filtersql()` convenience function rejects any payload or `**kwargs` that contains one of these keys, to prevent a client from escalating its own privileges. They must be supplied as **named parameters** to `filtersql()` (which forwards them to `Datasource`).

---

### 2.7 Column keys in `values` and `id`

The keys of `values` (in `insert` and `update`) and of `id` (in `update` and `delete`) are column names on the single table named as `source`.

They must be **single identifiers in Unicode NFC form**. Accepted characters are letters (ASCII and non-ASCII), digits, underscore, and spaces between characters. So `quantità`, `qta totale`, and `n° fattura` are valid. Rejected are characters that would break identifier quoting or change the meaning of the string: quotes, backslash, dot (schema qualification), `->`/`->>` (JSONB paths), control characters, and leading/trailing whitespace.

The NFC requirement is a hard contract: filtersql does not normalize input, it rejects non-NFC keys with `InvalidIdentifierError`. This makes the comparison below reliable, and puts the responsibility for canonical form on the schema, not on the request.

This restriction is what makes the `scope` collision check reliable. `scope` keys are compared against these keys by **NFC + casefold** string match, and the check would be defeatable if a client could reference the same physical column under a different spelling — for example `users.tenant_id`, or `tenant_id` with a trailing space, both of which normalize to the same column in some dialects.

To filter rows by a JSONB path or a qualified name, use `filters` in `select()`. The `id` parameter is for primary-key lookup only.

```json
// Accepted - the scope collision check works on these
{
  "action": "update",
  "source": "users",
  "id":     { "id": 42 },
  "values": { "email": "new@example.com" }
}
```

```json
// Rejected - qualified, contains a dot
{
  "action": "update",
  "source": "users",
  "id":     { "users.id": 42 },
  "values": { "email": "new@example.com" }
}
```

---

### 2.8 Returning (`returning`)

Used by `"insert"`. A single column name (plain identifier) that is added to the SQL as `RETURNING "col"`. Supported on `'pg'`, `'sqlite'`, `'duckdb'`. On `'mysql'` or `'oracle'`, `returning` raises `ValidationError`.

The returned column is checked against `allowed_columns` if that allowlist is set.

---

### 2.9 Limits and constants

| Constant | Value | Meaning |
| :--- | :--- | :--- |
| `DEFAULT_PAGE_LENGTH` | 100 | `length` used if omitted from `limit`. `limit: {}` applies the defaults (`start` 0); only an absent/`null` `limit` means no LIMIT clause. |
| `MAX_LIMIT_LENGTH` | 10 000 | Maximum `limit.length`. Exceeding raises `ValidationError`. |
| `MAX_IN_LIST` | 1 000 | Maximum number of values in `in` / `notin`. Exceeding raises `ValidationError`. |
| `MAX_FILTER_DEPTH` | 32 | Maximum nesting depth of `or` / `and` / `not`. Exceeding raises `ValidationError`. |

`limit.start` and `limit.length` must be integers. Strings that parse as integers (`"10"`) and integral numerics (`3.0`, `Decimal('3')`) are accepted; booleans, non-integral numbers (`2.9`), `NaN` and infinities raise `ValidationError`.

---

## 3. JSON Schema Specification (Draft 7)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "FilterSQLPayload",
  "type": "object",
  "required": ["action", "source"],
  "properties": {
    "action": {
      "type": "string",
      "enum": ["select", "insert", "update", "delete"]
    },
    "source": {
      "type": "string",
      "minLength": 1
    },
    "columns": {
      "type": "array",
      "items": {
        "anyOf": [
          { "type": "string" },
          {
            "type": "object",
            "required": ["field"],
            "properties": {
              "field": { "type": "string" },
              "alias": { "type": "string" },
              "as":    { "type": "string" },
              "raw":   { "type": "boolean" }
            },
            "additionalProperties": true
          }
        ]
      }
    },
    "filters": {
      "type": "array",
      "items": { "$ref": "#/definitions/filterElement" }
    },
    "group_by": {
      "type": "array",
      "items": { "type": "string" }
    },
    "having": {
      "type": "array",
      "items": { "$ref": "#/definitions/filterElement" }
    },
    "order": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["field"],
        "properties": {
          "field": { "type": "string" },
          "order": { "type": "string", "enum": ["asc", "desc"] }
        }
      }
    },
    "limit": {
      "type": "object",
      "properties": {
        "start":  { "type": "integer", "minimum": 0 },
        "length": { "type": "integer", "minimum": 1, "maximum": 10000 }
      },
      "additionalProperties": false
    },
    "cursor": {
      "type": "object",
      "additionalProperties": {
        "type": ["string", "number", "boolean"]
      }
    },
    "direction": {
      "type": "string",
      "enum": ["seek", "next", "prev"]
    },
    "values": { "type": "object" },
    "id":     { "type": "object" },
    "returning": { "type": "string", "minLength": 1 }
  },
  "dependencies": {
    "cursor": ["direction"]
  },
  "definitions": {
    "filterElement": {
      "anyOf": [
        {
          "type": "object",
          "required": ["field", "operator"],
          "properties": {
            "field": { "type": "string" },
            "operator": { "type": "string" },
            "value": {},
            "value_type": {
              "type": "string",
              "enum": ["numeric", "integer", "bigint", "real", "double precision",
                       "date", "timestamp", "timestamptz", "time", "boolean", "uuid"]
            },
            "raw": { "type": "boolean" }
          }
        },
        {
          "type": "object",
          "required": ["or"],
          "properties": {
            "or": {
              "type": "array",
              "items": { "$ref": "#/definitions/filterElement" }
            }
          },
          "additionalProperties": false
        },
        {
          "type": "object",
          "required": ["and"],
          "properties": {
            "and": {
              "type": "array",
              "items": { "$ref": "#/definitions/filterElement" }
            }
          },
          "additionalProperties": false
        },
        {
          "type": "object",
          "required": ["not"],
          "properties": {
            "not": {
              "anyOf": [
                { "$ref": "#/definitions/filterElement" },
                {
                  "type": "array",
                  "items": { "$ref": "#/definitions/filterElement" }
                }
              ]
            }
          },
          "additionalProperties": false
        }
      ]
    }
  }
}
```

---

## 4. Concrete Examples

### 4.1 SELECT with Hierarchical Filters

```json
{
  "action": "select",
  "source": "documents",
  "columns": [
    "id",
    { "field": "title", "alias": "document_title" },
    { "field": "attributes->>amount", "alias": "cached_amount" }
  ],
  "filters": [
    { "field": "status", "operator": "=", "value": "published" },
    {
      "or": [
        { "field": "author", "operator": "=", "value": "Federico" },
        { "and": [
            { "field": "doc_type", "operator": "=", "value": "CONTRACT" },
            { "field": "attributes->>amount", "operator": ">=", "value": "5000", "value_type": "numeric" }
          ]
        }
      ]
    }
  ],
  "order": [{ "field": "id", "order": "desc" }],
  "limit": { "start": 0, "length": 25 }
}
```

### 4.2 INSERT Operation

```json
{
  "action": "insert",
  "source": "users",
  "values": {
    "first_name": "John",
    "last_name": "Smith",
    "role": "admin"
  }
}
```

### 4.3 UPDATE with Filter Arrays

```json
{
  "action": "update",
  "source": "contracts",
  "id": {
    "id": 1042
  },
  "values": {
    "status": "archived",
    "updated_at": "2026-07-20T20:00:00Z"
  }
}
```

### 4.4 Multi-Column Keyset Pagination Vector

```json
{
  "action": "select",
  "source": "contract",
  "columns": ["id", "doc_date", "subject"],
  "cursor": {
    "doc_date": "2026-01-15",
    "id": 894
  },
  "direction": "next",
  "order": [
    { "field": "doc_date", "order": "asc" },
    { "field": "id", "order": "asc" }
  ],
  "limit": { "length": 50 }
}
```

### 4.5 Nested NOT

```json
{
  "action": "select",
  "source": "users",
  "columns": ["id", "status"],
  "filters": [
    { "field": "status", "operator": "=", "value": "active" },
    {
      "not": [
        { "field": "role", "operator": "=", "value": "guest" },
        { "field": "locked", "operator": "=", "value": true }
      ]
    }
  ]
}
```

Produces (SQLite, `?` placeholders):

```sql
where
  ("status" = ? and not ("role" = ? and "locked" = ?))
```

Values: `["active", "guest", true]`.