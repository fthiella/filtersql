# Changelog

All notable changes to this project will be documented in this file.

## [1.2.7] - 2026-09-24

### Security
- **Scope bypass via identifier normalization.**
  `insert()` and `update()` accepted column keys such as `"tenant_id "`
  (trailing whitespace) or `"users.tenant_id"` (qualified) that
  `_quote()` normalizes to the same physical column as a
  `scope`-enforced key, but that the collision check - which compared
  raw strings - did not recognize. On MySQL, `SET users.tenant_id = ...`
  is accepted and silently updated the scope column; on SQLite, trailing
  whitespace was stripped by `_quote()` and the same effect occurred.
  Both allowed a client to overwrite the column that determines its own
  tenant.

  Write-target keys now reject the leading/trailing whitespace,
  qualification, quoting, and JSONB-path syntaxes that were being
  normalized away, and the scope-collision check compares keys by
  Unicode NFC + casefold on both sides. This closes the bypass by
  construction: rather than trying to detect every dialect-specific
  spelling of "the same column", the spellings that would require
  detection are rejected, and the remaining comparison has no
  normalization gap.

### Added
- Write-target keys (`values` in `insert`/`update`, `id` in
  `update`/`delete`) now accept the full set of characters that are
  legal in a quoted SQL identifier: spaces between characters
  (`"qta totale"`), non-ASCII letters (`"quantità"`, `"città"`), and
  symbols that are not structurally significant (`"n° fattura"`).
  Previously these were rejected by an overly strict `\w+` check.

### Fixed
- `where()` now validates its `order` argument the same way `select()`
  does. Previously a malformed `order` passed directly to `where()`
  raised `TypeError`/`KeyError` from inside `_build_where` instead of
  a `ValidationError`.
- `_build_limit()` now rejects `length <= 0`, aligning with the
  `"minimum": 1` declared in the SPECS JSON Schema. Previously `length=0`
  produced `LIMIT 0, 0`.
- `filtersql()` now validates that `payload` is a dict and that `action`
  is a string before calling `.lower()`. Previously `filtersql(payload=[1,2,3])`
  raised `AttributeError`, and `filtersql({"action": 1})` raised
  `AttributeError` on the `.lower()` call.
- `Datasource.__init__()` now validates that `scope` is a dict and that
  each key is a bare identifier. Previously a malformed scope key
  (e.g. `"tenant_id "`) was accepted at construction and failed later
  at the first query.

### Breaking Changes
- Write-target keys must be valid Unicode identifiers in NFC form.
  Leading or trailing whitespace, qualified names (`users.id`),
  quoted names, backslashes, and JSONB paths (`data->>x`) are
  rejected with `InvalidIdentifierError`. `id` no longer accepts
  JSONB paths; use `filters` in `select()` for non-key filtering.

### Notes
- No other behavior changed. The `scope` feature continues to work as
  before for plain identifiers.
- Upgrade recommended for all multi-tenant deployments. If you use
  `scope`, this release closes a path that let a client reassign its
  own records to another tenant.

## [1.2.6] - 2026-09-20

### Security
- **Scope bypass in `insert()`, `update()`, and `delete()`.**
  A client could pass a scoped field name (e.g. `tenant_id`) inside
  `values` (for insert/update) or `id` (for delete) and bypass the
  server-side tenant boundary. In `update()`, this allowed moving a
  record out of its own scope. All three methods now raise
  `ValidationError` when a scoped field collides with user input.

### Fixed
- `_safe_sql_literal()` now rejects null bytes instead of letting the
  driver crash with an opaque error.
- `_build_filter_group()` skips empty `{'or': []}` / `{'and': []}`
  groups — including nested groups whose children are all empty —
  instead of emitting an invalid `()` clause.
- `delete()` validates that `id` is a dict (was `AttributeError`).
- `where()` validates that `filters` is a list.
- `select()` validates that `order` items are dicts with a `field` key,
  and that `limit` is a dict.
- `_build_limit()` handles `None`, non-integer, and negative values.
- `_invert_order()` and `_cursor_operator()` now accept `'ASC'`/`'DESC'`.
- `filtersql()` blacklist extended: `fts_language` is now rejected when
  supplied via the payload, alongside `dbms`, `placeholder`, `scope`,
  and `allow_raw_*`. All server-side configuration follows the same rule
  - kwarg only, never payload.

