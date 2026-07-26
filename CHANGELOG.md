# Changelog

All notable changes to this project will be documented in this file.

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