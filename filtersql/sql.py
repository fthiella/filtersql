# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import os
import unicodedata
import threading

DBMS_MAP = {
    'sqlite': {
        "placeholder":         '?',
        "quote":               '"',
        "search_map": {
            '=':                '{col} = {param}',
            '!=':               '{col} != {param}',
            '>':                '{col} > {param}',
            '>=':               '{col} >= {param}',
            '<':                '{col} < {param}',
            '<=':               '{col} <= {param}',
            # case sensitive
            'starts_with':      '{col} glob {param}',
            'ends_with':        '{col} glob {param}',
            'contains':         '{col} glob {param}',
            'not_starts_with':  '{col} not glob {param}',
            'not_ends_with':    '{col} not glob {param}',
            'not_contains':     '{col} not glob {param}',
            # case insensitive
            'istarts_with':     '{col} like {param}',
            'iends_with':       '{col} like {param}',
            'icontains':        '{col} like {param}',
            'not_istarts_with': '{col} not like {param}',
            'not_iends_with':   '{col} not like {param}',
            'not_icontains':    '{col} not like {param}',
            # other
            'in':               '{col} in ({params})',
            'notin':            '{col} not in ({params})',
            'null':             '{col} is null',
            'notnull':          '{col} is not null',
            'between':          '{col} between {param1} and {param2}',
            # SQLite's REGEXP has no case-insensitive mode; iregexp is an alias.
            'regexp':           '{col} regexp {param}',
            'iregexp':          '{col} regexp {param}',
            'not_regexp':       '{col} not regexp {param}',
            'not_iregexp':      '{col} not regexp {param}',
        },
        "limit":  'limit {start}, {length}',
        "like_escape": {"style": "backslash", "escape_char": "\\", "wildcards": ["%", "_"]},
        "glob_escape": {"style": "bracket", "wildcards": ["*", "?", "["]},
    },
    'pg': {
        "placeholder":         '%s',
        "quote":               '"',
        "search_map": {
            '=':                '{col} = {param}',
            '!=':               '{col} != {param}',
            '>':                '{col} > {param}',
            '>=':               '{col} >= {param}',
            '<':                '{col} < {param}',
            '<=':               '{col} <= {param}',
            # case sensitive
            'starts_with':      '{col} like {param}',
            'ends_with':        '{col} like {param}',
            'contains':         '{col} like {param}',
            'not_starts_with':  '{col} not like {param}',
            'not_ends_with':    '{col} not like {param}',
            'not_contains':     '{col} not like {param}',
            # case insensitive
            'istarts_with':     '{col} ilike {param}',
            'iends_with':       '{col} ilike {param}',
            'icontains':        '{col} ilike {param}',
            'not_istarts_with': '{col} not ilike {param}',
            'not_iends_with':   '{col} not ilike {param}',
            'not_icontains':    '{col} not ilike {param}',
            # vectors
            'fts':              "{col} @@ websearch_to_tsquery('{lang}', {param})",
            'fts_query':        "to_tsvector('{lang}', coalesce({col}, '')) @@ websearch_to_tsquery('{lang}', {param})",
            # other
            'in':               '{col} in ({params})',
            'notin':            '{col} not in ({params})',
            'null':             '{col} is null',
            'notnull':          '{col} is not null',
            'between':          '{col} between {param1} and {param2}',
            'regexp':           '{col} ~ {param}',
            'iregexp':          '{col} ~* {param}',
            'not_regexp':       '{col} !~ {param}',
            'not_iregexp':      '{col} !~* {param}'
        },
        "limit": 'limit {length} offset {start}',
        "like_escape": {"style": "backslash", "escape_char": "\\", "wildcards": ["%", "_"]},
    },
    'duckdb': {
        "placeholder":         '?',
        "quote":               '"',
        "search_map": {
            '=':                '{col} = {param}',
            '!=':               '{col} != {param}',
            '>':                '{col} > {param}',
            '>=':               '{col} >= {param}',
            '<':                '{col} < {param}',
            '<=':               '{col} <= {param}',
            # case sensitive
            'starts_with':      '{col} like {param}',
            'ends_with':        '{col} like {param}',
            'contains':         '{col} like {param}',
            'not_starts_with':  '{col} not like {param}',
            'not_ends_with':    '{col} not like {param}',
            'not_contains':     '{col} not like {param}',
            # case insensitive
            'istarts_with':     '{col} ilike {param}',
            'iends_with':       '{col} ilike {param}',
            'icontains':        '{col} ilike {param}',
            'not_istarts_with': '{col} not ilike {param}',
            'not_iends_with':   '{col} not ilike {param}',
            'not_icontains':    '{col} not ilike {param}',
            # other
            'in':               '{col} in ({params})',
            'notin':            '{col} not in ({params})',
            'null':             '{col} is null',
            'notnull':          '{col} is not null',
            'between':          '{col} between {param1} and {param2}',
            'regexp':           '{col} ~ {param}',
            'iregexp':          '{col} ~* {param}',
            'not_regexp':       '{col} !~ {param}',
            'not_iregexp':      '{col} !~* {param}'
        },
        "limit": 'limit {length} offset {start}',
        "like_escape": {"style": "backslash", "escape_char": "\\", "wildcards": ["%", "_"]},
    },
    'mysql': {
        "placeholder":         '%s',
        "quote":               '`',
        "search_map": {
            '=':                '{col} = {param}',
            '!=':               '{col} != {param}',
            '>':                '{col} > {param}',
            '>=':               '{col} >= {param}',
            '<':                '{col} < {param}',
            '<=':               '{col} <= {param}',
            # case sensitive (LIKE BINARY)
            'starts_with':      '{col} like binary {param}',
            'ends_with':        '{col} like binary {param}',
            'contains':         '{col} like binary {param}',
            'not_starts_with':  '{col} not like binary {param}',
            'not_ends_with':    '{col} not like binary {param}',
            'not_contains':     '{col} not like binary {param}',
            # case insensitive (standard LIKE)
            'istarts_with':     '{col} like {param}',
            'iends_with':       '{col} like {param}',
            'icontains':        '{col} like {param}',
            'not_istarts_with': '{col} not like {param}',
            'not_iends_with':   '{col} not like {param}',
            'not_icontains':    '{col} not like {param}',
            # full text search
            'fts':              "match({col}) against({param} in boolean mode)",
            'fts_query':        "match({col}) against({param} in boolean mode)",
            # other
            'in':               '{col} in ({params})',
            'notin':            '{col} not in ({params})',
            'null':             '{col} is null',
            'notnull':          '{col} is not null',
            'between':          '{col} between {param1} and {param2}',
            'regexp':           '{col} regexp binary {param}',
            'iregexp':          '{col} regexp {param}',
            'not_regexp':       '{col} not regexp binary {param}',
            'not_iregexp':      '{col} not regexp {param}',
        },
        "limit": 'limit {start}, {length}',
        "like_escape": {"style": "backslash", "escape_char": "\\", "wildcards": ["%", "_"]},
        "literal_backslash_escapes": True,
    },
    'oracle': {
        "placeholder":         ':{n}',
        "quote":               '"',
        "search_map": {
            '=':                '{col} = {param}',
            '!=':               '{col} != {param}',
            '>':                '{col} > {param}',
            '>=':               '{col} >= {param}',
            '<':                '{col} < {param}',
            '<=':               '{col} <= {param}',
            # case sensitive
            'starts_with':      '{col} like {param}',
            'ends_with':        '{col} like {param}',
            'contains':         '{col} like {param}',
            'not_starts_with':  '{col} not like {param}',
            'not_ends_with':    '{col} not like {param}',
            'not_contains':     '{col} not like {param}',
            # case insensitive - upper()
            'istarts_with':     'upper({col}) like upper({param})',
            'iends_with':       'upper({col}) like upper({param})',
            'icontains':        'upper({col}) like upper({param})',
            'not_istarts_with': 'upper({col}) not like upper({param})',
            'not_iends_with':   'upper({col}) not like upper({param})',
            'not_icontains':    'upper({col}) not like upper({param})',
            # other
            'in':               '{col} in ({params})',
            'notin':            '{col} not in ({params})',
            'null':             '{col} is null',
            'notnull':          '{col} is not null',
            'between':          '{col} between {param1} and {param2}',
            'regexp':           'regexp_like({col}, {param})',
            'iregexp':          'regexp_like({col}, {param}, \'i\')',
            'not_regexp':       'not regexp_like({col}, {param})',
            'not_iregexp':      'not regexp_like({col}, {param}, \'i\')',
        },
        "limit": 'offset {start} rows fetch next {length} rows only',
        "like_escape": {"style": "backslash", "escape_char": "\\", "wildcards": ["%", "_"]},
    }
}

