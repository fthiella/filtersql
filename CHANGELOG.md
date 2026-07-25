# Changelog

All notable changes to this project will be documented in this file.

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