### Notes
- No breaking changes to documented behavior.
- Upgrade recommended for all multi-tenant deployments and for anyone
  using `filtersql()` with untrusted input.

## [1.2.5] - 2026-09-19

### Fixed
- **`debug()` substituted values that contain the placeholder character.**
  With `placeholder='?'`, a value such as `"what?"` would cause the next
  iteration of the substitution loop to replace the `?` *inside the
  already-formatted value* instead of the next real placeholder. `debug()`
  now splits the query on the placeholder once, recomposes with the
  formatted values, and returns the query unchanged if the placeholder
  count doesn't match `len(values)`.
- **`select()` had a dead validation branch for non-list `filters`.**
  `filters = list(filters or [])` always produced a list, so the
  subsequent `isinstance(filters, list)` check could never fail; a dict
  passed as `filters` would be silently converted to its keys and fail
  later with an opaque error. The type check now runs *before* the
  conversion.
- **`filtersql()` blacklist now also covers `placeholder`, `dbms`, and
  `scope`.** The 1.2.3 release closed the payload-based escalation for
  `raw_source` / `allow_raw_source` / `allow_raw_fields`, but these three
  server-side parameters could still be set from an untrusted payload. A
  payload such as `{"placeholder": "? or 1=1"}` could turn a parameterized
  query into a non-parameterized one. All six keys are now rejected with a
  clear `ValidationError` before they can reach the `Datasource`.

### Documentation
- Aligned `SPECS.md` with the implementation:
  - `value_type` enum now matches `_PG_ALLOWED_CAST_TYPES` (added `real`,
    `double precision`, `time`; removed `text`, which was a no-op cast).
  - `direction` without `cursor` is now documented as legal (it only
    inverts `ORDER BY`); the previous "Invariant Rules" contradicted the
    implementation.
  - `raw` is now present in the `filterElement` schema.
  - New §2.6 documents the server-side configuration surface (`dbms`,
    `placeholder`, `scope`, `fts_language`, `allow_raw_fields`,
    `allow_raw_source`/`raw_source`) and states that none of it may be
    supplied via the payload.
- `README.md`: fixed the `allow_raw_fields` typo, removed a duplicated
  "Lightweight" bullet, corrected the multi-column cursor example (the
  `order` list must contain the cursor fields), replaced the misleading
  `placeholder=':val'` example with a real one, and aligned the Pydantic
  and Gemini schemas to scalar-only operators (matching the caveat already
  present for the Gemini example).

### Notes
- No breaking changes to documented behavior. All three code fixes tighten
  validation or correct output for inputs that previously produced
  misleading results (debug output) or crashed with a driver-level error
  (placeholder injection via payload).
- Upgrade recommended for anyone using the `filtersql()` convenience
  function with input that isn't fully server-controlled.

## [1.2.4] - 2026-08-09

### Added
- `dbms` is now case-insensitive: `'pg'`, `'PG'`, `'Pg'` (and equivalents
  for `SQLite`, `mysql`, `DuckDB`, `Oracle`) all resolve to the same
  canonical dialect. Only casing is normalized - unrecognized names or
  aliases (e.g. `'postgres'`) still raise `ConfigurationError` exactly as
  before, listing the valid canonical names. Internal `DBMS_MAP` keys and
  every `self.dbms == 'Pg'`-style comparison in the codebase are
  unchanged; normalization happens once, in the constructor.

### Fixed
- **MySQL: invalid `ESCAPE` clause syntax on wildcard operators.** Any
  `contains`/`starts_with`/`ends_with` (and their `not_`/`i`/`not_i`
  variants) on `dbms='mysql'` generated `escape '\'` - a single backslash,
  which MySQL's default string-literal escaping rules treat as an escaped
  quote, leaving the literal unterminated and the query unparsable.
  `_safe_sql_literal` is now dialect-aware and doubles embedded backslashes
  for MySQL (Pg/SQLite/DuckDB use standard-conforming strings and are
  unaffected); `_wildcard_escape_clause` routes through it instead of
  interpolating the raw escape character.
