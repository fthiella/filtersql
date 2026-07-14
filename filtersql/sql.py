# -*- coding: utf-8 -*-
import re

DBMS_MAP = {
    'SQLite': {
        "delimiter":   ',',
        "quote":       '"',
        "search_map": {
            '=':               '{col} = {param}',
            '!=':              '{col} != {param}',
            '>':               '{col} > {param}',
            '>=':              '{col} >= {param}',
            '<':               '{col} < {param}',
            '<=':              '{col} <= {param}',
            'starts_with':     '{col} glob {param} || \'*\'',
            'ends_with':       '{col} glob \'*\' || {param}',
            'contains':        '{col} glob \'*\' || {param} || \'*\'',
            'istarts_with':    '{col} like {param} || \'%\'',
            'iends_with':      '{col} like \'%\' || {param}',
            'icontains':       '{col} like \'%\' || {param} || \'%\'',
            'in':              '{col} in ({params})',
            'notin':           '{col} not in ({params})',
            'reverse_in':      '{param} in ({cols})',
            'null':            '{col} is null',
            'notnull':         '{col} is not null',
            'between':         '{col} between {param1} and {param2}',
            'not_starts_with': '{col} not glob {param} || \'*\'',
            'not_contains':    '{col} not glob \'*\' || {param} || \'*\'',
            'not_icontains':   '{col} not like \'%\' || {param} || \'%\'',
            'regexp':          '{col} regexp {param}',
        },
        "limit":  'limit {0}, {1}',
    },
    'Pg': {
        "delimiter":   ',',
        "quote":       '"',
        "search_map": {
            '=':               '{col} = {param}',
            '!=':              '{col} != {param}',
            '>':               '{col} > {param}',
            '>=':              '{col} >= {param}',
            '<':               '{col} < {param}',
            '<=':              '{col} <= {param}',
            'starts_with':     '{col} like {param} || \'%\'',
            'ends_with':       '{col} like \'%\' || {param}',
            'contains':        '{col} like \'%\' || {param} || \'%\'',
            'istarts_with':    '{col} ilike {param} || \'%\'',
            'iends_with':      '{col} ilike \'%\' || {param}',
            'icontains':       '{col} ilike \'%\' || {param} || \'%\'',
            'in':              '{col} in ({params})',
            'notin':           '{col} not in ({params})',
            'reverse_in':      '{param} in ({cols})',
            'null':            '{col} is null',
            'notnull':         '{col} is not null',
            'fts':             "{col} @@ websearch_to_tsquery('{lang}', {param})",
            'fts_query':       "to_tsvector('{lang}', coalesce({col}, '')) @@ websearch_to_tsquery('{lang}', {param})",
            'between':         '{col} between {param1} and {param2}',
            'not_starts_with': '{col} not like {param} || \'%\'',
            'not_contains':    '{col} not like \'%\' || {param} || \'%\'',
            'not_icontains':   '{col} not ilike \'%\' || {param} || \'%\'',
            'regexp':          '{col} ~ {param}',
            'iregexp':         '{col} ~* {param}',
        },
        "limit": 'limit {1} offset {0}',
    },
    'mysql': {
        "delimiter": ',',
        "quote":     '`',
        "search_map": {
            '=':               '{col} = {param}',
            '!=':              '{col} != {param}',
            '>':               '{col} > {param}',
            '>=':              '{col} >= {param}',
            '<':               '{col} < {param}',
            '<=':              '{col} <= {param}',
            'starts_with':     '{col} like binary concat({param}, \'%\')',
            'ends_with':       '{col} like binary concat(\'%\', {param})',
            'contains':        '{col} like binary concat(\'%\', {param}, \'%\')',
            'istarts_with':    '{col} like concat({param}, \'%\')',
            'iends_with':      '{col} like concat(\'%\', {param})',
            'icontains':       '{col} like concat(\'%\', {param}, \'%\')',
            'in':              '{col} in ({params})',
            'notin':           '{col} not in ({params})',
            'reverse_in':      '{param} in ({cols})',
            'null':            '{col} is null',
            'notnull':         '{col} is not null',
            'fts':              "match({col}) against({param} in boolean mode)",
            'fts_query':        "match({col}) against({param} in boolean mode)",
            'between':         '{col} between {param1} and {param2}',
            'not_starts_with': '{col} not like binary concat({param}, \'%\')',
            'not_contains':    '{col} not like binary concat(\'%\', {param}, \'%\')',
            'not_icontains':   '{col} not like concat(\'%\', {param}, \'%\')',
            'regexp':          '{col} regexp {param}',
            'iregexp':         '{col} regexp {param}',
        },
        "limit": 'limit {0}, {1}',
    },
    'Oracle': {
        "delimiter": ',',
        "quote":     '"',
        "search_map": {
            '=':               '{col} = {param}',
            '!=':              '{col} != {param}',
            '>':               '{col} > {param}',
            '>=':              '{col} >= {param}',
            '<':               '{col} < {param}',
            '<=':              '{col} <= {param}',
            'starts_with':     '{col} like {param} || \'%\'',
            'ends_with':       '{col} like \'%\' || {param}',
            'contains':        '{col} like \'%\' || {param} || \'%\'',
            'istarts_with':    'regexp_like({col}, \'^\' || {param}, \'i\')',
            'iends_with':      'regexp_like({col}, {param} || \'$\', \'i\')',
            'icontains':       'regexp_like({col}, {param}, \'i\')',
            'in':              '{col} in ({params})',
            'notin':           '{col} not in ({params})',
            'reverse_in':      '{param} in ({cols})',
            'null':            '{col} is null',
            'notnull':         '{col} is not null',
            'between':         '{col} between {param1} and {param2}',
            'not_starts_with': '{col} not like {param} || \'%\'',
            'not_contains':    '{col} not like \'%\' || {param} || \'%\'',
            'not_icontains':   'not regexp_like({col}, {param}, \'i\')',
            'regexp':          'regexp_like({col}, {param})',
            'iregexp':         'regexp_like({col}, {param}, \'i\')',
        },
        "limit": 'offset {0} rows fetch next {1} rows only'
    }
}

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
    filtersql Class
    Sql queries for AI, DataTables, LLM outputs and any other Frontend application
    """

    def __init__(
        self, 
        *, 
        source: str = None,
        dbms: str = None,
        raw_source: bool = False,
        order: list = None,
        limit: dict = None,
        scope: dict = None,
        direction: str = None,
        placeholder: str = '?',
        fts_language: str = 'english'
    ):
        """
        Datasource initialization
        """

        self.source          = source
        self.raw_source      = raw_source
        self.order           = order or []
        self.limit           = limit
        self.scope           = scope or {}
        self.dbms            = dbms
        self.direction       = direction
        self.placeholder     = placeholder
        self.fts_language    = fts_language

        if not self.dbms or self.dbms not in DBMS_MAP:
            raise ConfigurationError(
                f"Unknown or missing dbms: '{self.dbms}'. Valid: {list(DBMS_MAP.keys())}"
            )

    def select(self, *, columns: list = None, filters: list = None, order: list = None, limit: dict = None, direction: str = None) -> tuple[str, list]:
        """Build a SELECT query. Pass columns, filters, order, limit explicitly."""
        filters = list(filters or [])
        if not isinstance(filters, list):
            raise ValidationError("Expected list as 'filters'.")
            
        columns = columns or []
        if not isinstance(columns, list):
            raise ValidationError("Expected list as 'columns'.")

        quote_char = DBMS_MAP[self.dbms]['quote']
        delim = DBMS_MAP[self.dbms]['delimiter']

        parsed_columns = [
            self._quote(x['field'], quote_char)
            for x in columns
        ]

        active_direction = direction or self.direction
        where_clause, where_values = self.where(filters=filters, direction=active_direction)

        active_order = order if order is not None else self.order
        parsed_order = [
            self._quote(x.get('field'), quote_char)
            + " "
            + self._invert_order(x.get('order', 'asc'), active_direction == 'prev')
            for x in active_order
        ]

        active_limit = limit if limit is not None else self.limit
        limit = ""
        if active_limit:
            limit = self._build_limit(
                dbms=self.dbms, 
                start=active_limit.get("start", 0), 
                length=active_limit.get("length", 99)
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

        if parsed_order:
            segments.extend([
                "order by",
                "  " + (delim + "\n  ").join(parsed_order)
            ])

        if limit:
            segments.append(limit)

        return "\n".join(segments) + "\n", where_values

    def insert(self, *, values: dict = None, returning: str = None) -> tuple[str, list]:
        """Build an INSERT statement. Requires values dict, optional returning field."""

        if not values and not self.scope:
            raise ValidationError("insert() requires at least one value")

        if returning and self.dbms != 'Pg':
            raise ValidationError(f"returning is not supported by {self.dbms}")

        if values and not isinstance(values, dict):
            raise ValidationError("Expected a dictionary for 'values'")

        final_values = {**(values or {}), **self.scope}

        source = self._resolve_source()
        quote_char = DBMS_MAP[self.dbms]['quote']

        fields = []
        set_values = []
        placeholders = []

        for k, v in final_values.items():
            fields.append(self._quote(k, quote_char))
            placeholders.append(self.placeholder)
            set_values.append(v)

        segments = [
            f"insert into {source}",
            "  (" + ", ".join(fields) + ")",
            "values",
            "  (" + ", ".join(placeholders) + ")"
        ]

        if returning:
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

        source = self._resolve_source()
        quote_char = DBMS_MAP[self.dbms]['quote']

        set_parts = []
        set_values = []

        for k, v in values.items():
            set_parts.append(f"{self._quote(k, quote_char)} = {self.placeholder}")
            set_values.append(v)

        my_filters = [{'field': k, 'operator': '=', 'value': v} for k, v in id.items()]

        where_clause, where_values = self.where(filters=my_filters)

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

        my_filters = [{'field': k, 'operator': '=', 'value': v} for k, v in id.items()]
        
        source = self._resolve_source()
        where_clause, where_values = self.where(filters=my_filters)

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
        """Returns query with placeholders replaced by actual values, for debugging."""
        debug_query = query
        for val in values:
            if isinstance(val, str):
                escaped = val.replace("'", "''")
                formatted_val = f"'{escaped}'"
            elif val is None:
                formatted_val = "null"
            else:
                formatted_val = str(val)

            debug_query = debug_query.replace(self.placeholder, formatted_val, 1)
            
        return debug_query

    def where(self, *, filters: list = None, direction: str = None) -> tuple[str, list]:
        """Build a WHERE clause from filters. Returns (clause, values)."""
        active_direction = direction or self.direction
        scope_filters = [{'field': k, 'operator': '=', 'value': v} for k, v in self.scope.items()]
        all_filters = scope_filters + list(filters or [])
        if all_filters:
            return self._build_where(filters=all_filters, direction=active_direction, dbms=self.dbms)
        return "", []

    def _build_where(self, *, filters: list, direction: str, dbms: str) -> tuple[str, list]:
        """Build a WHERE clause from filters. Returns (clause, values)."""
        if direction and direction not in ['seek', 'next', 'prev']:
            raise ValidationError(
                f"Invalid direction '{direction}'. Please use: seek, next, prev."
            )

        operators = {'seek': '=', 'next': '>', 'prev': '<'}

        # --- FIX: Controllo di tipo "Fail Fast" per bloccare input malformati ---
        for item in filters:
            if not isinstance(item, dict):
                raise ValidationError(
                    f"Invalid filter format. Expected dict, got: {type(item).__name__} ({item})"
                )
        # -------------------------------------------------------------------------

        # Ora possiamo usare .get() in totale sicurezza
        f_cursor = [x for x in filters if x.get('type') == 'move']
        f_search = [x for x in filters if x.get('type', 'search') == 'search']

        m_where = []
        m_data = []

        # Build cursor pagination clause
        if direction in ['seek', 'next', 'prev'] and f_cursor:
            op = operators[direction]
            
            if direction == 'seek':
                conditions = []
                for cursor in f_cursor:
                    conditions.append(
                        f"{self._quote(cursor['field'], DBMS_MAP[dbms]['quote'])} = {self.placeholder}"
                    )
                    m_data.append(cursor['value'])
                m_where.append(' and '.join(conditions))
            else:
                # Keyset pagination: (col1 > v1) OR (col1 = v1 AND col2 > v2)
                # NOTA: I duplicati in m_data sono necessari per i placeholder posizionali
                or_conditions = []
                for i in reversed(range(len(f_cursor))):
                    and_parts = []
                    for j in range(i):
                        c = f_cursor[j]
                        and_parts.append(
                            f"{self._quote(c['field'], DBMS_MAP[dbms]['quote'])} = {self.placeholder}"
                        )
                        m_data.append(c['value'])
                    c = f_cursor[i]
                    and_parts.append(
                        f"{self._quote(c['field'], DBMS_MAP[dbms]['quote'])} {op} {self.placeholder}"
                    )
                    m_data.append(c['value'])
                    or_conditions.append('(' + ' and '.join(and_parts) + ')')
                m_where.append(' or '.join(or_conditions))

        # Build search conditions
        s_sql, s_data = self._build_filter_group(f_search, join='and')

        # Combine
        q_where = []
        if m_where:
            q_where.append('(' + ' and '.join(m_where) + ')')
        if s_sql:
            q_where.append('(' + s_sql + ')')

        return ' and '.join(q_where), m_data + s_data

    def _build_filter_group(self, filters: list, join: str = 'and') -> tuple:
        parts = []
        values = []

        for item in filters:
            if not isinstance(item, dict):
                raise ValidationError(f"Invalid filter. dict expected, got: {type(item).__name__} ({item})")

            if 'or' in item:
                sub_sql, sub_vals = self._build_filter_group(item['or'], join='or')
                parts.append('(' + sub_sql + ')')
                values.extend(sub_vals)

            elif 'and' in item:
                sub_sql, sub_vals = self._build_filter_group(item['and'], join='and')
                parts.append('(' + sub_sql + ')')
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

        field      = f.get('field')
        operator   = f.get('operator', 'icontains')
        value      = f.get('value')
        value_type = f.get('value_type', 'text')

        if not field:
            raise ValidationError(f"Filter is missing required 'field' key: {f}")

        sql_frag = self._build_condition(
            col=field,
            searchcriteria=operator,
            search_value=value,
            value_type=value_type,
        )

        if operator in ['null', 'notnull']:
            return sql_frag, []
        elif operator in ['in', 'notin']:
            if isinstance(value, (list, tuple)):
                return sql_frag, list(value)
            else:
                return sql_frag, [value]
        elif operator == 'between':
            return sql_frag, list(value)
        else:
            return sql_frag, [value]

    def _build_condition(self, col: str, searchcriteria: str = "icontains", search_value=None, value_type: str = "text") -> str:
        if searchcriteria in ['fts', 'fts_query'] and self.dbms not in ['Pg', 'mysql']:
            raise ValidationError(f"FTS operator not supported for {self.dbms}")

        if searchcriteria not in DBMS_MAP[self.dbms]["search_map"]:
            valid = list(DBMS_MAP[self.dbms]['search_map'].keys())
            raise ValidationError(f"Operator '{searchcriteria}' not valid for {self.dbms}. Valid: {valid}")

        raw_statement = DBMS_MAP[self.dbms]["search_map"][searchcriteria]

        if searchcriteria == 'reverse_in':
            col_list = [c.strip() for c in col.split(',')]
            parsed_cols = []
            for c in col_list:
                if self.dbms == 'Pg' and '->>' in c:
                    parts = c.split('->>')
                    main_col = self._quote(parts[0].strip(), DBMS_MAP[self.dbms]["quote"])
                    parsed_cols.append(f"{main_col}->>'{parts[1].strip()}'")
                else:
                    parsed_cols.append(self._quote(c, DBMS_MAP[self.dbms]["quote"]))

            return raw_statement.format(param=self.placeholder, cols=', '.join(parsed_cols))

        if self.dbms == 'Pg' and '->>' in col:
            parts = col.split('->>')
            main_col = self._quote(parts[0].strip(), DBMS_MAP[self.dbms]["quote"])
            key = parts[1].strip()
            
            if value_type == 'numeric':
                col_expr = f"({main_col}->>'{key}')::numeric"
                param_expr = f"{self.placeholder}::numeric"
            elif value_type == 'date':
                col_expr = f"({main_col}->>'{key}')::date"
                param_expr = f"{self.placeholder}::date"
            else:
                col_expr = f"{main_col}->>'{key}'"
                param_expr = self.placeholder
        else:
            col_expr = self._quote(col, DBMS_MAP[self.dbms]["quote"])
            param_expr = self.placeholder

        if searchcriteria in ['in', 'notin']:
            if not isinstance(search_value, (list, tuple)):
                search_value = [search_value] if search_value is not None else []
            
            placeholders_str = ", ".join([param_expr] * len(search_value))
            return raw_statement.format(col=col_expr, params=placeholders_str)

        elif searchcriteria == 'between':
            if not isinstance(search_value, (list, tuple)) or len(search_value) != 2:
                raise ValidationError(f"'between' operator requires a list of two values, got: {search_value!r}")
            return raw_statement.format(col=col_expr, param1=param_expr, param2=param_expr)

        return raw_statement.format(col=col_expr, param=param_expr, lang=self.fts_language)

    def _quote(self, name: str, quote: str) -> str:
        """
        Secure quoting that distinguishes between column and table context.
        """

        if not name or not str(name).strip():
            raise InvalidIdentifierError("Identifier cannot be empty.")

        name = str(name).strip()

        if '->>' in name:
            col, path = name.split('->>', 1)
            return f"{self._quote(col.strip(), quote)}->>'{path.strip().strip('\"\'')}'"

        if '.' in name:
            parts = [p.strip() for p in name.split('.') if p.strip()]
            if len(parts) > 2:
                raise InvalidIdentifierError(f"Too many parts in identifier: {name}")
            return ".".join(f"{quote}{p}{quote}" for p in parts)

        if not re.match(r'^[a-zA-Z0-9_\sÀ-ÿ\u0080-\uFFFF\-]+$', name, re.UNICODE):
            raise InvalidIdentifierError(f"Invalid characters in identifier '{name}'.")

        return f"{quote}{name}{quote}"

    def _invert_order(self, ord: str, inv: str) -> str:
        if ord not in ['asc', 'desc']:
            raise ValidationError("order must be 'asc' or 'desc'")
        if inv:
            return 'desc' if ord == 'asc' else 'asc'
        return ord

    def _resolve_source(self) -> str:
        """
        Resolves the source (table or subquery).

        WARNING: If raw_source=True, the source string is used directly 
        in the SQL query. This is a SQL injection risk if the source
        contains untrusted input. Only use with trusted, hardcoded values.
        """
        if self.raw_source:
            # Intentionally raw for subquery injection
            # Example: "(SELECT * FROM users WHERE id > 100) AS filtered_users"
            return self.source
        return self._quote(self.source, DBMS_MAP[self.dbms]['quote'])

    def _build_limit(self, **kwargs) -> str:
        start = int(kwargs.get("start", 0))
        length = int(kwargs.get("length", 99))
        
        return DBMS_MAP[kwargs["dbms"]].get("limit", "").format(
                    start,
                    length,
                    start + length
                )

def filtersql(payload, dbms='Pg', scope=None, raw_source=False, placeholder='?') -> tuple[str, list]:
    action = payload.get('action', '').lower()
    source = payload.get('source')
    
    if not source:
        raise ValidationError("Need to specify 'source'.")
    if action not in ['select', 'insert', 'update', 'delete']:
        raise ValidationError(f"Invalid action '{action}'. Please specify: select, insert, update, delete.")

    ds = Datasource(
        source=source,
        dbms=dbms,
        raw_source=raw_source, 
        order=payload.get('order'),
        limit=payload.get('limit'),
        scope=scope,
        direction=payload.get('direction'),
        placeholder=placeholder
    )

    if action == 'select':
        return ds.select(
            columns=payload.get('columns'),
            filters=payload.get('filters')
        )

    elif action == 'insert':
        return ds.insert(
            values=payload.get('values', {}),
            returning=payload.get('returning')
        )

    elif action == 'update':
        return ds.update(
            id=payload.get('id', {}),
            values=payload.get('values', {})
        )
    
    elif action == 'delete':
        return ds.delete(
            id=payload.get('id', {})
        )