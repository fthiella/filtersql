# filtersql

**Version: 0.9.5**

A compiler from structured JSON filters to safe SQL.

> **JSON → compiler → Safe SQL**

This library is not meant to cover every SQL feature, but it is designed specifically for:

* **DataTables** server-side backends
* **Access-style** (cursor-based) pagination
* **AI-generated** filter/query pipelines (LLM prompt engineering)

Supports **PostgreSQL, SQLite, MySQL, and Oracle**.

---

## Install

```bash
pip install filtersql
```

## Quick Start (SELECT)

```python
from filtersql import Datasource

ds = Datasource(source='users', dbms='Pg')

query, params = ds.select(
    columns=['id', 'first_name', 'email'],
    filters=[
        {'field': 'first_name', 'operator': 'icontains', 'value': 'john'},
        {'field': 'status', 'operator': '=', 'value': 'active'}
    ],
    order=[{'field': 'id', 'order': 'desc'}]
)

print(query)                                                    
print(params)

rows = execute_db(query, values)
```
## Core Concepts

```python
columns = ['id', 'first_name']                    # simple
```
or
```python
columns = [
    {'field': 'first_name', 'alias': 'First Name'},
    {'field': 'created_at', 'raw': True}          # raw SQL
]
```

## CRUD Operations (Insert, Update, Delete)

filtersql allows you to write, modify, and delete rows safely and cleanly.

### Insert

To insert a record into a table, pass your column-value dictionary to `insert()`:

```python
import filtersql

ds = filtersql.Datasource(source='users', dbms='Pg', placeholder='%s')

query, values = ds.insert(  
    values = {  
        'first_name': 'John',  
        'last_name': 'Smith',  
        'email': 'john.smith@example.com'  
    }  
)

print(query)  
# insert into "users"  
#   ("first_name", "last_name", "email")  
# values  
#   (%s, %s, %s)

print(values)  
# ['John', 'Smith', 'john.smith@example.com']
```

#### PostgreSQL returning

If you are using PostgreSQL, you can request that the statement returns a generated key (like an auto-incrementing ID) using the returning argument:

```python
query, values = ds.insert(  
    values    = {'first_name': 'John', 'last_name': 'Bobs'},  
    returning = 'id'  
)

print(query)  
# insert into "users"  
#   ("first_name", "last_name")  
# values  
#   (%s, %s)  
# returning "id"
```

### Update

Updating rows requires an id dictionary (to target rows using exact match equality =) and a values dictionary for the updated data:

```python
import filtersql

ds = filtersql.Datasource(source='users', dbms='Pg', placeholder='%s')

query, values = ds.update(  
    id     = {'id': 42, 'tenant_id': 1},  
    values = {'first_name': 'Johnny', 'status': 'active'}  
)

print(query)  
# update  
#   "users"  
# set  
#   "first_name" = %s,  
#   "status" = %s  
# where  
#   ("id" = %s and "tenant_id" = %s)

print(values)  
# ['Johnny', 'active', 42, 1]
```

### Delete

Deleting records requires only an id lookup coordinate dictionary:

```python
import filtersql

ds = filtersql.Datasource(source='users', dbms='Pg', placeholder='%s')

query, values = ds.delete(  
    id = {'id': 42, 'tenant_id': 1}  
)

print(query)  
# delete from  
#   "users"  
# where  
#   ("id" = %s and "tenant_id" = %s)

print(values)  
# [42, 1]
```

## Filters

### AND filters (default)

By default, flat lists of dictionaries are combined with `AND` operators:

```python
filters = [  
    {'field': 'status',   'operator': '=',         'value': 'active'},  
    {'field': 'doc_date', 'operator': '>=',        'value': '2025-01-01'},  
    {'field': 'title',    'operator': 'icontains', 'value': 'oxygen'},  
]  
# -> status = %s AND doc_date >= %s AND title ILIKE %s
```

### **OR groups**

Group conditions under `OR` logic by nesting them under the `'or'` key:

```python
filters = [  
    {'field': 'status', 'operator': '=', 'value': 'active'},  
    {'or': [  
        {'field': 'first_name', 'operator': 'icontains', 'value': 'john'},  
        {'field': 'last_name',  'operator': 'icontains', 'value': 'john'},  
    ]},  
]  
# -> status = %s AND (first_name ILIKE %s OR last_name ILIKE %s)
```