- **Scalar operators (`=`, `!=`, `>`, `contains`, `regexp`, `fts`, etc.)
  silently accepted list/tuple/dict values.** A filter such as
  `{'operator': '=', 'value': []}` produced a syntactically valid query
  with a list bound as a scalar parameter, which then failed at the driver
  with an opaque binding error instead of a clear `ValidationError` at
  build time. These operators now reject non-scalar values immediately.
- **`in`/`notin` with a falsy scalar value (`''`, `0`, `False`) produced a
  placeholder/value-count mismatch.** The WHERE-clause builder decided
  "empty" by checking truthiness of the raw value (`not ''` → treated as
  empty, 0 placeholders), while the values-list builder checked the
  already-listified value (`['']` → not empty, 1 value) - the two
  disagreed, producing `Incorrect number of bindings supplied` at
  execution time. Both now normalize to a list before deciding emptiness,
  so they always agree.
- **`_quote()` silently produced an empty identifier for input consisting
  only of dots** (e.g. `field: '.'`), splicing nothing into the SQL text
  instead of raising. Now raises `InvalidIdentifierError`.
- Added regression tests for all of the above (property-based, via
  `hypothesis`, plus real-execution tests against SQLite and AST validation
  against all 5 supported dialects via `sqlglot`).

### Notes
- No breaking changes to documented behavior - all four fixes tighten
  validation or correct dialect-specific SQL generation for inputs that
  either previously produced wrong/invalid SQL or crashed with a
  driver-level error. Any code relying on those specific broken behaviors
  (e.g. catching `sqlite3.ProgrammingError` from a filtersql-built query)
  should now expect a `ValidationError`/`InvalidIdentifierError` instead.
- Upgrade recommended for all MySQL users, and for anyone accepting
  filter payloads from untrusted or loosely-validated sources (frontends,
  LLM output).

## [1.2.3] - 2026-07-28
### Security
- `raw_source` and `raw` (on columns/filters) now require explicit opt-in.
  Previously, setting `raw_source=True` or `raw=True` worked unconditionally,
  bypassing all quoting/escaping. This is now gated behind two new
  `Datasource` constructor flags, `allow_raw_source` and `allow_raw_fields`
  (both default `False`) - the feature must be explicitly enabled server-side,
  so it can't be turned on accidentally or via client-controlled input.
  This is a breaking change: existing code using `raw_source=True` or
  `raw=True` must now also pass `allow_raw_source=True` / `allow_raw_fields=True`.
- Closed a related gap in the `filtersql()` convenience function: `raw_source`,
  `allow_raw_source`, and `allow_raw_fields` can no longer be set via the
  JSON payload itself - only as server-side keyword arguments. Previously
  `raw_source` could be flipped on by an untrusted payload.
- `debug()` is now disabled unless the `FILTERSQL_DEBUG=1` environment
  variable is set, to prevent accidental use in production. This is also
  a breaking change for any code calling `debug()` without that env var set.
- Upgrade recommended for all users of 1.2.x.

### Fixed
- Keyset pagination (`cursor`) now respects each column's own sort direction.
  Previously the `next`/`prev` comparison operator was applied uniformly to
  every cursor column regardless of its `asc`/`desc` setting in `order`,
  silently producing wrong results (missing/duplicate rows, no error) for
  any multi-column sort mixing directions.
