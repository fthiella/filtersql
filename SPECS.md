# filtersql JSON Payload Specification (v1.0)

**Version**: 1.0 (Draft)

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
|   ├── order (array of column-ordering definitions)          |
|   ├── limit (object: start, length)                         |
|   └── cursor (object: multi-column context metrics)         |
+-------------------------------------------------------------+
```

### Top-Level Properties

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `action` | `string` | **Yes** | The CRUD intent. Allowed values: `"select"`, `"insert"`, `"update"`, `"delete"`. |
| `source` | `string` | **Yes** | The destination identifier (e.g., table name, database view, or subquery expression). |
| `columns` | `array` | No | Defines the projection properties. Used exclusively by `"select"`. |
| `filters` | `array` | No | A flat or nested set of conditions mapping directly to a SQL `WHERE` clause. |
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
* `value` (Any, Context-Dependent): The target criteria. Omitted for `null`/`notnull` operators. Must be an array for `in`, `notin`, and `between`.
* `value_type` (`string`, Optional): Instructs explicit datatype casting on evaluation (e.g., `"numeric"`, `"date"`), predominantly utilized in JSONB extraction operations.

#### Supported Filter Operators:
| Operator | Description | Value Type | Expected SQL Match |
| :--- | :--- | :--- | :--- |
| `=`, `!=` | Equality checks | Primitive | `=` or `!=` |
| `>`, `>=`, `<`, `<=` | Range evaluations | Primitive | Comparisons (`>`, `<=`, etc.) |
| `between` | Boundary check | Array `[min, max]` | `BETWEEN ? AND ?` |
| `in`, `notin` | Enumerated list membership | Array of primitives | `IN (?, ?, ...)` |
| `contains`, `icontains` | Substring match (Exact / Case-Insensitive) | `string` | `LIKE` / `ILIKE` with matching wildcards |
| `starts_with`, `istarts_with` | Prefix match (Exact / Case-Insensitive) | `string` | String pre\fix matching |
| `ends_with`, `iends_with` | Suffix match (Exact / Case-Insensitive) | `string` | String suffix matching |
| `null`, `notnull` | Emptiness evaluations | Omitted | `IS NULL` / `IS NOT NULL` |
| `reverse_in` | Constant scanning across columns | `string` (comma-sep columns)| `? IN (col1, col2)` |
| `regexp`, `iregexp` | Regular expression evaluation | `string` | Native Regex tokens (`~`, `~*`, `regexp_like`) |
| `fts`, `fts_query` | Full-Text Search processing | `string` | `@@ websearch_to_tsquery` or `MATCH AGAINST` |

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
To execute high-efficiency pagination over substantial dataset windows without resorting to performance-degrading `OFFSET` syntax, the payload implements **Keyset Pagination** via `cursor` and `direction`.

#### Invariant Rules:
1.  If `cursor` is provided, `direction` **must** also be provided.
2.  If `direction` is provided, `cursor` **must** also be provided.
3.  Any mismatch or isolating omission of either token must result in an explicit `ValidationError`.

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
        "type": ["string", "number", "boolean", "null"]
      }
    },
    "direction": {
      "type": "string",
      "enum": ["seek", "next", "prev"]
    }
  },
  "dependencies": {
    "cursor": ["direction"],
    "direction": ["cursor"]
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
            "value_type": { "type": "string", "enum": ["text", "numeric", "date"] }
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