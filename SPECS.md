# filtersql JSON Payload Specification (v1.2.7)

**Version**: 1.2.7

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
|   └── direction (string: "seek" | "next" | "prev")          |
+-------------------------------------------------------------+
```

### Top-Level Properties

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `action` | `string` | **Yes** | The CRUD intent. Allowed values: `"select"`, `"insert"`, `"update"`, `"delete"`. |
| `source` | `string` | **Yes** | The destination identifier (e.g., table name, database view, or subquery expression). |
| `columns` | `array` | No | Defines the projection properties. Used exclusively by `"select"`. |
| `filters` | `array` | No | A flat or nested set of conditions mapping directly to a SQL `WHERE` clause. |
| `group_by` | `array of strings` | No | List of columns for `GROUP BY` |
| `having`   | `array of filters` | No | Same format as `filters`, applied as `HAVING` |
| `order` | `array` | No | A list defining the sorting hierarchy. |
| `limit` | `object` | No | Window configuration defining offset boundaries (`start` and `length`). |
| `cursor` | `object` | No | Coordinates containing field-value boundaries for keyset pagination. |
| `direction` | `string` | No | Required if `cursor` is provided. Allowed values: `"seek"`, `"next"`, `"prev"`. |

---

## 2. Properties Specification

### 2.1 Columns Projection (`columns`)
The `columns` property defines the subset of attributes to retrieve. It is an array that can contain either **plain strings** or **structured objects**.

#### Structured Column Object Properties:
* `field` (`string`, **Required**): The name of the underlying database attribute or column.
* `alias` / `as` (`string`, Optional): A rename identifier mapped to the SQL `AS` operator.
* `raw` (`boolean`, Optional): If `true`, the `field` string is injected directly without automated quoting templates. Useful for aggregation primitives (`COUNT(*)`, `MAX(age)`).

```json
"columns": [
  "id",
  { "field": "doc_date", "alias": "created_at" },
  { "field": "COUNT(*)", "raw": true, "alias": "total_count" }
]
```

---

### 2.2 Conditions Engine (`filters`)
The `filters` array serves as the collection point for constraints. By default, items placed at the root level of the `filters` array are evaluated using implicit `AND` logic.

#### Atomic Filter Object Properties:
* `field` (`string`, **Required**): The targeted column name, JSONB keypath (`attributes->>amount`), or schema-prefixed name (`m.author`).
* `operator` (`string`, **Required**): The evaluation token.  
  There is no default — every filter must explicitly specify an operator.
* `value` (Any, Context-Dependent): The target criteria. Omitted for `null`/`notnull` operators. Must be an array for `in`, `notin`, and `between`.
* `value_type` (`string`, Optional): Instructs explicit datatype casting on evaluation (e.g., `"numeric"`, `"date"`), predominantly utilized in JSONB extraction operations.

#### Supported Filter Operators:

| Operator | Description | Value Type | Expected SQL Match |
| :--- | :--- | :--- | :--- |
| `=`, `!=` | Equality checks | Primitive | `=` or `!=` |
| `>`, `>=`, `<`, `<=` | Range evaluations | Primitive | Comparisons (`>`, `<=`, etc.) |
| `between` | Boundary check | Array `[min, max]` | `BETWEEN ? AND ?` |
| `in`, `notin` | Enumerated list membership | Array of primitives | `IN (?, ?, ...)` |
| `contains`, `not_contains` | Substring match / exclusion (Case-Sensitive) | `string` | `LIKE` (or `GLOB`) with wildcards |
| `starts_with`, `not_starts_with`| Prefix match / exclusion (Case-Sensitive) | `string` | String prefix matching |
| `ends_with`, `not_ends_with` | Suffix match / exclusion (Case-Sensitive) | `string` | String suffix matching |
| `icontains`, `not_icontains` | Substring match / exclusion (Case-Insensitive) | `string` | `ILIKE` with wildcards |
| `istarts_with`, `not_istarts_with`| Prefix match / exclusion (Case-Insensitive)| `string` | String prefix matching |
| `iends_with`, `not_iends_with` | Suffix match / exclusion (Case-Insensitive) | `string` | String suffix matching |
| `null`, `notnull` | Emptiness evaluations | Omitted | `IS NULL` / `IS NOT NULL` |
| `reverse_in` | Constant scanning across columns | Scalar | `? IN (col1, col2)` |
| `regexp`, `not_regexp` | Regular expression / exclusion (Case-Sensitive) | `string` | Native Regex tokens (`~`, `!~`, `regexp_like`) |
| `iregexp`, `not_iregexp` | Regular expression / exclusion (Case-Insensitive) | `string` | Native Regex tokens (`~*`, `!~*`, etc.) |
| `fts`, `fts_query` | Full-Text Search processing | `string` | `@@ websearch_to_tsquery` or `MATCH AGAINST` |

For `reverse_in`, the field is a comma-separated list of column names, and value is a scalar.

A scalar value is also accepted for `in`/`notin` and treated as a single-element list.

`fts` is available on PostgreSQL and MySQL. `fts_query` is available on PostgreSQL only. Using either on an unsupported dialect raises `ValidationError`.

#### Empty List Handling for Set Operators (`in` / `notin`)
Passing an empty array (`"value": []`) to set evaluation operators is safely translated into deterministic SQL truths without throwing syntax errors:
* `"operator": "in"` with `[]` evaluates to `1 = 0` (Always FALSE).
* `"operator": "notin"` with `[]` evaluates to `1 = 1` (Always TRUE).

#### Nested Logical Groups (`or` / `and`):
Complex trees are supported recursively by defining an object containing a single key (`"or"` or `"and"`) containing a sub-array of filter definitions.

```json
"filters": [
  { "field": "status", "operator": "=", "value": "active" },
  {
    "or": [
      { "field": "first_name", "operator": "icontains", "value": "alex" },
      { "field": "last_name", "operator": "icontains", "value": "alex" }
    ]
  }
]
```

---

### 2.3 Sorting Array (`order`)
The `order` property handles indexing sequences. It is an array of objects evaluated sequentially from index `0`.

#### Properties:
* `field` (`string`, **Required**): The sorting target attribute.
* `order` (`string`, Optional): Sort direction. Allowed values: `"asc"`, `"desc"`. Defaults to `"asc"`.

```json
"order": [
  { "field": "doc_date", "order": "desc" },
  { "field": "id", "order": "asc" }
]
```

---

### 2.4 Keyset Pagination (`cursor` & `direction`)

To execute high-efficiency pagination over substantial dataset windows
without resorting to performance-degrading `OFFSET` syntax, the payload
implements **Keyset Pagination** via `cursor` and `direction`.

If `cursor` is provided, `direction` must also be provided - a cursor
without a direction is a `ValidationError`.

`direction` may be provided without `cursor`. In that case it only
inverts `ORDER BY`, which is useful for a "prev page" navigation where
the cursor isn't yet known.

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

### 2.5 Group By and Having

`group_by` accepts a list of column names (plain strings).

`having` uses the exact same filter format as `filters`. A `field` is
quoted as an identifier by default. An aggregate expression like `COUNT(*)`
is not an identifier, so mark it `"raw": true` and repeat the expression
itself, rather than referencing the column's `alias`.

**Why not reference the alias?** PostgreSQL, Oracle, and SQL Server only
expose SELECT-list aliases to `ORDER BY`/`GROUP BY`, not to `HAVING`.
MySQL and SQLite are more permissive, but relying on that is non-portable.
Repeating the expression works everywhere.

**Note on `raw`:** `raw: true` requires the server to opt in via a
`Datasource(allow_raw_fields=True)` (or the equivalent in another
implementation). A payload alone cannot enable raw mode — this is a
security boundary, not an oversight. If raw is not enabled, the query
build fails with a `ConfigurationError`.

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

### 2.6 Server-Side Configuration

The following parameters are **not** part of the payload. They are set
by the application when constructing the `Datasource` (or equivalent)
and must never be read from the payload.

| Parameter | Description |
| :--- | :--- |
| `dbms` | SQL dialect: `'Pg'`, `'SQLite'`, `'mysql'`, `'DuckDB'`, `'Oracle'`. Case-insensitive. |
| `placeholder` | Parameter marker used in generated SQL: `%s` (Pg/MySQL), `?` (SQLite/DuckDB/Oracle), or a custom string. |
| `scope` | Dict of `field: value` conditions applied to every operation. Used for multi-tenant filtering. Server-side only. |
| `fts_language` | Language name passed to `websearch_to_tsquery` (PostgreSQL only, default: `'english'`). |
| `allow_raw_fields` | If `false`, payloads containing `raw: true` raise `ConfigurationError`. |
| `allow_raw_source` / `raw_source` | Enable a raw subquery as `source`. Must be explicitly opted in. |

The `filtersql()` convenience function rejects any payload that
contains one of these keys, to prevent a client from escalating its
own privileges.

### 2.7 Column keys in `values` and `id`

The keys of `values` (in `insert` and `update`) and of `id` (in `update`
and `delete`) are column names on the single table named as `source`.
They must be **single bare identifiers**: letters, digits, underscore,
no whitespace.

Qualified names (`users.id`), quoted names, and JSONB paths
(`attributes->>x`) are rejected with `InvalidIdentifierError`.

This restriction is what makes the `scope` collision check reliable.
`scope` keys are compared against these keys by case-insensitive string
match, and the check would be defeatable if a client could reference
the same physical column under a different spelling - for example
`users.tenant_id`, or `tenant_id` with a trailing space, both of which
normalize to the same column in some dialects.

To filter rows by a JSONB path or a qualified name, use `filters` in
`select()`. The `id` parameter is for primary-key lookup only.

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
              "as": { "type": "string" },
              "raw": { "type": "boolean" }
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
        "start": { "type": "integer", "minimum": 0 },
        "length": { "type": "integer", "minimum": 1 }
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
    }
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
    { "field": "attributes->>amount", "alias": "cached_amount", "value_type": "numeric" }
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