- Fixed a related bug where an `order` passed directly to `select()` (to
  override the `Datasource`'s constructor-time order) was ignored by the
  cursor logic, causing the generated `WHERE` and `ORDER BY` clauses to
  disagree.
- Fixed a bug where using `cursor`/`direction` with no `order` configured
  anywhere could silently drop the cursor condition, returning an
  unfiltered query instead of the paginated slice.
- Added regression tests for all of the above.
- Empty List Handling (`in` / `notin`): Passing an empty array (`value: []`) now compiles safely to `1 = 0` (for `in`) or `1 = 1` (for `notin`) instead of generating syntactically invalid SQL (`IN ()`).
- Quote Stripping in `_safe_sql_literal`: Removed `.strip("\"'")` so JSON keys or literals starting/ending with literal quotes are not unintentionally modified during string escaping.

### Added
- **JSONB `value_type` Whitelist & Validation**: Expanded Postgres JSONB cast support to include `integer`, `bigint`, `real`, `double precision`, `timestamp`, `timestamptz`, `time`, `boolean`, and `uuid` alongside `numeric` and `date`. Passing an unrecognized `value_type` now raises a clear `ValidationError`.

### Documentation
- Updated `README.md` and `SPECS.md` to document the empty list (`1 = 0` / `1 = 1`) evaluation semantics.
- Updated `SPECS.md` JSON Schema with the expanded `value_type` enum.
- Documented `raw_source` / `allow_raw_source` in the README (previously
  undocumented), including a safe/unsafe usage example.
- Updated the `raw=True` column/`having` examples to include the required
  `allow_raw_fields=True` flag.
- Noted the `FILTERSQL_DEBUG=1` requirement for `debug()`.

## [1.2.2] - 2026-07-27
### Security
- Fixed a SQL injection vulnerability affecting the `fts_language`
  constructor parameter. A value containing a single quote could break out
  of the `websearch_to_tsquery(...)` string literal and inject arbitrary SQL.
- Affected: any application passing an `fts_language` value that isn't a
  fixed, developer-controlled string (e.g. derived from a user-facing
  locale/language selector) when using the `fts`/`fts_query` operators on
  Postgres.
- Not affected: applications that hardcode `fts_language`, don't use
  full-text search, or use a non-Postgres dialect.
- Upgrade recommended for all users of 1.2.x.

## [1.2.1] - 2026-07-27
### Security
- Fixed a SQL injection vulnerability affecting Postgres JSONB (`->>`) filter
  fields. A `field` value containing a single quote could break out of the
  generated string literal and inject arbitrary SQL into the WHERE clause.
  Also affected the `reverse_in` operator.
- Affected: any application using `filtersql` with Postgres and
  passing filter `field` values that aren't fully controlled by the developer
  (e.g. exposed via a REST API or generated from LLM output), where those
  filters target JSONB paths (`col->>key`).
- Not affected: filters that don't use JSONB paths, or any non-Postgres
  dialect (MySQL, SQLite, etc.).
- Upgrade recommended for all users of 1.2.

## [1.2] - 2026-07-26

### Security
- Moved `\x00` check to the start of `_quote()` to block JSONB bypasses.
- Fixed SQL injection risk when passing pre-quoted identifiers.

### Breaking Changes
- Removed default `icontains`. Filters now require an explicit `operator` key (raises `ValidationError`).

### Fixed
- `raw=True` now works in `having` clauses (bypasses quoting and JSONB parsing).
- `filtersql()` now reads `dbms`, `placeholder`, `raw_source`, and `scope` directly from the JSON payload.

### Added
- Auto-escapes `%`, `_`, `*`, `?`, and `[` in pattern searches (`contains`, `starts_with`, etc.).
- Added GitHub Actions workflow running `pytest` across Python 3.9–3.12.

## [1.1]
### Added
- DuckDB support in `DBMS_MAP`
- `group_by` and `having` parameters in `select()`
- DuckDB + Pandas example
- New operators support

### Fixed
- Operator validation and definitions
- `mysql` default placeholder updated to `%s`

## [1.0]
### Added
- Initial stable release
- Multi-DBMS support (PostgreSQL, SQLite, MySQL, Oracle)
- Cursor-based pagination (`cursor` + `direction`)
- Full-text search (PostgreSQL, MySQL)
- JSONB support with `value_type`
- Raw expressions with `raw=True`
- Column aliases with `alias`/`as`
- `scope` for multi-tenant filters
- `debug()` method for development
- `cursor` parameter in `select()`
- `columns` support as plain strings
- Security comments in `sql.py`
- `specs.md` with formal JSON specification

### Fixed
- Oracle pagination now uses `OFFSET FETCH`
- PostgreSQL pattern matching uses `chr(37)` for safety
- `raw=True` with `alias` now works correctly

### Security
- Parameterized queries by default
- Secure identifier quoting with escaping
- `raw_source` warning documented

### Changed
- Updated `README.md` with examples and documentation