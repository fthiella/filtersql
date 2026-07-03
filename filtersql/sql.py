# -*- coding: utf-8 -*-

DBMS_MAP = {
    'SQLite': {
        "delimiter":   ',',
        "quote":       '"',
        "search_map": {
            '=':            '{}=?',
            '!=':           '{}!=?',
            '>':            '{}>?',
            '>=':           '{}>=?',
            '<':            '{}<?',
            '<=':           '{}<=?',
            'starts_with':  '{} glob ? || \'*\'',
            'ends_with':    '{} glob \'*\' || ?',
            'contains':     '{} glob \'*\' || ? || \'*\'',
            'istarts_with': '{} like ? || \'%\'',
            'iends_with':   '{} like \'%\' || ?',
            'icontains':    '{} like \'%\' || ? || \'%\'',
            'in':           '{} in ({})',
            'notin':        '{} not in ({})',
            'reverse_in':   '{} in ({})',
            'null':            '{} is null',
            'notnull':         '{} is not null',
            'between':         '{} between ? and ?',
            'not_starts_with': '{} not glob ? || \'*\'',
            'not_contains':    '{} not glob \'*\' || ? || \'*\'',
            'not_icontains':   '{} not like \'%\' || ? || \'%\'',
            'regexp':          '{} regexp ?',
        },
        "limit":  'limit {0}, {1}',
    },
    'Pg': {
        "delimiter":   ',',
        "quote":       '"',
        "search_map": {
            '=':            '{}=?',
            '!=':           '{}!=?',
            '>':            '{}>?',
            '>=':           '{}>=?',
            '<':            '{}<?',
            '<=':           '{}<=?',
            'starts_with':  '{} like ? || \'%\'',
            'ends_with':    '{} like \'%\' || ?',
            'contains':     '{} like \'%\' || ? || \'%\'',
            'istarts_with': '{} ilike ? || \'%\'',
            'iends_with':   '{} ilike \'%\' || ?',
            'icontains':    '{} ilike \'%\' || ? || \'%\'',
            'in':           '{} in ({})',
            'notin':        '{} not in ({})',
            'reverse_in':   '{} in ({})',
            'null':         '{} is null',
            'notnull':      '{} is not null',
            'fts':             "{} @@ websearch_to_tsquery('italian', ?)",
            'fts_query':       "to_tsvector('italian', coalesce({}, '')) @@ websearch_to_tsquery('italian', ?)",
            'between':         '{} between ? and ?',
            'not_starts_with': '{} not like ? || \'%\'',
            'not_contains':    '{} not like \'%\' || ? || \'%\'',
            'not_icontains':   '{} not ilike \'%\' || ? || \'%\'',
            'regexp':          '{} ~ ?',
            'iregexp':         '{} ~* ?',
        },
        "limit": 'limit {1} offset {0}',
    },
    'mysql': {
        "delimiter": ',',
        "quote":     '`',
        "search_map": {
            '=':            '{}=?',
            '!=':           '{}!=?',
            '>':            '{}>?',
            '>=':           '{}>=?',
            '<':            '{}<?',
            '<=':           '{}<=?',
            'starts_with':  '{} like binary concat(?, \'%\')',
            'ends_with':    '{} like binary concat(\'%\', ?)',
            'contains':     '{} like binary concat(\'%\', ?, \'%\')',
            'istarts_with': '{} like concat(?, \'%\')',
            'iends_with':   '{} like concat(\'%\', ?)',
            'icontains':    '{} like concat(\'%\', ?, \'%\')',
            'in':           '{} in ({})',
            'notin':        '{} not in ({})',
            'reverse_in':   '{} in ({})',
            'null':            '{} is null',
            'notnull':         '{} is not null',
            'between':         '{} between ? and ?',
            'not_starts_with': '{} not like binary concat(?, \'%\')',
            'not_contains':    '{} not like binary concat(\'%\', ?, \'%\')',
            'not_icontains':   '{} not like concat(\'%\', ?, \'%\')',
            'regexp':          '{} regexp ?',
            'iregexp':         '{} regexp ?',
        },
        "limit": 'limit {0}, {1}',
    },
    'Oracle': {
        "delimiter": ',',
        "quote":     '"',
        "search_map": {
            '=':            '{}=?',
            '!=':           '{}!=?',
            '>':            '{}>?',
            '>=':           '{}>=?',
            '<':            '{}<?',
            '<=':           '{}<=?',
            'starts_with':  '{} like ? || \'%\'',
            'ends_with':    '{} like \'%\' || ?',
            'contains':     '{} like \'%\' || ? || \'%\'',
            'istarts_with': 'regexp_like({}, \'^\' || ?, \'i\')',
            'iends_with':   'regexp_like({}, ? || \'$\', \'i\')',
            'icontains':    'regexp_like({}, ?, \'i\')',
            'in':           '{} in ({})',
            'notin':        '{} not in ({})',
            'reverse_in':   '{} in ({})',
            'null':            '{} is null',
            'notnull':         '{} is not null',
            'between':         '{} between ? and ?',
            'not_starts_with': '{} not like ? || \'%\'',
            'not_contains':    '{} not like \'%\' || ? || \'%\'',
            'not_icontains':   'not regexp_like({}, ?, \'i\')',
            'regexp':          'regexp_like({}, ?)',
            'iregexp':         'regexp_like({}, ?, \'i\')',
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

        # base_filters: always applied to every query on this datasource.
        # Use for tenant isolation, soft-delete, user scoping etc.
        # Dynamic per-call filters are passed to select() / where().
        self.base_filters = kwargs.get('base_filters', [])

        self.order        = kwargs.get('order', [])
        self.limit        = kwargs.get('limit', None)
        self.dbms         = kwargs.get('dbms', None)
        self.move         = kwargs.get('move', 'search')
        self.placeholder  = kwargs.get('placeholder', '?')
        self.fts_language = kwargs.get('fts_language', 'italian')

        if self.dbms not in DBMS_MAP:
            raise ValueError(f"Unknown dbms '{self.dbms}'. Valid: {list(DBMS_MAP)}")

    def __shim_legacy_json(self, items):
        """
        backwards compatibility, to be removed
        """
        if not items:
            return items
            
        for item in items:
            if 'name' in item and 'field' not in item:
                item['field'] = item['name']
            if 'searchcriteria' in item and 'operator' not in item:
                item['operator'] = item['searchcriteria']
            if 'search' in item and 'value' not in item:
                item['value'] = item['search']
                
            op = item.get('operator')
            if op == 'sub':
                item['operator'] = 'contains'
            elif op == 'like':
                item['operator'] = 'starts_with'
            elif op == 'ilike':
                item['operator'] = 'icontains'
                
        return items

    def _quote(self, name: str, quote: str) -> str:
        """returns a quoted string"""
        if not name:
            raise ValueError(f"field name is missing or empty")

        if '.' in name:
            parts = name.split('.')
            return f"{parts[0]}.{quote}{parts[1]}{quote}"

        return quote + name + quote

    def _build_filter(self, col: str, searchcriteria: str = "icontains", search_value=None, value_type: str = "text") -> str:
        """
        given a column name col, the type of search searchcriteria
        returns a single where statement
        """
        if searchcriteria not in DBMS_MAP[self.dbms]["search_map"]:
            searchcriteria = 'icontains'
            
        raw_statement = DBMS_MAP[self.dbms]["search_map"][searchcriteria]

        if searchcriteria in ['in', 'notin']:
            if not isinstance(search_value, (list, tuple)):
                search_value = [search_value] if search_value is not None else []
            
            if self.placeholder == '%s':
                raw_statement = raw_statement.replace('%', '%%')

            placeholders_str = ", ".join([self.placeholder] * len(search_value))
            raw_statement = raw_statement.format("{}", placeholders_str)

        elif searchcriteria == 'between':
            # value must be a list/tuple of exactly two items: [low, high]
            if not isinstance(search_value, (list, tuple)) or len(search_value) != 2:
                raise ValueError(f"'between' operator requires a list of exactly two values, got: {search_value!r}")
            if self.placeholder == '%s':
                raw_statement = raw_statement.replace('%', '%%')
            raw_statement = raw_statement.replace('?', self.placeholder)

        elif searchcriteria in ['fts', 'fts_query']:
            if self.dbms not in ['Pg']:
                raise ValueError(f"Operator '{searchcriteria}' is not supported by {self.dbms}")
            raw_statement = raw_statement.replace('italian', self.fts_language)
            if self.placeholder == '%s':
                raw_statement = raw_statement.replace('%', '%%')
            raw_statement = raw_statement.replace('?', self.placeholder)

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
            
            return f"{self.placeholder} IN ({', '.join(parsed_cols)})"
            
        else:
            if self.placeholder == '%s':
                raw_statement = raw_statement.replace('%', '%%')
            raw_statement = raw_statement.replace('?', self.placeholder)

        # gestione campi json con tipizzazione esplicita
        if self.dbms == 'Pg' and '->>' in col:
            parts = col.split('->>')
            main_column = self._quote(parts[0].strip(), DBMS_MAP[self.dbms]["quote"])
            json_key = parts[1].strip()
            
            # Eseguiamo il cast guidato esplicitamente dall'attributo del JSON
            if value_type == 'numeric':
                sql_field = f"({main_column}->>'{json_key}')::numeric"
                raw_statement = raw_statement.replace(self.placeholder, f"{self.placeholder}::numeric")
            elif value_type == 'date':
                sql_field = f"({main_column}->>'{json_key}')::date"
                raw_statement = raw_statement.replace(self.placeholder, f"{self.placeholder}::date")
            else:
                sql_field = f"{main_column}->>'{json_key}'"
                
            return raw_statement.format(sql_field)

        return raw_statement.format(self._quote(col, DBMS_MAP[self.dbms]["quote"]))

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

    def _invert_order(self, ord: str, inv: str) -> str:
        if ord not in ['asc', 'desc']:
            raise ValueError("order must be 'asc' or 'desc'")

        if inv:
            return 'desc' if ord == 'asc' else 'asc'
        return ord

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

    def where(self, **kwargs):
        # base_filters (always applied) + filters (per-call)
        all_filters = self.base_filters + kwargs.get('filters', [])

        if len(all_filters) > 0:
            q_filters = self._build_where(
                filters=all_filters,
                move=self.move,
                dbms=self.dbms
            )
            return " and " + q_filters['where'], q_filters['value']
        return "", []

    def limit_pool(self, default_pool_size=40):
        return "\n" + DBMS_MAP[self.dbms].get("limit", "").format(0, default_pool_size)

    def paginate(self, final_list, **kwargs):
        start = kwargs.get('start', self.limit.get('start', 0) if self.limit else 0)
        length = kwargs.get('length', self.limit.get('length', 5) if self.limit else 5)
        return final_list[start : start + length]

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

        # base_filters (always applied) + filters (per-call)
        all_filters = self.base_filters + kwargs.get('filters', [])
        if len(all_filters) > 0:
            q_filters = self._build_where(
                filters=all_filters,
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