DEFAULT_PAGE_LENGTH = 100
MAX_IN_LIST = 1000
MAX_LIMIT_LENGTH = 10_000
MAX_FILTER_DEPTH = 32

_DBMS_CASE_INSENSITIVE_LOOKUP = {k.lower(): k for k in DBMS_MAP}
_FORBIDDEN_IDENTIFIER_CHARS = frozenset('"`.\\')
_JSONB_OP_RE = re.compile(r'(->>|->)')

class FilterSQLError(Exception):
    """Base class for exceptions in this module."""
    pass

class InvalidIdentifierError(FilterSQLError):
    """Raised when a field name is invalid or potentially dangerous."""
    pass

class ValidationError(FilterSQLError):
    """Raised when user input is invalid (e.g., bad field name, bad types)."""
    pass

class ConfigurationError(FilterSQLError):
    """Raised when DBMS or source configuration is invalid."""
    pass

class Datasource:
    """
    Parameterized SQL from a filter AST (frontend, DataTables, LLM).

    Values are always bound. Identifiers go through _quote (reads) or
    _quote_write_target (insert/update/delete keys). Tenant `scope` is
    enforced server-side and cannot be set from the payload.

    `allowed_columns` is an exact allowlist of client identifiers.
    None keeps the old behaviour. A collection, even empty, is closed:
    columns, filters, order, cursors, group by and write keys must be
    listed verbatim (no case folding). Scope columns are injected after
    that check and do not have to be listed. SELECT * and raw are
    refused while the list is active.
    """

    # Operators whose SQL pattern embeds wildcard characters (%, _, *, ?) around
    # a user-supplied value. Any literal wildcard char inside that value must be
    # escaped, or it changes match semantics instead of being matched literally.
    _CASE_SENSITIVE_WILDCARD_OPS = frozenset({
        'starts_with', 'ends_with', 'contains',
        'not_starts_with', 'not_ends_with', 'not_contains',
    })
    _CASE_INSENSITIVE_WILDCARD_OPS = frozenset({
        'istarts_with', 'iends_with', 'icontains',
        'not_istarts_with', 'not_iends_with', 'not_icontains',
    })
    _WILDCARD_OPS = _CASE_SENSITIVE_WILDCARD_OPS | _CASE_INSENSITIVE_WILDCARD_OPS

    _PG_ALLOWED_CAST_TYPES = frozenset({
        'numeric', 'integer', 'bigint', 'real', 'double precision',
        'date', 'timestamp', 'timestamptz', 'time',
        'boolean', 'uuid'
    })

    def __init__(
        self,
        *,
        dbms: str = None,
        source: str = None,
        raw_source: bool = False,
        allow_raw_source: bool = False,
        allow_raw_fields: bool = False,
        allowed_columns: set = None,
        allowed_sources: set = None,
        order: list = None,
        limit: dict = None,
        scope: dict = None,
        direction: str = None,
        placeholder: str = None,
        fts_language: str = None,
    ):
        """
        Datasource initialization
        """
        # Case-insensitive dbms: 'pg', 'PG', 'Pg' all resolve to the same
        # canonical key. Only casing is normalized here - unrecognized
        # names (typos, aliases like 'postgres') are left as-is and will
        # correctly fail the DBMS_MAP membership check right below, with
        # the original value quoted back in the error message.
        if isinstance(dbms, str):
            dbms = _DBMS_CASE_INSENSITIVE_LOOKUP.get(dbms.strip().lower(), dbms)
        self.dbms             = dbms
        self.allow_raw_source = allow_raw_source
        self.allow_raw_fields = allow_raw_fields

        if not self.dbms or self.dbms not in DBMS_MAP:
            raise ConfigurationError(
                f"Unknown or missing dbms: '{self.dbms}'. Valid: {list(DBMS_MAP.keys())}"
            )

        self.source          = source
        self.raw_source      = raw_source
        self.order           = order or []
        self.limit           = limit

        if scope is not None:
            if not isinstance(scope, dict):
                raise ConfigurationError(f"Expected dict for 'scope', got {type(scope).__name__}")
            for k in scope:
                self._validate_bare_identifier(k)
        self.scope = scope or {}

        self.allowed_columns = self._normalize_allowlist(allowed_columns, 'allowed_columns')
        self.allowed_sources = self._normalize_allowlist(allowed_sources, 'allowed_sources')

        self.direction       = direction
        self.fts_language    = fts_language or 'english'

        self.placeholder = placeholder or DBMS_MAP[self.dbms]["placeholder"]

        if self.placeholder.count('{n}') > 1 or (
            '{n}' not in self.placeholder
            and ('{' in self.placeholder or '}' in self.placeholder)
        ):
            raise ConfigurationError("placeholder may contain '{n}' at most once and no other braces.")
        self._numbered = '{n}' in self.placeholder
        if self._numbered:
            self._bind_prefix, self._bind_suffix = self.placeholder.split('{n}')

        # Per-thread bind counter. Set to a fresh value at the top of every
        # query build (see _begin_binds). Using threading.local instead of an
        # instance attribute because a Datasource is routinely constructed once
        # and shared across threads (module-level object in a web server); the
        # bind numbering must be isolated per concurrent build, or two threads
        # interleave :1, :2, :3 and produce corrupted SQL.
        self._local = threading.local()

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('_local', None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._local = threading.local()

    def _begin_binds(self) -> None:
        self._local.n = 0 if self._numbered else None

    def _ph(self) -> str:
        if self._local.n is None:
            return self.placeholder
        self._local.n += 1
        return f"{self._bind_prefix}{self._local.n}{self._bind_suffix}"

    def select(
        self,
        *,
        columns: list = None,
        filters: list = None,
        group_by: list = None,
        having: list = None,
        order: list = None,
        limit: dict = None,
        direction: str = None,
        cursor: dict = None
    ) -> tuple[str, list]:
        """
        Build a SELECT query. Pass columns, filters, order, limit explicitly.
        """
        self._begin_binds()
        active_order = self._validate_order(order if order is not None else self.order)

        if filters is not None and not isinstance(filters, list):
            raise ValidationError(
                f"Expected list for 'filters', got {type(filters).__name__}: {filters!r}"
            )
        filters = list(filters) if filters else []

        if columns is None:
            columns = []
        if not isinstance(columns, list):
            raise ValidationError("Expected list as 'columns'.")

        if group_by is not None and not isinstance(group_by, list):
            raise ValidationError("Expected list as 'group_by'")

        if having is not None and not isinstance(having, list):
            raise ValidationError("Expected list as 'having'")

        quote_char = DBMS_MAP[self.dbms]['quote']
        delim = ','

        parsed_columns = []
        for x in columns:
            if isinstance(x, str):
                # Simple column name
                self._check_allowed_column(x)
                parsed_columns.append(self._quote(x, quote_char))
            elif isinstance(x, dict):
                field = x.get('field')
                if not field:
                    raise ValidationError(f"Column dict missing 'field': {x}")

                if x.get('raw', False):
                    if self.allowed_columns is not None:
                        raise ValidationError(
                            "raw columns are not permitted when allowed_columns is set."
                        )
                    if not self.allow_raw_fields:
                        raise ConfigurationError(
                            "raw columns/filters are disabled. Set allow_raw_fields=True to enable."
                        )
                    raw_sql = str(field)
                    alias = x.get('alias') or x.get('as')
                    if alias:
                        raw_sql += f" as {self._quote_write_target(alias, quote_char)}"
                    parsed_columns.append(raw_sql)
                else:
                    self._check_allowed_column(field)
                    quoted = self._quote(field, quote_char)
                    alias = x.get('alias') or x.get('as')
                    if alias:
                        quoted += f" as {self._quote_write_target(alias, quote_char)}"
                    parsed_columns.append(quoted)
            else:
                raise ValidationError(f"Invalid column format: {x}")

        if self.allowed_columns is not None and not parsed_columns:
            raise ValidationError(
                "columns must be specified explicitly when allowed_columns is set "
                "(SELECT * is not allowed)."
            )

        active_direction = direction or self.direction
        where_clause, where_values = self.where(filters=filters, direction=active_direction, cursor=cursor, order=active_order, _continue=True)

        having_clause = ""
        having_values = []
        if having:
            having_clause, having_values = self.having(filters=having, _continue=True)
        
        values = where_values + having_values

        parsed_order = [
            self._quote(x['field'], quote_char)
            + " "
            + self._invert_order(x.get('order') or 'asc', active_direction == 'prev')
            for x in active_order
        ]

        active_limit = limit if limit is not None else self.limit
        limit = ""
        if active_limit is not None:
            if not isinstance(active_limit, dict):
                raise ValidationError(f"Expected dict for 'limit', got {type(active_limit).__name__}")
            limit = self._build_limit(
                dbms=self.dbms, 
                start=active_limit.get("start"), 
                length=active_limit.get("length")
            )

        segments = []
        segments.append(f"select")
        if parsed_columns:
            segments.append(f"{delim}\n".join(f"  {c}" for c in parsed_columns))
        else:
            segments.append("  *")

        segments.extend([
            "from",
            f"  {self._resolve_source()}"
        ])

        if where_clause:
            segments.extend([
                "where",
                f"  {where_clause}"
            ])

        if group_by:
            for col in group_by:
                self._check_allowed_column(col)
            segments.extend([
                "group by",
                f"  " + ", ".join(self._quote(col, quote_char) for col in group_by)
            ])

        if having_clause:
            segments.extend([
                "having",
                f"  {having_clause}"
            ])

        if parsed_order:
            segments.extend([
                "order by",
                "  " + (delim + "\n  ").join(parsed_order)
            ])

        if limit:
            segments.append(limit)

        return "\n".join(segments) + "\n", values

    def insert(self, *, values: dict = None, returning: str = None) -> tuple[str, list]:
        """Build an INSERT statement. Requires values dict, optional returning field."""

        if not values and not self.scope:
            raise ValidationError("insert() requires at least one value")

        if returning and self.dbms not in ('pg', 'sqlite', 'duckdb'):
            raise ValidationError(f"returning is not supported by {self.dbms}")

        if values and not isinstance(values, dict):
            raise ValidationError("Expected a dictionary for 'values'")

        # Reject explicit values for any scope-enforced column BEFORE
        # merging scope in. Comparison is case-insensitive and runs only
        # after each key is confirmed to be a bare identifier (see
        # _quote_write_target below) - so 'users.tenant_id' or
        # '`users`.`tenant_id`' (MySQL accepts a table-qualified column
        # on the SET side of an UPDATE) is rejected as malformed before
        # it ever reaches this comparison, rather than needing to be
        # recognized as an alias for 'tenant_id' by it.
        if values:
            for k in values:
                self._validate_bare_identifier(k)
                self._check_allowed_column(k)
            self._check_scope_collision(values.keys())

        self._begin_binds()

        final_values = {**(values or {}), **self.scope}

        source = self._resolve_source()
        quote_char = DBMS_MAP[self.dbms]['quote']

        fields = []
        set_values = []
        placeholders = []

        for k, v in final_values.items():
            fields.append(self._quote_write_target(k, quote_char))
            placeholders.append(self._ph())
            set_values.append(v)

        segments = [
            f"insert into {source}",
            "  (" + ", ".join(fields) + ")",
            "values",
            "  (" + ", ".join(placeholders) + ")"
        ]

        if returning:
            self._check_allowed_column(returning)
            ret_col = self._quote(returning, quote_char)
            segments.append(f"returning {ret_col}")

        return "\n".join(segments), set_values

    def update(self, *, id: dict, values: dict) -> tuple[str, list]:
        """Build an UPDATE statement. Requires id dict and values dict."""
        if not id:
            raise ValidationError("update() requires at least one id field")
        if not values:
            raise ValidationError("update() requires at least one value to update")

        if not isinstance(id, dict):
            raise ValidationError("The 'id' parameter must be a dictionary.")
        if not isinstance(values, dict):
            raise ValidationError("The 'values' parameter must be a dictionary.")

        for k in values:
            self._validate_bare_identifier(k)
            self._check_allowed_column(k)
        self._check_scope_collision(values.keys())

        # 'id' identifies the row(s) to update on this same single table -
        # same reasoning as 'values': no legitimate reason to qualify it,
        # and allowing qualification here would let a scoped column be
        # reintroduced into the WHERE clause under a different spelling.
        for k in id:
            self._validate_bare_identifier(k)
            self._check_allowed_column(k)
        self._check_scope_collision(id.keys())

        self._begin_binds()
        source = self._resolve_source()
        quote_char = DBMS_MAP[self.dbms]['quote']

        set_parts = []
        set_values = []

        for k, v in values.items():
            set_parts.append(f"{self._quote_write_target(k, quote_char)} = {self._ph()}")
            set_values.append(v)

        my_filters = [{'field': k, 'operator': '=', 'value': v} for k, v in id.items()]

        where_clause, where_values = self.where(filters=my_filters, _continue=True)

        segments = [
            "update",
            f"  {source}",
            "set",
            "  " + ",\n  ".join(set_parts)
        ]

        if where_clause:
            segments.extend([
                "where",
                f"  {where_clause}"
            ])

        return "\n".join(segments), set_values + where_values

    def delete(self, *, id: dict) -> tuple[str, list]:
        """Build a DELETE statement. Requires id dict."""
        if not id:
            raise ValidationError("delete() requires at least one id field")
        if not isinstance(id, dict):
            raise ValidationError("The 'id' parameter must be a dictionary.")

        for k in id:
            self._validate_bare_identifier(k)
            self._check_allowed_column(k)
        self._check_scope_collision(id.keys())

        self._begin_binds()
        my_filters = [{'field': k, 'operator': '=', 'value': v} for k, v in id.items()]

        source = self._resolve_source()
        where_clause, where_values = self.where(filters=my_filters, _continue=True)

        segments = [
            "delete from",
            f"  {source}"
        ]

        if where_clause:
            segments.extend([
                "where",
                f"  {where_clause}"
            ])

        return "\n".join(segments), where_values

    def debug(self, query: str, values: list) -> str:
        """
        Returns query with placeholders replaced by actual values
        WARNING: This method outputs raw SQL with interpolated values.
        Only use for debugging in development environments.
        """
        if not os.getenv('FILTERSQL_DEBUG', '').lower() in ('1', 'true', 'yes', 'on'):
            raise RuntimeError(
                "debug() is disabled. Set FILTERSQL_DEBUG=1 to enable it. "
                "Never use this in production."
            )

        parts = self._split_binds(query)
        if parts is None or len(parts) - 1 != len(values):
            return query

        def _format(val):
            if isinstance(val, str):
                return "'" + val.replace("'", "''") + "'"
            if val is None:
                return "null"
            return str(val)

        out = [parts[0]]
        for val, tail in zip(values, parts[1:]):
            out.append(_format(val))
            out.append(tail)
        return ''.join(out)

    def _split_binds(self, query: str) -> list | None:
        """
        Split query on bind markers, ignoring text inside quotes.
        Handles both fixed placeholders (?, %s) and numbered ones (:{n}).
        """
        if self._numbered:
            pattern = re.compile(
                re.escape(self._bind_prefix) + r'(\d+)' + re.escape(self._bind_suffix)
            )
        else:
            pattern = re.compile(re.escape(self.placeholder))

        parts = []
        buf = []
        i = 0
        n = len(query)
        expected = 1
        quote = None

        while i < n:
            ch = query[i]
            if quote is not None:
                buf.append(ch)
                if ch == quote:
                    if i + 1 < n and query[i + 1] == quote:
                        buf.append(query[i + 1])
                        i += 2
                        continue
                    quote = None
                i += 1
                continue
            if ch in ("'", '"', '`'):
                buf.append(ch)
                quote = ch
                i += 1
                continue

            match = pattern.match(query, i)
            if self._numbered:
                ok = match and int(match.group(1)) == expected
            else:
                ok = bool(match)

            if ok:
                parts.append(''.join(buf))
                buf = []
                if self._numbered:
                    expected += 1
                i = match.end()
                continue

            buf.append(ch)
            i += 1

        parts.append(''.join(buf))
        if self._numbered and expected - 1 != len(parts) - 1:
            return None
        return parts

    def _validate_order(self, order_list: list | None) -> list:
        if order_list is None:
            return []
        if not isinstance(order_list, list):
            raise ValidationError(f"Expected list for 'order', got {type(order_list).__name__}")
        seen = set()
        for item in order_list:
            if not isinstance(item, dict) or not item.get('field'):
                raise ValidationError(f"Each item in 'order' must be a dict with a 'field' key: {item!r}")
            field = item['field']
            if field in seen:
                raise ValidationError(
                    f"Duplicate field {field!r} in 'order'. "
                    f"Each column may appear only once."
                )
            seen.add(field)
            self._check_allowed_column(field)
        return order_list

    def where(self, *, filters: list = None, direction: str = None, cursor: dict = None, order: list = None, _continue: bool = False) -> tuple[str, list]:
        """Build a WHERE clause from filters and cursor. Returns (clause, values)."""
        if not _continue:
            self._begin_binds()
        active_direction = direction or self.direction
        active_order = self._validate_order(order if order is not None else self.order)

        if filters is not None and not isinstance(filters, list):
            raise ValidationError(
                f"Expected list for 'filters', got {type(filters).__name__}: {filters!r}"
            )

        if cursor is not None and not isinstance(cursor, dict):
            raise ValidationError(
                f"Invalid cursor format. Expected dict, got: {type(cursor).__name__}"
            )

        if active_direction is not None and active_direction not in ('seek', 'next', 'prev'):
            raise ValidationError(
                f"Invalid direction '{active_direction}'. Please use: seek, next, prev."
            )

        if cursor:
            if not active_direction:
                raise ValidationError(
                    "A 'direction' ('seek', 'next', 'prev') must be provided "
                    "when using a 'cursor'."
                )
            for k, v in cursor.items():
                if v is None:
                    raise ValidationError(
                        f"Cursor value for field {k!r} cannot be None. "
                        f"Use a 'null'/'notnull' filter for NULL tests."
                    )
                if isinstance(v, (list, tuple, dict, set, frozenset)):
                    raise ValidationError(
                        f"Cursor value for field {k!r} must be a scalar, "
                        f"got {type(v).__name__}."
                    )

        if cursor and active_direction in ('next', 'prev'):
            if not active_order:
                raise ValidationError(
                    f"Keyset pagination ('{active_direction}') requires an 'order' configuration."
                )

            order_fields = [o['field'] for o in active_order]
            order_field_set = set(order_fields)

            extra = [k for k in cursor if k not in order_field_set]
            if extra:
                raise ValidationError(
                    f"Cursor field(s) {extra} must be present in 'order' for keyset pagination."
                )

            missing = [f for f in order_fields if f not in cursor]
            if missing:
                raise ValidationError(
                    f"Cursor is missing required order field(s): {missing}"
                )

        scope_filters = [{'field': k, 'operator': '=', 'value': v} for k, v in self.scope.items()]
        # Client filters only. Scope is server-owned and is not part of
        # the allowlist, otherwise a tenant key would have to be listed
        # and the client could name it too.
        self._check_allowed_filters(filters)
        all_filters = scope_filters + list(filters or [])

        if all_filters or cursor:
            return self._build_where(filters=all_filters, direction=active_direction, cursor=cursor, order=active_order)
        return "", []

    def having(self, *, filters: list = None, _continue: bool = False) -> tuple[str, list]:
        """
        Build HAVING clause. Same logic as WHERE but for GROUP BY.
        """
        if filters is not None and not isinstance(filters, list):
            raise ValidationError(
                f"Expected list for 'filters', got {type(filters).__name__}: {filters!r}"
            )

        if not filters:
            return "", []

        if not _continue:
            self._begin_binds()

        self._check_allowed_filters(filters)
        return self._build_filter_group(filters, join='and')

    def _build_where(self, *, filters: list, direction: str, cursor: dict = None, order: list = None) -> tuple[str, list]:
        """Build a WHERE clause from filters. Returns (clause, values)."""

        for item in filters:
            if not isinstance(item, dict):
                raise ValidationError(f"Invalid filter format. Expected dict, got: {type(item).__name__} ({item})")

        m_where = []
        m_data = []

        if cursor and direction:
            quote = DBMS_MAP[self.dbms]['quote']

            order_map = {
                o['field']: o.get('order', 'asc')
                for o in (order or [])
            }

            if direction == 'seek':
                conditions = []
                for k, v in cursor.items():
                    self._check_allowed_column(k)
                    conditions.append(
                        f"{self._quote(k, quote)} = {self._ph()}"
                    )
                    m_data.append(v)
                m_where.append(' and '.join(conditions))
            else:
                # Proper multi-column keyset with per-column ASC/DESC awareness
                cursor_items = [
                    (o['field'], cursor[o['field']])
                    for o in (order or [])
                ]

                or_conditions = []
                for i in reversed(range(len(cursor_items))):
                    and_parts = []

                    # equality on the more-significant columns
                    for j in range(i):
                        k, v = cursor_items[j]
                        and_parts.append(
                            f"{self._quote(k, quote)} = {self._ph()}"
                        )
                        m_data.append(v)

                    # inequality on the current column
                    k, v = cursor_items[i]
                    col_order = order_map.get(k, 'asc')
                    op = self._cursor_operator(direction, col_order)
                    and_parts.append(
                        f"{self._quote(k, quote)} {op} {self._ph()}"
                    )
                    m_data.append(v)

                    or_conditions.append('(' + ' and '.join(and_parts) + ')')
                m_where.append(' or '.join(or_conditions))

        s_sql, s_data = self._build_filter_group(filters, join='and')

        q_where = []
        if m_where:
            q_where.append('(' + ' and '.join(m_where) + ')')
        if s_sql:
            q_where.append('(' + s_sql + ')')

        return ' and '.join(q_where), m_data + s_data

    def _build_filter_group(self, filters: list, join: str = 'and', _depth: int = 0) -> tuple:
        if _depth > MAX_FILTER_DEPTH:
            raise ValidationError(
                f"Filter groups nested deeper than {MAX_FILTER_DEPTH}."
            )

        parts = []
        values = []

        for item in filters:
            if not isinstance(item, dict):
                raise ValidationError(f"Invalid filter. dict expected, got: {type(item).__name__} ({item})")

            group_keys = [k for k in ('or', 'and', 'not') if k in item]
            if group_keys:
                if len(item) != 1:
                    raise ValidationError(
                        f"Filter group dict must contain only a single group key ('and', 'or', 'not'), got keys: {list(item.keys())}"
                    )
                gkey = group_keys[0]
                if gkey in ('or', 'and'):
                    if not isinstance(item[gkey], list):
                        raise ValidationError(f"Expected list for '{gkey}' group, got {type(item[gkey]).__name__}")
                    sub_sql, sub_vals = self._build_filter_group(item[gkey], join=gkey, _depth=_depth + 1)
                    if sub_sql:
                        parts.append('(' + sub_sql + ')')
                        values.extend(sub_vals)
                else:  # 'not'
                    not_content = item['not']
                    if isinstance(not_content, dict):
                        sub_filters = [not_content]
                    elif isinstance(not_content, list):
                        sub_filters = not_content
                    else:
                        raise ValidationError(f"Expected dict or list for 'not' group, got {type(not_content).__name__}")
                    sub_sql, sub_vals = self._build_filter_group(sub_filters, join='and', _depth=_depth + 1)
                    if sub_sql:
                        parts.append('not (' + sub_sql + ')')
                        values.extend(sub_vals)
            else:
                sql_frag, vals = self._build_condition_sql(item)
                parts.append(sql_frag)
                values.extend(vals)

        joiner = f' {join} '
        return joiner.join(parts), values

    def _build_condition_sql(self, f: dict) -> tuple:
        """
        Builds SQL fragment and values for a single filter dict.
        Returns (sql_fragment, values_list).
        """
        field    = f.get('field')
        operator = f.get('operator')

        if not operator:
            raise ValidationError(f"Filter is missing required 'operator' key: {f}")
        if not field:
            raise ValidationError(f"Filter is missing required 'field' key: {f}")

        kind, values = self._normalize_filter_value(operator, f.get('value'))

        sql_frag = self._build_condition(
            col=field,
            searchcriteria=operator,
            kind=kind,
            values=values,
            value_type=f.get('value_type'),
            raw=f.get('raw', False),
        )
        return sql_frag, values

    def _normalize_filter_value(self, operator: str, value) -> tuple[str, list]:
        """
        Returns (kind, values), where kind is one of:

          'none'    : operator takes no bind value (null / notnull); values == []
          'scalar'  : operator takes exactly one scalar; values has len 1
          'list'    : in / notin with a non-empty list; values has len N
          'empty'   : in / notin with an empty list; values == []
          'between' : between with exactly two scalars; values has len 2

        Values are returned ready to bind: wildcard escaping for pattern
        operators is applied here, so _build_condition_sql can return them
        unchanged and _build_condition only needs the count to emit the right
        number of placeholders.

        Single source of truth for "is this filter's value valid, and what
        shape does it have". Both consumers (WHERE and HAVING, via
        _build_filter_group -> _build_condition_sql) go through here, so a
        fix for one operator can no longer land in only one of the two paths
        (the failure mode behind the 1.2.4 in/notin empty-list bug).
        """
        if operator in ('null', 'notnull'):
            return 'none', []

        if operator in ('in', 'notin'):
            if isinstance(value, (dict, set, frozenset)):
                raise ValidationError(
                    f"Operator '{operator}' expects a scalar or a list, "
                    f"got {type(value).__name__}."
                )
            if value is None:
                raise ValidationError(
                    f"Operator '{operator}' does not accept None. "
                    f"Use 'null' or 'notnull' to test for null."
                )
            values = list(value) if isinstance(value, (list, tuple)) else [value]

            for v in values:
                if v is None:
                    raise ValidationError(
                        f"Operator '{operator}' does not accept None. "
                        f"Use 'null' or 'notnull' to test for null."
                    )
                if isinstance(v, (list, tuple, dict, set, frozenset)):
                    raise ValidationError(
                        f"Operator '{operator}' expects scalar values, "
                        f"got {type(v).__name__}."
                    )

            if not values:
                return 'empty', []
            if len(values) > MAX_IN_LIST:
                raise ValidationError(
                    f"'{operator}' accepts at most {MAX_IN_LIST} values, "
                    f"got {len(values)}."
                )
            return 'list', values

        if operator == 'between':
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValidationError(
                    f"'between' operator requires a list of two values, "
                    f"got: {value!r}"
                )
            for v in value:
                if v is None:
                    raise ValidationError(
                        "Operator 'between' does not accept None. "
                        "Use 'null' or 'notnull' to test for null."
                    )
                if isinstance(v, (list, tuple, dict, set, frozenset)):
                    raise ValidationError(
                        f"Operator 'between' expects scalar values, "
                        f"got {type(v).__name__}."
                    )
            return 'between', list(value)

        # Scalar operators (=, !=, >, contains, regexp, fts, …)
        if value is None:
            raise ValidationError(
                f"Operator '{operator}' does not accept None. "
                f"Use 'null' or 'notnull' to test for null."
            )
        if isinstance(value, (list, tuple, dict, set, frozenset)):
            raise ValidationError(
                f"Operator '{operator}' expects a single scalar value, "
                f"got {type(value).__name__}: {value!r}"
            )

        if operator in self._WILDCARD_OPS:
            value = self._escape_wildcard_value(value, operator)

        return 'scalar', [value]

    def _build_condition(
        self,
        col: str,
        searchcriteria: str,
        kind: str,
        values: list,
        value_type: str | None = None,
        raw: bool = False,
    ) -> str:
        if raw and self.allowed_columns is not None:
            raise ValidationError(
                "raw filters are not permitted when allowed_columns is set."
            )
        if raw and not self.allow_raw_fields:
            raise ConfigurationError(
                "raw columns/filters are disabled. Set allow_raw_fields=True to enable."
            )

        if searchcriteria in ('fts', 'fts_query') and self.dbms not in ('pg', 'mysql'):
            raise ValidationError(f"FTS operator not supported for {self.dbms}")

        if searchcriteria not in DBMS_MAP[self.dbms]["search_map"]:
            valid = list(DBMS_MAP[self.dbms]['search_map'].keys())
            raise ValidationError(
                f"Operator '{searchcriteria}' not valid for {self.dbms}. Valid: {valid}"
            )

        raw_statement = DBMS_MAP[self.dbms]["search_map"][searchcriteria]
        quote_char = DBMS_MAP[self.dbms]["quote"]

        cast_suffix = ''
        if raw:
            col_expr = str(col)
        else:
            col_expr = self._quote(col, quote_char)
            if (
                self.dbms == 'pg'
                and value_type
                and str(value_type).strip().lower() not in ('text',)
            ):
                _, path = self._parse_jsonb_path(col)
                if path:
                    cast_type = value_type.strip().lower()
                    if cast_type not in self._PG_ALLOWED_CAST_TYPES:
                        raise ValidationError(
                            f"Invalid value_type '{value_type}' for JSONB path. "
                            f"Allowed: {sorted(list(self._PG_ALLOWED_CAST_TYPES))}"
                        )
                    col_expr = f"({col_expr})::{cast_type}"
                    cast_suffix = f"::{cast_type}"

        def marker() -> str:
            return self._ph() + cast_suffix

        if kind == 'none':
            return raw_statement.format(col=col_expr)

        if kind == 'empty':
            return "1 = 0" if searchcriteria == 'in' else "1 = 1"

        if kind == 'list':
            placeholders_str = ", ".join(marker() for _ in values)
            return raw_statement.format(col=col_expr, params=placeholders_str)

        if kind == 'between':
            return raw_statement.format(
                col=col_expr, param1=marker(), param2=marker()
            )

        # kind == 'scalar'
        rendered = raw_statement.format(
            col=col_expr,
            param=marker() if '{param}' in raw_statement else '',
            lang=self._safe_sql_literal(self.fts_language),
        )
        rendered += self._wildcard_escape_clause(searchcriteria)
        return rendered

    def _wildcard_escape_config(self, operator: str) -> dict:
        """
        Returns the escape config (style/char/wildcards) that applies to this
        operator for the current dialect, or None if the operator isn't a
        wildcard-pattern operator.

        SQLite is the one dialect that splits wildcard operators across two
        different matching engines (GLOB for case-sensitive, LIKE for
        case-insensitive), so it needs its own branch; every other dialect
        uses LIKE/ILIKE for all of them.
        """
        if operator not in self._WILDCARD_OPS:
            return None
        dialect_cfg = DBMS_MAP[self.dbms]
        if self.dbms == 'sqlite' and operator in self._CASE_SENSITIVE_WILDCARD_OPS:
            return dialect_cfg.get('glob_escape')
        return dialect_cfg.get('like_escape')

    def _escape_wildcard_value(self, value, operator: str):
        """
        Escapes literal wildcard characters in a user-supplied value,
        then wraps the value in the appropriate wildcard markers (%, *) 
        for the given operator.
        """
        if value is None or operator not in self._WILDCARD_OPS:
            return value

        cfg = self._wildcard_escape_config(operator)
        escaped_value = str(value)

        if cfg:
            wildcard_set = set(cfg['wildcards'])
            if cfg['style'] == 'backslash':
                esc = cfg['escape_char']
                out = []
                for ch in escaped_value:
                    if ch == esc or ch in wildcard_set:
                        out.append(esc)
                    out.append(ch)
                escaped_value = ''.join(out)
            elif cfg['style'] == 'bracket':
                # GLOB-style: wrapping a metacharacter in brackets
                out = []
                for ch in escaped_value:
                    out.append(f'[{ch}]' if ch in wildcard_set else ch)
                escaped_value = ''.join(out)

        is_glob = (self.dbms == 'sqlite' and operator in self._CASE_SENSITIVE_WILDCARD_OPS)
        wc = '*' if is_glob else '%'

        if operator in {'starts_with', 'istarts_with', 'not_starts_with', 'not_istarts_with'}:
            return f"{escaped_value}{wc}"
        elif operator in {'ends_with', 'iends_with', 'not_ends_with', 'not_iends_with'}:
            return f"{wc}{escaped_value}"
        elif operator in {'contains', 'icontains', 'not_contains', 'not_icontains'}:
            return f"{wc}{escaped_value}{wc}"

        return escaped_value

    def _wildcard_escape_clause(self, operator: str) -> str:
        """
        Returns the SQL suffix needed to declare the escape character used
        above (e.g. " escape '\\'"), or '' if none is needed for this
        operator/dialect (GLOB doesn't use an ESCAPE clause at all).
        """
        cfg = self._wildcard_escape_config(operator)
        if not cfg or cfg['style'] != 'backslash':
            return ''
        # Route through _safe_sql_literal rather than interpolating
        # cfg['escape_char'] directly - it needs the same dialect-aware
        # backslash-doubling as any other literal spliced into MySQL SQL
        # text (see _safe_sql_literal docstring).
        return f" escape '{self._safe_sql_literal(cfg['escape_char'])}'"

    def _safe_sql_literal(self, raw_value: str) -> str:
        """
        Sanitizes a string before it is embedded directly inside a
        single-quoted SQL string literal (i.e. NOT as a bound parameter).

        Used anywhere a value has to be spliced into the SQL text itself
        rather than passed as a placeholder - e.g. a JSONB key extracted
        from a '->>' path expression, or a full-text-search language name
        embedded in websearch_to_tsquery('{lang}', ...).

        Escapes any embedded single quote by doubling it (standard SQL
        string literal escaping). Without this, a value such as
        "amount' or '1'='1" would break out of the surrounding '...'
        literal and inject arbitrary SQL.

        On dialects where backslash is itself a string-literal escape
        character (MySQL, unless NO_BACKSLASH_ESCAPES is set), embedded
        backslashes are doubled too - otherwise a value ending in a
        backslash escapes the closing quote instead of terminating the
        literal, leaving the rest of the query concatenated into the
        string (a syntax error at best, a smuggling vector at worst).

        Deliberately does NOT trim whitespace or strip quote characters -
        either could be meaningful, real content (e.g. a JSONB key that
        legitimately has a trailing space, common in data imported from
        spreadsheets/CSVs) and this function has no way to distinguish
        that from incidental formatting. Cosmetic whitespace around the
        '->>' operator is trimmed at the parsing site instead, before
        this function ever sees the value.
        """
        value = str(raw_value)
        if '\x00' in value:
            raise ValidationError("SQL literal contains null byte.")
        if DBMS_MAP[self.dbms].get('literal_backslash_escapes'):
            value = value.replace('\\', '\\\\')
        return value.replace("'", "''")

    # Kept as an alias: _safe_jsonb_key was the original, narrower name for
    # this helper before it was generalized to cover fts_language too.
    _safe_jsonb_key = _safe_sql_literal

    @staticmethod
    def _validate_bare_identifier(name: str) -> str:
        """
        Requires `name` to be a single bare identifier suitable as a
        write target (values/id keys).

        Accepted: letters (ASCII and non-ASCII), digits, underscore, and
        spaces between characters. So "quantità", "qta totale", and
        "n° fattura" are all valid - there is no reason to reject a
        character that SQL can quote safely.

        Rejected: characters that would break identifier quoting (`"`,
        backtick, backslash), change the structural meaning of the string
        (dot = schema qualification, -> and ->> = JSONB path), introduce
        invisible ambiguity (control characters), or appear as leading/
        trailing whitespace (the signature of the collision-check bypass
        this method exists to close).

        The returned value is the NFC canonical form. Callers must use
        the return value, not the original, when constructing SQL -
        otherwise a caller could pass an NFC key for validation and an
        NFD key for execution, hitting a different column on byte-exact
        dialects.
        """
        if not isinstance(name, str) or not name:
            raise InvalidIdentifierError("Identifier cannot be empty.")

        canonical = unicodedata.normalize('NFC', name)
        if canonical != name:
            raise InvalidIdentifierError(
                f"Column name {name!r} is not in Unicode NFC form. "
                f"Normalize it to {canonical!r} before using it as a "
                f"write-target key."
            )

        if name != name.strip():
            raise InvalidIdentifierError(
                f"Column name {name!r} has leading or trailing whitespace. "
                f"filtersql does not strip identifiers, so this would be "
                f"treated as a column literally named {name!r}. Remove the "
                f"whitespace if it was accidental."
            )

        for ch in name:
            if ch in _FORBIDDEN_IDENTIFIER_CHARS:
                raise InvalidIdentifierError(
                    f"Column name {name!r} contains forbidden character "
                    f"{ch!r}. Write-target keys may not contain quotes, "
                    f"backslash, or dot."
                )
            if unicodedata.category(ch).startswith('C'):
                raise InvalidIdentifierError(
                    f"Column name {name!r} contains a control character."
                )

        if '->' in name:
            raise InvalidIdentifierError(
                f"Column name {name!r} contains a JSONB path operator. "
                f"Use `filters` in select() for JSONB filtering."
            )

        return canonical

    @staticmethod
    def _normalize_allowlist(value, name: str):
        """Validates an allowlist argument and returns it as a frozenset (or None)."""
        if value is None:
            return None
        if not isinstance(value, (set, frozenset, list, tuple)):
            raise ConfigurationError(
                f"Expected set/list/tuple for '{name}', got {type(value).__name__}"
            )
        if not all(isinstance(c, str) and c for c in value):
            raise ConfigurationError(f"'{name}' entries must be non-empty strings")
        return frozenset(value)

    def _check_allowed_source(self) -> None:
        """
        Raises if `allowed_sources` is set and the configured source is not in it.
        Exact string match (no case folding, no schema inference): list
        'public.users' if that is what the payload sends. Applies to raw
        sources too, where the whole source string must be listed.
        """
        if self.allowed_sources is None:
            return
        if self.source not in self.allowed_sources:
            raise ValidationError(
                f"Source {self.source!r} is not in allowed_sources."
            )

    def _check_allowed_column(self, name: str) -> None:
        """
        Raises if `allowed_columns` is set and `name` is not in it.

        Match is exact, after no normalization. Case folding would treat
        "Email" and "email" as the same column, and on Postgres they are
        not. Dialects that fold unquoted names still reject a spelling
        that was not listed.
        """
        if self.allowed_columns is None:
            return
        if name not in self.allowed_columns:
            raise ValidationError(
                f"Column {name!r} is not in allowed_columns."
            )

    def _check_allowed_filters(self, filters, _depth: int = 0) -> None:
        if self.allowed_columns is None or not filters:
            return
        if _depth > MAX_FILTER_DEPTH:
            raise ValidationError(
                f"Filter groups nested deeper than {MAX_FILTER_DEPTH}."
            )
        for item in filters:
            if not isinstance(item, dict):
                continue
            if 'or' in item and isinstance(item['or'], list):
                self._check_allowed_filters(item['or'], _depth + 1)
            if 'and' in item and isinstance(item['and'], list):
                self._check_allowed_filters(item['and'], _depth + 1)
            if 'not' in item:
                not_content = item['not']
                if isinstance(not_content, dict):
                    self._check_allowed_filters([not_content], _depth + 1)
                elif isinstance(not_content, list):
                    self._check_allowed_filters(not_content, _depth + 1)
            if item.get('raw'):
                raise ValidationError(
                    "raw filters are not permitted when allowed_columns is set."
                )
            if isinstance(item.get('field'), str):
                self._check_allowed_column(item['field'])

    def _quote_write_target(self, name: str, quote: str) -> str:
        """Validates `name` as a bare identifier, then quotes it."""
        return self._quote(self._validate_bare_identifier(name), quote)

    def _check_scope_collision(self, keys) -> None:
        """
        Raises if any of `keys` collides with a scope-enforced column.

        Comparison is by NFC + casefold on both sides. NFC so that an
        NFD spelling of a scoped column collides with an NFC scope key;
        casefold because quoted identifiers are case-insensitive on
        SQLite and MySQL.

        `keys` should already have passed _validate_bare_identifier, so
        there is no remaining normalization gap between what is checked
        here and what _quote_write_target produces.
        """
        if not self.scope:
            return

        def canon(k):
            return unicodedata.normalize('NFC', str(k)).casefold()

        scope_keys = {canon(k) for k in self.scope}
        collisions = [k for k in keys if canon(k) in scope_keys]
        if collisions:
            raise ValidationError(
                f"Cannot set scoped field(s): {collisions}. "
                f"Scope fields are managed server-side."
            )

    def _parse_jsonb_path(self, name: str) -> tuple[str, list]:
        """
        Split a Pg JSONB path into (base_identifier, [(operator, key), ...]).

        Non-Pg dialects, or names with no -> / ->>, return (name, []).
        Cosmetic whitespace around operators is trimmed from keys.
        Trailing operators with no key raise InvalidIdentifierError.
        """
        if self.dbms != 'pg' or '->' not in name:
            return name, []

        parts = _JSONB_OP_RE.split(name)
        if len(parts) == 1:
            return name, []

        base = parts[0].strip()
        path = []
        for i in range(1, len(parts), 2):
            op = parts[i]
            if i + 1 >= len(parts):
                raise InvalidIdentifierError(
                    f"JSONB path is missing a key after {op!r}: {name!r}"
                )
            key = parts[i + 1].strip()
            if not key:
                raise InvalidIdentifierError(
                    f"JSONB path is missing a key after {op!r}: {name!r}"
                )
            path.append((op, key))

        if not base:
            raise InvalidIdentifierError(
                f"JSONB path is missing a column: {name!r}"
            )
        return base, path

    def _quote(self, name: str, quote: str) -> str:
        """
        Quote an identifier for this dialect.

        Single entry point for SELECT/WHERE/ORDER/GROUP column refs
        (schema.table, Pg JSONB paths). Write targets go through
        _quote_write_target, which rejects dots and JSONB first.

        Leading/trailing whitespace on the whole name is rejected, not
        stripped — same rule as _validate_bare_identifier. Whitespace
        around '.' and '->'/'->>' is treated as cosmetic and trimmed.
        """
        if not isinstance(name, str) or not name:
            raise InvalidIdentifierError("Identifier cannot be empty.")
        if name != name.strip():
            raise InvalidIdentifierError(
                f"Column name {name!r} has leading or trailing whitespace. "
                f"filtersql does not strip identifiers, so this would be "
                f"treated as a column literally named {name!r}. Remove the "
                f"whitespace if it was accidental."
            )
        if '\x00' in name:
            raise InvalidIdentifierError("Identifier contains null byte.")

        base, path = self._parse_jsonb_path(name)
        if path:
            quoted_base = self._quote(base, quote)
            safe_path = "".join(
                f"{op}'{self._safe_jsonb_key(key)}'" for op, key in path
            )
            return f"{quoted_base}{safe_path}"

        if '.' in name:
            parts = [p.strip() for p in name.split('.')]
            if not all(parts) or len(parts) > 2:
                raise InvalidIdentifierError(f"Invalid dotted identifier: {name!r}")
            return ".".join(self._quote(p, quote) for p in parts)

        escaped_name = name.replace(quote, quote * 2)
        return f"{quote}{escaped_name}{quote}"

    def _invert_order(self, ord: str, inv: str | bool) -> str:
        ord_clean = str(ord).lower() if ord is not None else ''
        if ord_clean not in ['asc', 'desc']:
            raise ValidationError("order must be 'asc' or 'desc'")
        if inv:
            return 'desc' if ord_clean == 'asc' else 'asc'
        return ord_clean

    def _cursor_operator(self, direction: str, col_order: str) -> str:
        col_order_clean = str(col_order).lower() if col_order is not None else 'asc'
        if col_order_clean not in ('asc', 'desc'):
            raise ValidationError("order must be 'asc' or 'desc'")
        if direction == 'seek':
            return '='
        if direction == 'next':
            return '>' if col_order_clean == 'asc' else '<'
        if direction == 'prev':
            return '<' if col_order_clean == 'asc' else '>'
        raise ValidationError(f"Invalid direction '{direction}'")

    def _resolve_source(self) -> str:
        """
        Resolves the source (table or subquery).

        WARNING: If raw_source=True, the source string is used directly 
        in the SQL query. This is a SQL injection risk if the source
        contains untrusted input. Only use with trusted, hardcoded values.

        Example of safe usage:
                # Hardcoded subquery - safe
                ds = Datasource(
                    source="(SELECT * FROM users WHERE active = true) AS active_users",
                    raw_source=True,
                    dbms='Pg'
                )

                # User-provided table name - UNSAFE!
                ds = Datasource(
                    source=request.GET.get('table'),  # NEVER DO THIS
                    raw_source=True,
                    dbms='Pg'
                )
        """
        if not self.source or not isinstance(self.source, str) or not self.source.strip():
            raise ConfigurationError("Datasource requires a non-empty string 'source'.")
        self._check_allowed_source()

        if self.raw_source:
            if not self.allow_raw_source:
                raise ConfigurationError("raw_source is disabled. Set allow_raw_source=True to enable.")

            # Intentionally raw for subquery injection
            # Example: "(SELECT * FROM users WHERE id > 100) AS filtered_users"
            return self.source
        return self._quote(self.source, DBMS_MAP[self.dbms]['quote'])

    @staticmethod
    def _coerce_limit_int(raw_value, field_name: str):
        """
        Coerces an integer-like value from a limit dict.

        Accepts int, a string that parses as an integer (typical of
        request.args.get), and any numeric type whose value is exactly an
        integer (float 3.0, Decimal('3'), Fraction(3, 1)).

        Rejects bool (True would silently mean 1), non-integral numerics
        (2.9 would silently mean 2 under int()), and non-numeric strings.

        Returns None if `raw_value` is None, so the caller can apply the
        default.
        """
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            raise ValidationError(
                f"Limit '{field_name}' must be an integer, got bool."
            )
        try:
            coerced = int(raw_value)
        except (ValueError, TypeError, OverflowError, ArithmeticError):
            raise ValidationError(
                f"Limit '{field_name}' must be an integer."
            )
        # Reject silent truncation of fractional values. Strings are exempt:
        # int('10') is a legitimate form-input path, and it has no fractional
        # part to lose. Non-string numeric types must survive an exact
        # round-trip.
        if not isinstance(raw_value, str) and coerced != raw_value:
            raise ValidationError(
                f"Limit '{field_name}' must be an integer, got {raw_value!r}."
            )
        return coerced

    def _build_limit(self, **kwargs) -> str:
        raw_start  = kwargs.get("start")
        raw_length = kwargs.get("length")

        start  = self._coerce_limit_int(raw_start,  "start")
        length = self._coerce_limit_int(raw_length, "length")

        if start is None:
            start = 0
        if length is None:
            length = DEFAULT_PAGE_LENGTH

        if start < 0:
            raise ValidationError("Limit 'start' cannot be negative.")
        if length <= 0:
            raise ValidationError("Limit 'length' must be greater than 0.")
        if length > MAX_LIMIT_LENGTH:
            raise ValidationError(
                f"Limit 'length' cannot exceed {MAX_LIMIT_LENGTH}."
            )

        limit_template = DBMS_MAP[kwargs["dbms"]].get("limit", "")
        return limit_template.format(start=start, length=length)

def filtersql(payload=None, dbms=None, scope=None, raw_source=False,
              allow_raw_source=False, allow_raw_fields=False,
              allowed_columns=None, allowed_sources=None,
              placeholder=None, fts_language=None, **kwargs) -> tuple[str, list]:
    if payload is not None and not isinstance(payload, dict):
        raise ValidationError(f"Expected dict for 'payload', got {type(payload).__name__}")

    data = (payload or {}).copy()
    data.update(kwargs)

    raw_action = data.get('action')
    if not raw_action or not isinstance(raw_action, str):
        raise ValidationError("Payload requires a valid string 'action' ('select', 'insert', 'update', 'delete').")
    
    action = raw_action.lower()
    if action not in ['select', 'insert', 'update', 'delete']:
        raise ValidationError(f"Invalid action '{action}'. Please specify: select, insert, update, delete.")

    source = data.get('source')
    if not source or not isinstance(source, str) or not source.strip():
        raise ValidationError("Payload requires a non-empty string 'source'.")

    if not dbms:
        raise ConfigurationError(
            f"dbms is required. Valid: {list(DBMS_MAP.keys())}"
        )

    for key in ['raw_source', 'allow_raw_source', 'allow_raw_fields',
                'placeholder', 'dbms', 'scope', 'fts_language',
                'allowed_columns', 'allowed_sources']:
        if key in data:
            raise ValidationError(f"'{key}' is a server-side configuration flag and cannot be set from the payload.")

    ds = Datasource(
        source=source,
        dbms=dbms,
        raw_source=raw_source,
        allow_raw_source=allow_raw_source,
        allow_raw_fields=allow_raw_fields,
        allowed_columns=allowed_columns,
        allowed_sources=allowed_sources,
        order=data.get('order'),
        limit=data.get('limit'),
        scope=scope,
        direction=data.get('direction'),
        placeholder=placeholder,
        fts_language=fts_language,
    )

    if action == 'select':
        return ds.select(
            columns=data.get('columns'),
            filters=data.get('filters'),
            group_by=data.get('group_by'),
            having=data.get('having'),
            cursor=data.get('cursor'),
            direction=data.get('direction'),
        )
    elif action == 'insert':
        return ds.insert(
            values=data.get('values', {}),
            returning=data.get('returning')
        )
    elif action == 'update':
        return ds.update(
            id=data.get('id', {}),
            values=data.get('values', {})
        )
    elif action == 'delete':
        return ds.delete(
            id=data.get('id', {})
        )