### Nesting

You can nest `AND` inside `OR` and vice versa:

```python
filters = [  
    {'or': [  
        {'field': 'doc_type', 'operator': '=', 'value': 'CONTRACT'},  
        {'and': [  
            {'field': 'doc_type', 'operator': '=',   'value': 'ORDER'},  
            {'field': 'amount',   'operator': '>=',  'value': '10000'},  
        ]},  
    ]},  
]  
# -> (doc_type = %s OR (doc_type = %s AND amount >= %s))
```

## Using filtersql with AI / LLM pipelines

The premise is straightforward: ask your LLM to output a clean JSON representing only target filters, validate it using Pydantic, and let filtersql assemble the actual, secure SQL query. The values are always passed as parameters so there is no risk of SQL injection even if the model produces unexpected output.

### Basic flow

user question -> LLM -> JSON -> Pydantic -> filtersql -> parameterized SQL

### Define the Pydantic schema

You tell the LLM exactly which fields and operators it can use. Anything outside the list gets rejected by Pydantic before it reaches the database.

```python
from pydantic import BaseModel, Field  
from typing import List, Literal

class SQLFilterSchema(BaseModel):  
    field: Literal[  
        'doc_type',  
        'doc_date',  
        'author',  
        'title',  
        'attributes->>supplier',  
        'attributes->>amount',  
    ] = Field(description="Column name or JSONB path")  
    operator: Literal[  
        '=', '!=', '>', '>=', '<', '<=',  
        'icontains', 'istarts_with',  
        'in', 'notin', 'null', 'notnull'  
    ] = Field(description="Comparison operator")  
    value: str = Field(description="Value to search for")

class QuerySchema(BaseModel):  
    semantic_query: str = Field(description="Cleaned query for vector/FTS search")  
    sql_filters: List[SQLFilterSchema] = Field(description="SQL filters")
```

### Call the LLM with structured output

```python
ai_response = ai_client.models.generate_content(  
    model='gemini-flash',  
    contents=user_question,  
    config=GenerateContentConfig(  
        system_instruction=YOUR_INTENT_PARSER_PROMPT,  
        response_mime_type="application/json",  
        response_schema=QuerySchema,  
        temperature=0.0,  
    )  
)  
parsed = QuerySchema.model_validate_json(ai_response.text)
```

### Build only the WHERE clause

Sometimes you don't want a full `SELECT`, you just want to inject dynamic filters into an existing query.

```python
import filtersql

filters = [f.model_dump() for f in parsed.sql_filters]

ds = filtersql.Datasource(source = 'documents', dbms = 'Pg', placeholder = '%s')

where_clause, values = ds.where(filters=filters)  
# where_clause: '("doc_type"=%s and "doc_date">=%s)'  
# values:       ['CONTRACT', '2025-01-01']
```

### JSONB fields and value_type

When a JSONB field contains numeric or date values, add `value_type` to get the right Postgres cast:

```python
{'field': 'attributes->>amount',      'operator': '>=', 'value': '10000',     'value_type': 'numeric'}  
# -> ("attributes"->>'amount')::numeric >= %s::numeric

{'field': 'attributes->>expiry_date', 'operator': '<=', 'value': '2025-12-31', 'value_type': 'date'}  
# -> ("attributes"->>'expiry_date')::date <= %s::date
```

Without the cast, Postgres performs text comparisons, leading to incorrect results for numeric ranges (e.g., `'9' > '10'`).

## Full-text search (PostgreSQL and MySQL only)

Two operators for full-text search using `websearch_to_tsquery`:

### fts (for a pre-built tsvector column)

```python
{'field': 'tsv_content', 'operator': 'fts', 'value': 'oxygen supply'}  
# -> "tsv_content" @@ websearch_to_tsquery('english', %s)
```

### fts_query (builds the tsvector on the fly from a text column)

```python
{'field': 'description', 'operator': 'fts_query', 'value': 'oxygen supply'}  
# -> to_tsvector('english', coalesce("description", '')) @@ websearch_to_tsquery('english', %s)
```

Default language is `'english'`. You can change it globally on initialization:

```python
ds = filtersql.Datasource(..., fts_language='italian')
```

### MySQL

MySQL FTS uses `MATCH() AGAINST()` in BOOLEAN MODE:

