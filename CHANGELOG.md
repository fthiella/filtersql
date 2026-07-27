# Changelog

All notable changes to this project will be documented in this file.

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