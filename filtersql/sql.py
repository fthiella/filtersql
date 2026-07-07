# -*- coding: utf-8 -*-

DBMS_MAP = {
    'SQLite': {
        "delimiter":   ',',
        "quote":       '"',
        "search_map": {
            '=':               '{col}={param}',
            '!=':              '{col}!={param}',
            '>':               '{col}>{param}',
            '>=':              '{col}>={param}',
            '<':               '{col}<{param}',
            '<=':              '{col}<={param}',
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
            '=':               '{col}={param}',
            '!=':              '{col}!={param}',
            '>':               '{col}>{param}',
            '>=':              '{col}>={param}',
            '<':               '{col}<{param}',
            '<=':              '{col}<={param}',
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
            'fts':             "{col} @@ websearch_to_tsquery({lang}, {param})",
            'fts_query':       "to_tsvector({lang}, coalesce({col}, '')) @@ websearch_to_tsquery({lang}, {param})",
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
            '=':               '{col}={param}',
            '!=':              '{col}!={param}',
            '>':               '{col}>{param}',
            '>=':              '{col}>={param}',
            '<':               '{col}<{param}',
            '<=':              '{col}<={param}',
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
            '=':               '{col}={param}',
            '!=':              '{col}!={param}',
            '>':               '{col}>{param}',
            '>=':              '{col}>={param}',
            '<':               '{col}<{param}',
            '<=':              '{col}<={param}',
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
        "top": ' {columns} from (select qqq.*, rownum rrr from (select ',
        "limit": ') qqq where rownum <= {2}) where rrr>{0}',
    }
}

class Datasource:
    """
    filtersql Class
    Sql queries for AI, DataTables, LLM outputs and any other Frontend application
    """

    def __init__(self, **kwargs):
        self.source       = kwargs.get('source', None)
        self.raw_source   = kwargs.get('raw_source', False)
        self.order        = kwargs.get('order', [])
        self.limit        = kwargs.get('limit', None)
        self.dbms         = kwargs.get('dbms', None)
        self.move         = kwargs.get('move', 'search')
        self.placeholder  = kwargs.get('placeholder', '?')
        self.fts_language = kwargs.get('fts_language', 'english')

        if self.dbms not in DBMS_MAP:
            raise ValueError(f"Unknown dbms '{self.dbms}'. Valid: {list(DBMS_MAP)}")

    def select(self, **kwargs):
        # columns: passed per-call, can be computed at runtime
        raw_columns = kwargs.get('columns', [])
        columns = list(
            map(
                lambda x: self._quote(x.get('field'), DBMS_MAP[self.dbms]['quote']),
                filter(
                    lambda x: (x.get("type", "text") != "blob"),
                    raw_columns)
            ))

        filters = kwargs.get('filters', [])
        if len(filters) > 0:
            q_filters = self._build_where(
                filters=filters,
                move=self.move,
                dbms=self.dbms
            )
        else:
            q_filters = None

        order_by = list(
            map(
                lambda x: self._quote(x.get('field'), DBMS_MAP[self.dbms]['quote'])
                    + " "
                    + self._invert_order(
                        x.get("order", "asc"),
                        self.move == 'backwards'
                    ),
                kwargs.get('order', self.order)
            ))

        limit_top = ""
        limit_bottom = ""
        active_limit = kwargs.get('limit', self.limit)

        if active_limit:
            limit_top = self._build_limit_top(dbms=self.dbms, start=active_limit.get("start", 0), length=active_limit.get("length", 99), columns=columns)
            limit_bottom = self._build_limit_bottom(dbms=self.dbms, start=active_limit.get("start", 0), length=active_limit.get("length", 99), columns=columns)

        query = "select{}\n".format(limit_top)
        query += ",\n".join(list(map(lambda x: "  "+x, columns))) + "\n"
        query += "from\n"
        
        if self.raw_source:
            query += "  " + self.source + "\n"
        else:
            query += "  " + self._quote(self.source, DBMS_MAP[self.dbms]['quote']) + "\n"

        if (q_filters):
            query += "where\n"
            query += "  " + q_filters['where'] + "\n"

        if (order_by):
            query += "order by\n"
            query += "  " + ",\n  ".join(order_by) + "\n"

        if (limit_bottom):
            query += limit_bottom + "\n"

        if (q_filters):
            return (query, q_filters['value'])
        else:
            return (query, [])

    def insert(self, **kwargs):
        values    = kwargs.get('values', {})
        returning = kwargs.get('returning', None)

        if not values:
            raise ValueError("insert() requires at least one value")
        if returning and self.dbms != 'Pg':
            raise ValueError(f"returning is not supported by {self.dbms}")

        if self.raw_source:
            source = self.source
        else:
            source = self._quote(self.source, DBMS_MAP[self.dbms]['quote'])

        fields = [self._quote(k, DBMS_MAP[self.dbms]['quote']) for k in values.keys()]
        placeholders = [self.placeholder] * len(fields)
        set_values = list(values.values())

        query  = "insert into " + source + "\n"
        query += "  (" + ", ".join(fields) + ")\n"
        query += "values\n"
        query += "  (" + ", ".join(placeholders) + ")\n"

        if returning:
            ret_col = self._quote(returning, DBMS_MAP[self.dbms]['quote'])
            query += "returning " + ret_col + "\n"

        return query, set_values

    def update(self, **kwargs):
        id_dict = kwargs.get('id', {})
        values  = kwargs.get('values', {})
        if not id_dict:
            raise ValueError("update() requires at least one id field")
        if not values:
            raise ValueError("update() requires at least one value to update")

        my_filters = [{ 'field': k, 'operator': '=', 'value': v} for k,v in id_dict.items()]

        if self.raw_source:
            source = self.source
        else:
            source = self._quote(self.source, DBMS_MAP[self.dbms]['quote'])

        set_parts = [
            self._quote(k, DBMS_MAP[self.dbms]['quote']) + " = " + self.placeholder
            for k in values.keys()
        ]
        set_values = list(values.values())

        where_clause, where_values = self.where(filters=my_filters)

        query  = "update\n"
        query += "  " + source + "\n"
        query += "set\n"
        query += "  " + ",\n  ".join(set_parts) + "\n"
        query += "where\n"
        query += "  " + where_clause + "\n"

        return query, set_values + where_values

    def delete(self, **kwargs):
        id_dict = kwargs.get('id', {})
        if not id_dict:
            raise ValueError("delete() requires at least one id field")

        my_filters = [{ 'field': k, 'operator': '=', 'value': v} for k,v in id_dict.items()]

        if self.raw_source:
            source = self.source
        else:
            source = self._quote(self.source, DBMS_MAP[self.dbms]['quote'])

        where_clause, where_values = self.where(filters=my_filters)

        query  = "delete from\n"
        query += "  " + source + "\n"
        query += "where\n"
        query += "  " + where_clause + "\n"

        return query, where_values

    def where(self, **kwargs):
        filters = kwargs.get('filters', [])

        if len(filters) > 0:
            q_filters = self._build_where(
                filters=filters,
                move=self.move,
                dbms=self.dbms
            )
            return q_filters['where'], q_filters['value']
        return "", []

    def paginate(self, final_list, **kwargs):
        start = kwargs.get('start', self.limit.get('start', 0) if self.limit else 0)
        length = kwargs.get('length', self.limit.get('length', 5) if self.limit else 5)
        return final_list[start : start + length]

    def limit_pool(self, default_pool_size=40):
        return "\n" + DBMS_MAP[self.dbms].get("limit", "").format(0, default_pool_size)

    def _build_where(self, **kwargs):
        o = {'find': '=', 'forwards': '>', 'backwards': '<'}

        f_move   = [x for x in kwargs['filters'] if isinstance(x, dict) and x.get('type', 'search') == 'move']
        f_search = [x for x in kwargs['filters'] if not isinstance(x, dict) or x.get('type', 'search') == 'search']

        m_where = []
        m_data  = []

        if kwargs["move"] in ['find', 'forwards', 'backwards']:
            for i in range(len(f_move), 0, -1):
                or_where = list(map(
                    lambda x: self._build_filter(col=x.get('field'), searchcriteria='='),
                    f_move[0:i-1]
                ))
                m_statement = (
                    self._quote(f_move[i-1].get('field'), DBMS_MAP[kwargs["dbms"]]['quote'])
                    + o[kwargs["move"]]
                    + self.placeholder
                )
                or_where.append(m_statement)
                m_where.append('(' + ' and '.join(or_where) + ')')
                m_data.extend([x.get('value') for x in f_move[0:i]])

                if kwargs["move"] == 'find':
                    break

        s_sql, s_data = self._build_filter_group(f_search, join='and')

        q_where = []
        if m_where:
            q_where.append("(" + " or ".join(m_where) + ")")
        if s_sql:
            q_where.append("(" + s_sql + ")")

        return {
            'where': " and ".join(q_where),
            'value': m_data + s_data
        }

    def _build_filter_group(self, filters: list, join: str = 'and') -> tuple:
        """
        Recursively builds SQL for a list of filters.
        Each item can be:
          - a plain dict          → single filter (AND by default)
          - {'or':  [...]}        → OR group
          - {'and': [...]}        → AND group (for nesting inside an OR)
        Returns (sql_fragment, values_list).
        """
        parts = []
        values = []

        for item in filters:
            if not isinstance(item, dict):
                continue

            if 'or' in item:
                sub_sql, sub_vals = self._build_filter_group(item['or'], join='or')
                parts.append('(' + sub_sql + ')')
                values.extend(sub_vals)

            elif 'and' in item:
                sub_sql, sub_vals = self._build_filter_group(item['and'], join='and')
                parts.append('(' + sub_sql + ')')
                values.extend(sub_vals)

            else:
                sql_frag, vals = self._build_single_filter(item)
                parts.append(sql_frag)
                values.extend(vals)

        joiner = f' {join} '
        return joiner.join(parts), values

    def _build_single_filter(self, f: dict) -> tuple:
        """
        Builds SQL fragment and values for a single filter dict.
        Returns (sql_fragment, values_list).
        """
        colonna     = f.get('field')
        criterio    = f.get('operator', 'icontains')
        valore      = f.get('value')
        tipo_valore = f.get('value_type', 'text')

        sql_frag = self._build_filter(
            col=colonna,
            searchcriteria=criterio,
            search_value=valore,
            value_type=tipo_valore,
        )

        if criterio in ['null', 'notnull']:
            return sql_frag, []
        elif criterio in ['in', 'notin']:
            if isinstance(valore, (list, tuple)):
                return sql_frag, list(valore)
            else:
                return sql_frag, [valore]
        elif criterio == 'between':
            # value is [low, high]
            return sql_frag, list(valore)
        else:
            return sql_frag, [valore]

    def _build_filter(self, col: str, searchcriteria: str = "icontains", search_value=None, value_type: str = "text") -> str:
        if searchcriteria == 'fts' and self.dbms != 'Pg':
            raise ValueError(f"FTS operator not supported for {self.dbms}")

        if searchcriteria not in DBMS_MAP[self.dbms]["search_map"]:
            searchcriteria = 'icontains'
            
        raw_statement = DBMS_MAP[self.dbms]["search_map"][searchcriteria]
        quoted_col = self._quote(col, DBMS_MAP[self.dbms]["quote"])

        # 1. Handle specialized list structures (IN / NOT IN)
        if searchcriteria in ['in', 'notin']:
            if not isinstance(search_value, (list, tuple)):
                search_value = [search_value] if search_value is not None else []
            
            # Generates: ?, ?, ? or %s, %s, %s
            placeholders_str = ", ".join([self.placeholder] * len(search_value))
            return raw_statement.format(col=quoted_col, params=placeholders_str)

        # 2. Handle BETWEEN ranges
        elif searchcriteria == 'between':
            if not isinstance(search_value, (list, tuple)) or len(search_value) != 2:
                raise ValueError(f"'between' operator requires a list of exactly two values, got: {search_value!r}")
            return raw_statement.format(col=quoted_col, param1=self.placeholder, param2=self.placeholder)

        # 3. Handle REVERSE IN
        elif searchcriteria == 'reverse_in':
            col_list = [c.strip() for c in col.split(',')]
            parsed_cols = []
            for c in col_list:
                if self.dbms == 'Pg' and '->>' in c:
                    parts = c.split('->>')
                    main_column = self._quote(parts[0].strip(), DBMS_MAP[self.dbms]["quote"])
                    json_key = parts[1].strip()
                    parsed_cols.append(f"{main_column}->>'{json_key}'")
                else:
                    parsed_cols.append(self._quote(c, DBMS_MAP[self.dbms]["quote"]))
            
            return raw_statement.format(param=self.placeholder, cols=', '.join(parsed_cols))

        # 4. Handle JSONB paths with Type Casting (PostgreSQL)
        if self.dbms == 'Pg' and '->>' in col:
            parts = col.split('->>')
            main_column = self._quote(parts[0].strip(), DBMS_MAP[self.dbms]["quote"])
            json_key = parts[1].strip()
            
            if value_type == 'numeric':
                sql_field = f"({main_column}->>'{json_key}')::numeric"
                p_placeholder = f"{self.placeholder}::numeric"
            elif value_type == 'date':
                sql_field = f"({main_column}->>'{json_key}')::date"
                p_placeholder = f"{self.placeholder}::date"
            else:
                sql_field = f"{main_column}->>'{json_key}'"
                p_placeholder = self.placeholder
                
            return raw_statement.format(col=sql_field, param=p_placeholder, lang=self.fts_language)

        # 5. Default single variable assignment
        return raw_statement.format(col=quoted_col, param=self.placeholder, lang=self.fts_language)

    def _quote(self, name: str, quote: str) -> str:
        """returns a quoted string, handling JSONB operators if present"""
        if not name:
            raise ValueError(f"field name is missing or empty")

        if '->>' in name:
            col, path = name.split('->>')
            return f"{quote}{col}{quote}->>'{path}'"

        if '.' in name:
            parts = name.split('.')
            return f"{parts[0]}.{quote}{parts[1]}{quote}"

        return quote + name + quote

    def _invert_order(self, ord: str, inv: str) -> str:
        if ord not in ['asc', 'desc']:
            raise ValueError("order must be 'asc' or 'desc'")

        if inv:
            return 'desc' if ord == 'asc' else 'asc'
        return ord

    def _build_limit_top(self, **kwargs):
        return DBMS_MAP[kwargs["dbms"]].get("top", "").format(
                    kwargs.get("start", 0),
                    kwargs.get("length", 0),
                    kwargs.get("start", 0) + kwargs.get("length", 0),
                    columns=", ".join(kwargs.get("columns", None))
                )

    def _build_limit_bottom(self, **kwargs):
        return DBMS_MAP[kwargs["dbms"]].get("limit", "").format(
                    kwargs.get("start", 0),
                    kwargs.get("length", 99),
                    kwargs.get("start", 0) + kwargs.get("length", 99)
                )