```python
{'field': 'content', 'operator': 'fts', 'value': 'oxygen supply'}
# -> match("content") against(? in boolean mode)
```
Note: Requires a FULLTEXT index on the column.

## Flask + DataTables example

```python
import filtersql  
from filtersql.utils import parseDatatableArgs

@app.route("/api/table.json")  
def table_json():  
    a = parseDatatableArgs(request.args)

    columns = [  
        {'field': 'id'},  
        {'field': 'first_name'},  
        {'field': 'last_name'},  
        {'field': 'company_name'},  
    ]

    # build filters from DataTable per-column search  
    filters = []  
    for k in a['columns'].values():  
        if k['search']['value']:  
            col = columns[int(k['data'])]  
            filters.append({  
                'field':    col['field'],  
                'operator': 'icontains',  
                'value':    k['search']['value'],  
            })

    # build order from DataTable  
    order = [  
        {'field': columns[int(k['column'])]['field'], 'order': k['dir']}  
        for k in a['order'].values()  
    ]

    ds = filtersql.Datasource(  
        source = 'sample_uk',  
        dbms   = 'SQLite',  
    )

    query, values = ds.select(columns=columns)  
    records_total = execute_db("select count(*) from ({}) t".format(query), values)[0][0]

    query, values = ds.select(columns=columns, filters=filters)  
    records_filtered = execute_db("select count(*) from ({}) t".format(query), values)[0][0]

    query, values = ds.select(  
        columns = columns,  
        filters = filters,  
        order   = order,  
        limit   = {'start': int(request.args.get('start')), 'length': int(request.args.get('length'))},  
    )  
    rows = execute_db(query, values)

    return jsonify(  
        draw            = int(request.args.get('draw')),  
        recordsTotal    = records_total,  
        recordsFiltered = records_filtered,  
        data            = rows,  
    )
```

## Access-style pagination

Cursor-based pagination without offset. Useful for large tables where `LIMIT x OFFSET y` gets slow, or when you need to navigate record by record like in Microsoft Access.

```python
ds = filtersql.Datasource(  
    source = 'sample_uk',  
    dbms   = 'SQLite',  
    move   = 'forwards',  
    order  = [{'field': 'id', 'order': 'asc'}],  
)

# Pass the cursor coordinates explicitly into the filters argument using type='move'  
cursor_filters = [{'field': 'id', 'value': last_seen_id, 'type': 'move'}]

query, values = ds.select(columns=columns, filters=cursor_filters)
```

Use `move='backwards'` to go in reverse, or `move='find'`
to jump to a specific record. Multi-column cursors are supported,
just add more entries to the filters list with `type='move'`.

## Filter operators

| Operator | Description |
| :---- | :---- |
| `=` `!=` `>` `>=` `<` `<=` | Comparison |
| `between` | Range - value must be a list of two items [low, high] |
| `contains` | Case-sensitive substring (LIKE '%x%') |
| `starts_with` | Case-sensitive prefix |
| `ends_with` | Case-sensitive suffix |
| `not_contains` | Case-sensitive substring exclusion |
| `not_starts_with` | Case-sensitive prefix exclusion |
| `icontains` | Case-insensitive substring (ILIKE) |
| `istarts_with` | Case-insensitive prefix |
| `iends_with` | Case-insensitive suffix |
| `not_icontains` | Case-insensitive substring exclusion |
| `null` / `notnull` | NULL checks (no value bound) |
| `in` / `notin` | List membership |
| `reverse_in` | Value in a set of columns - %s IN (col1, col2) |
| `regexp` | Case-sensitive regular expression |
| `iregexp` | Case-insensitive regular expression (Pg: ~*, Oracle: regexp_like with i) |
| `fts` | Full-text search on tsvector column (Pg only) |
| `fts_query` | Full-text search on text column (Pg only) |

## **Supported Engines**

We support standard dialect mappings out of the box. The parameter placeholder token defaults to `'?'` for all systems,
but can be manually overridden via constructor kwargs:

| DBMS | dbms value |
| :---- | :---- |
| PostgreSQL | `'Pg'` |
| SQLite | `'SQLite'` |
| MySQL | `'mysql'` |
| Oracle | `'Oracle'` |

Need a custom placeholder (like `%s`, `:val` or `$1`)? Just override it:

```python
ds = filtersql.Datasource(..., placeholder=':val')
```

## License

MIT