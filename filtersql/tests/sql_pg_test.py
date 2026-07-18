# -*- coding: utf-8 -*-
"""
Test suite for filtersql v0.9+.
Tests SQL generation without a live DB.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import filtersql.sql as sql
from filtersql.sql import FilterSQLError, ValidationError, ConfigurationError, InvalidIdentifierError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_COLUMNS = [
    {'field': 'id'},
    {'field': 'first_name'},
    {'field': 'last_name'},
]

def make_ds(**kwargs):
    """Convenience factory — defaults to Pg with %s placeholder."""
    kwargs.setdefault('source', 'users')
    kwargs.setdefault('dbms', 'Pg')
    kwargs.setdefault('placeholder', '%s')
    return sql.Datasource(**kwargs)

def get_query(ds, **kwargs):
    """Return (query_str, values) from select()."""
    kwargs.setdefault('columns', BASE_COLUMNS)
    return ds.select(**kwargs)


# ---------------------------------------------------------------------------
# 1. Basic SELECT generation
# ---------------------------------------------------------------------------

class TestBasicSelect(unittest.TestCase):

    def test_select_all_columns(self):
        q, v = get_query(make_ds())
        self.assertIn('"id"', q)
        self.assertIn('"first_name"', q)
        self.assertIn('"last_name"', q)
        self.assertEqual(v, [])

    def test_from_clause(self):
        q, v = get_query(make_ds())
        self.assertIn('from', q.lower())
        self.assertIn('"users"', q)

    def test_raw_source_not_quoted(self):
        ds = make_ds(source='(select * from foo) sub', raw_source=True)
        q, _ = get_query(ds)
        self.assertIn('(select * from foo) sub', q)
        self.assertNotIn('"(select', q)

    def test_order_by_asc(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, _ = get_query(ds)
        self.assertIn('order by', q.lower())
        self.assertIn('"id" asc', q)

    def test_order_by_desc(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'desc'}])
        q, _ = get_query(ds)
        self.assertIn('"id" desc', q)

    def test_no_where_clause_without_filters(self):
        q, _ = get_query(make_ds())
        self.assertNotIn('where', q.lower())

    def test_dotted_field_name_quoted_correctly(self):
        """schema.table notation should quote only the column part."""
        ds = make_ds()
        q, _ = get_query(ds, columns=[{'field': 'u.first_name'}])
        self.assertIn('"u"."first_name"', q)


# ---------------------------------------------------------------------------
# 2. Filter operators — WHERE clause generation
# ---------------------------------------------------------------------------

class TestFilterOperators(unittest.TestCase):

    def _where(self, operator, value='test', field='first_name'):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': field, 'operator': operator, 'value': value}])
        return q, v

    # Equality / comparison
    def test_eq(self):
        q, v = self._where('=', 42, 'id')
        self.assertIn('"id" = %s', q)
        self.assertEqual(v, [42])

    def test_neq(self):
        q, v = self._where('!=', 42, 'id')
        self.assertIn('"id" != %s', q)

    def test_gt(self):
        q, v = self._where('>', 10, 'id')
        self.assertIn('"id" > %s', q)

    def test_gte(self):
        q, v = self._where('>=', 10, 'id')
        self.assertIn('"id" >= %s', q)

    def test_lt(self):
        q, v = self._where('<', 10, 'id')
        self.assertIn('"id" < %s', q)

    def test_lte(self):
        q, v = self._where('<=', 10, 'id')
        self.assertIn('"id" <= %s', q)

    # String matching
    def test_starts_with(self):
        q, v = self._where('starts_with', 'Jo')
        self.assertIn("like %s || chr(37)", q)
        self.assertEqual(v, ['Jo'])

    def test_ends_with(self):
        q, v = self._where('ends_with', 'son')
        self.assertIn("like chr(37) || %s", q)

    def test_contains(self):
        q, v = self._where('contains', 'oh')
        self.assertIn("like chr(37) || %s || chr(37)", q)

    def test_istarts_with(self):
        q, v = self._where('istarts_with', 'jo')
        self.assertIn('ilike', q)
        self.assertIn("|| chr(37)", q)

    def test_iends_with(self):
        q, v = self._where('iends_with', 'son')
        self.assertIn('ilike', q)
        self.assertIn("chr(37) ||", q)

    def test_icontains(self):
        q, v = self._where('icontains', 'oh')
        self.assertIn('ilike', q)
        self.assertIn("chr(37) ||", q)
        self.assertIn("|| chr(37)", q)

    # Negated string matching
    def test_not_contains(self):
        q, v = self._where('not_contains', 'oh')
        self.assertIn('not', q)
        self.assertIn('like', q)
        self.assertEqual(v, ['oh'])

    def test_not_starts_with(self):
        q, v = self._where('not_starts_with', 'Jo')
        self.assertIn('not', q)
        self.assertIn('like', q)
        self.assertEqual(v, ['Jo'])

    def test_not_icontains(self):
        q, v = self._where('not_icontains', 'oh')
        self.assertIn('not', q)
        self.assertIn('ilike', q)
        self.assertEqual(v, ['oh'])

    # NULL checks
    def test_null(self):
        q, v = self._where('null', None)
        self.assertIn('is null', q)
        self.assertEqual(v, [])

    def test_notnull(self):
        q, v = self._where('notnull', None)
        self.assertIn('is not null', q)
        self.assertEqual(v, [])

    # between
    def test_between(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'id', 'operator': 'between', 'value': [10, 20]}])
        self.assertIn('"id" between', q)
        self.assertEqual(v, [10, 20])

    def test_between_wrong_value_raises(self):
        ds = make_ds()
        with self.assertRaises(ValidationError):
            get_query(ds, filters=[{'field': 'id', 'operator': 'between', 'value': 10}])

    def test_between_wrong_length_raises(self):
        ds = make_ds()
        with self.assertRaises(ValidationError):
            get_query(ds, filters=[{'field': 'id', 'operator': 'between', 'value': [10]}])

    # IN / NOT IN
    def test_in_list(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'id', 'operator': 'in', 'value': [1, 2, 3]}])
        self.assertIn('"id" in', q)
        self.assertIn('%s, %s, %s', q)
        self.assertEqual(v, [1, 2, 3])

    def test_notin_list(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'id', 'operator': 'notin', 'value': [4, 5]}])
        self.assertIn('"id" not in', q)
        self.assertEqual(v, [4, 5])

    def test_in_single_value_scalar(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'id', 'operator': 'in', 'value': 7}])
        self.assertIn('"id" in', q)
        self.assertEqual(v, [7])

    def test_in_empty_list(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'id', 'operator': 'in', 'value': []}])
        self.assertIn('"id" in ()', q)
        self.assertEqual(v, [])

    # regexp
    def test_regexp(self):
        q, v = self._where('regexp', '^john')
        self.assertIn('~', q)
        self.assertEqual(v, ['^john'])

    def test_iregexp(self):
        q, v = self._where('iregexp', '^john')
        self.assertIn('~*', q)
        self.assertEqual(v, ['^john'])

    # reverse_in
    def test_reverse_in(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'role, status', 'operator': 'reverse_in', 'value': 'admin'}])
        self.assertIn('%s in (', q)
        self.assertIn('"role"', q)
        self.assertIn('"status"', q)

    def test_unknown_operator_raises_error(self):
        with self.assertRaises(ValidationError):
            q, v = self._where('nonexistent_op', 'foo')


# ---------------------------------------------------------------------------
# 3. OR / AND groups
# ---------------------------------------------------------------------------

class TestFilterGroups(unittest.TestCase):

    def test_or_group(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[
            {'or': [
                {'field': 'first_name', 'operator': 'icontains', 'value': 'john'},
                {'field': 'last_name',  'operator': 'icontains', 'value': 'john'},
            ]}
        ])
        self.assertIn('or', q.lower())
        self.assertIn('"first_name"', q)
        self.assertIn('"last_name"', q)
        self.assertEqual(v, ['john', 'john'])

    def test_or_group_combined_with_and(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[
            {'field': 'status', 'operator': '=', 'value': 'active'},
            {'or': [
                {'field': 'first_name', 'operator': 'icontains', 'value': 'john'},
                {'field': 'last_name',  'operator': 'icontains', 'value': 'john'},
            ]}
        ])
        self.assertIn('and', q.lower())
        self.assertIn('or', q.lower())
        self.assertEqual(v, ['active', 'john', 'john'])

    def test_and_nested_inside_or(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[
            {'or': [
                {'field': 'first_name', 'operator': '=', 'value': 'John'},
                {'and': [
                    {'field': 'last_name', 'operator': '=', 'value': 'Smith'},
                    {'field': 'id',        'operator': '>',  'value': 10},
                ]},
            ]}
        ])
        self.assertIn('or', q.lower())
        self.assertIn('and', q.lower())
        self.assertEqual(v, ['John', 'Smith', 10])

    def test_or_values_in_correct_order(self):
        """Values must match placeholder order."""
        ds = make_ds()
        q, v = get_query(ds, filters=[
            {'field': 'id', 'operator': '=', 'value': 1},
            {'or': [
                {'field': 'first_name', 'operator': '=', 'value': 'A'},
                {'field': 'last_name',  'operator': '=', 'value': 'B'},
            ]},
            {'field': 'id', 'operator': '<', 'value': 100},
        ])
        self.assertEqual(v, [1, 'A', 'B', 100])


# ---------------------------------------------------------------------------
# 4. Multiple filters combined
# ---------------------------------------------------------------------------

class TestMultipleFilters(unittest.TestCase):

    def test_two_search_filters_joined_with_and(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[
            {'field': 'first_name', 'operator': 'icontains', 'value': 'jo'},
            {'field': 'last_name',  'operator': 'icontains', 'value': 'sm'},
        ])
        self.assertIn('and', q.lower())
        self.assertEqual(v, ['jo', 'sm'])

    def test_null_and_eq_combined(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[
            {'field': 'last_name', 'operator': 'null', 'value': None},
            {'field': 'id',        'operator': '=',    'value': 1},
        ])
        self.assertIn('is null', q)
        self.assertIn('"id" = %s', q)
        self.assertEqual(v, [1])

    def test_extra_filters_in_select(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'id', 'operator': '>', 'value': 10}])
        self.assertIn('"id" > %s', q)
        self.assertEqual(v, [10])


# ---------------------------------------------------------------------------
# 5. JSONB column handling (Pg-specific)
# ---------------------------------------------------------------------------

class TestJsonbColumns(unittest.TestCase):

    def test_jsonb_icontains(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'data->>name', 'operator': 'icontains', 'value': 'jo'}])
        self.assertIn('"data"->>\'name\'', q)
        self.assertIn('ilike', q)

    def test_jsonb_eq(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'meta->>status', 'operator': '=', 'value': 'active'}])
        self.assertIn('"meta"->>\'status\'', q)
        self.assertNotIn('::numeric', q)
        self.assertNotIn('::date', q)

    def test_jsonb_numeric_gt(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'data->>age', 'operator': '>', 'value': 30, 'value_type': 'numeric'}])
        self.assertIn('::numeric', q)
        self.assertIn('"data"->>\'age\'', q)
        self.assertIn('%s::numeric', q)
        self.assertEqual(v, [30])

    def test_jsonb_date_gte(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'data->>created', 'operator': '>=', 'value': '2025-01-01', 'value_type': 'date'}])
        self.assertIn('::date', q)
        self.assertIn('%s::date', q)
        self.assertEqual(v, ['2025-01-01'])

    def test_jsonb_text_no_cast(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'data->>name', 'operator': '=', 'value': 'foo'}])
        self.assertNotIn('::numeric', q)
        self.assertNotIn('::date', q)
        self.assertEqual(v, ['foo'])


# ---------------------------------------------------------------------------
# 6. Limit / pagination
# ---------------------------------------------------------------------------

class TestLimit(unittest.TestCase):

    def test_limit_clause_present(self):
        ds = make_ds(limit={'start': 0, 'length': 10})
        q, _ = get_query(ds)
        self.assertIn('limit 10 offset 0', q)

    def test_limit_offset(self):
        ds = make_ds(limit={'start': 20, 'length': 10})
        q, _ = get_query(ds)
        self.assertIn('limit 10 offset 20', q)

    def test_no_limit_no_clause(self):
        ds = make_ds()
        q, _ = get_query(ds)
        self.assertNotIn('limit', q.lower())

    def test_limit_override_in_select(self):
        ds = make_ds(limit={'start': 0, 'length': 5})
        q, _ = get_query(ds, limit={'start': 10, 'length': 25})
        self.assertIn('limit 25 offset 10', q)


# ---------------------------------------------------------------------------
# 7. insert / update / delete
# ---------------------------------------------------------------------------

class TestInsert(unittest.TestCase):

    def test_insert_basic(self):
        ds = make_ds()
        q, v = ds.insert(values={'first_name': 'John', 'last_name': 'Smith'})
        self.assertIn('insert into', q.lower())
        self.assertIn('"first_name"', q)
        self.assertIn('"last_name"', q)
        self.assertIn('%s', q)
        self.assertEqual(v, ['John', 'Smith'])

    def test_insert_returning(self):
        ds = make_ds()
        q, v = ds.insert(values={'first_name': 'John'}, returning='id')
        self.assertIn('returning', q.lower())
        self.assertIn('"id"', q)

    def test_insert_returning_non_pg_raises(self):
        ds = sql.Datasource(source='users', dbms='SQLite')
        with self.assertRaises(ValidationError):
            ds.insert(values={'first_name': 'John'}, returning='id')

    def test_insert_empty_values_raises(self):
        ds = make_ds()
        with self.assertRaises(ValidationError):
            ds.insert(values={})

    def test_insert_returns_tuple(self):
        ds = make_ds()
        result = ds.insert(values={'first_name': 'John'})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


class TestUpdate(unittest.TestCase):

    def test_update_basic(self):
        ds = make_ds()
        q, v = ds.update(id={'id': 42}, values={'first_name': 'John'})
        self.assertIn('update', q.lower())
        self.assertIn('set', q.lower())
        self.assertIn('where', q.lower())
        self.assertIn('"first_name"', q)
        self.assertEqual(v, ['John', 42])

    def test_update_composite_key(self):
        ds = make_ds()
        q, v = ds.update(
            id     = {'id': 42, 'tenant_id': 1},
            values = {'first_name': 'John'},
        )
        self.assertIn('"id"', q)
        self.assertIn('"tenant_id"', q)
        self.assertEqual(v, ['John', 42, 1])

    def test_update_set_values_before_where_values(self):
        """SET values must come before WHERE values in the values list."""
        ds = make_ds()
        q, v = ds.update(
            id     = {'id': 99},
            values = {'first_name': 'Alice', 'last_name': 'Smith'},
        )
        self.assertEqual(v[0], 'Alice')
        self.assertEqual(v[1], 'Smith')
        self.assertEqual(v[2], 99)

    def test_update_empty_id_raises(self):
        ds = make_ds()
        with self.assertRaises(ValidationError):
            ds.update(id={}, values={'first_name': 'John'})

    def test_update_empty_values_raises(self):
        ds = make_ds()
        with self.assertRaises(ValidationError):
            ds.update(id={'id': 42}, values={})

    def test_update_returns_tuple(self):
        ds = make_ds()
        result = ds.update(id={'id': 1}, values={'first_name': 'John'})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


class TestDelete(unittest.TestCase):

    def test_delete_basic(self):
        ds = make_ds()
        q, v = ds.delete(id={'id': 42})
        self.assertIn('delete from', q.lower())
        self.assertIn('where', q.lower())
        self.assertIn('"id"', q)
        self.assertEqual(v, [42])

    def test_delete_composite_key(self):
        ds = make_ds()
        q, v = ds.delete(id={'id': 42, 'tenant_id': 1})
        self.assertIn('"id"', q)
        self.assertIn('"tenant_id"', q)
        self.assertEqual(v, [42, 1])

    def test_delete_empty_id_raises(self):
        ds = make_ds()
        with self.assertRaises(ValidationError):
            ds.delete(id={})

    def test_delete_returns_tuple(self):
        ds = make_ds()
        result = ds.delete(id={'id': 1})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# 8. Error / invalid input handling
# ---------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):

    def test_invalid_order_direction_raises(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'sideways'}])
        with self.assertRaises(ValidationError):
            get_query(ds)

    def test_invalid_dbms_raises(self):
        with self.assertRaises(ConfigurationError):
            sql.Datasource(source='t', dbms='FakeDB')

    def test_missing_field_in_filter_raises(self):
        ds = make_ds()
        with self.assertRaises(sql.ValidationError):
            get_query(ds, filters=[{'operator': '=', 'value': 1}])

    def test_placeholder_percent_s_escaped(self):
        """When placeholder is %s, it appears in the query as the parameter marker."""
        ds = make_ds()
        q, _ = get_query(ds, filters=[{'field': 'first_name', 'operator': 'icontains', 'value': 'jo'}])
        self.assertIn('%s', q)
        self.assertIn("ilike", q)


# ---------------------------------------------------------------------------
# 9. where() helper
# ---------------------------------------------------------------------------

class TestWhere(unittest.TestCase):

    def test_returns_empty_string_with_no_filters(self):
        ds = make_ds()
        clause, v = ds.where()
        self.assertEqual(clause, '')
        self.assertEqual(v, [])

    def test_returns_clause_without_and_prefix(self):
        ds = make_ds()
        clause, v = ds.where(filters=[{'field': 'id', 'operator': '=', 'value': 5}])
        self.assertFalse(clause.strip().upper().startswith('AND'))
        self.assertEqual(v, [5])

    def test_combines_multiple_filters(self):
        ds = make_ds()
        clause, v = ds.where(filters=[
            {'field': 'id',        'operator': '>',        'value': 0},
            {'field': 'last_name', 'operator': 'icontains','value': 'sm'},
        ])
        self.assertIn('"id" > %s', clause)
        self.assertIn('ilike', clause)
        self.assertEqual(v, [0, 'sm'])


# ---------------------------------------------------------------------------
# 10. Full-text search (Pg only)
# ---------------------------------------------------------------------------

class TestFts(unittest.TestCase):

    def test_fts_generates_tsquery(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'fc.tsv_content', 'operator': 'fts', 'value': 'contratti'}])
        self.assertIn('@@', q)
        self.assertIn('websearch_to_tsquery', q)
        self.assertIn('"fc"."tsv_content"', q)
        self.assertEqual(v, ['contratti'])

    def test_fts_default_language(self):
        ds = make_ds()
        q, _ = get_query(ds, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contratti'}])
        self.assertIn('english', q)

    def test_fts_custom_language(self):
        ds = make_ds(fts_language='italian')
        q, _ = get_query(ds, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contracts'}])
        self.assertIn('italian', q)
        self.assertNotIn('english', q)

    def test_fts_query_operator(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'fm.oggetto', 'operator': 'fts_query', 'value': 'contratti'}])
        self.assertIn('to_tsvector', q)
        self.assertIn('coalesce', q)
        self.assertIn('"fm"."oggetto"', q)
        self.assertIn('@@', q)
        self.assertEqual(v, ['contratti'])

    def test_fts_not_supported_on_sqlite(self):
        ds = sql.Datasource(source='docs', dbms='SQLite')
        with self.assertRaises(ValidationError):
            get_query(ds, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contratti'}])

    def test_fts_combined_with_deterministic_filters(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[
            {'field': 'doc_type', 'operator': '=',   'value': 'CONTRATTO'},
            {'field': 'tsv',      'operator': 'fts',  'value': 'contratti'},
        ])
        self.assertIn('"doc_type" = %s', q)
        self.assertIn('@@', q)
        self.assertIn('and', q.lower())
        self.assertEqual(v, ['CONTRATTO', 'contratti'])



# ---------------------------------------------------------------------------
# 11. _quote — deep tests
# ---------------------------------------------------------------------------

class TestQuote(unittest.TestCase):
    """Tests for _quote() — the identifier quoting method."""

    def _q(self, name, dbms='Pg'):
        ds = sql.Datasource(source='t', dbms=dbms)
        quote = sql.DBMS_MAP[dbms]['quote']
        return ds._quote(name, quote)

    # Basic quoting
    def test_simple_field_pg(self):
        self.assertEqual(self._q('first_name'), '"first_name"')

    def test_simple_field_mysql(self):
        self.assertEqual(self._q('first_name', 'mysql'), '`first_name`')

    def test_simple_field_sqlite(self):
        self.assertEqual(self._q('id', 'SQLite'), '"id"')

    def test_simple_field_oracle(self):
        self.assertEqual(self._q('id', 'Oracle'), '"id"')

    # Schema prefix
    def test_schema_prefix(self):
        self.assertEqual(self._q('m.doc_type'), '"m"."doc_type"')

    def test_schema_prefix_mysql(self):
        self.assertEqual(self._q('m.doc_type', 'mysql'), '`m`.`doc_type`')

    def test_schema_prefix_preserved_unquoted(self):
        """Schema part should NOT be quoted, only column part."""
        result = self._q('public.users')
        self.assertIn('"public".', result)
        self.assertNotIn('public.', result)
        self.assertIn('"users"', result)

    # JSONB paths
    def test_jsonb_path(self):
        result = self._q('data->>name')
        self.assertIn('"data"', result)
        self.assertIn("'name'", result)
        self.assertIn('->>', result)

    def test_jsonb_path_with_schema(self):
        """JSONB with schema prefix — handled by _build_condition not _quote."""
        result = self._q('m.attributes->>supplier')
        self.assertIn('"m".', result)
        self.assertIn('attributes', result)

    def test_jsonb_path_spaces_stripped(self):
        """Spaces around ->> should be handled gracefully."""
        result = self._q('data->>name')
        self.assertNotIn(' ', result)

    # Whitespace
    def test_whitespace_stripped(self):
        self.assertEqual(self._q('  first_name  '), '"first_name"')

    def test_whitespace_in_schema_prefix_stripped(self):
        self.assertEqual(self._q('  m . first_name  '), '"m"."first_name"')

    # Error cases
    def test_empty_string_raises(self):
        with self.assertRaises(InvalidIdentifierError):
            self._q('')

    def test_none_raises(self):
        ds = sql.Datasource(source='t', dbms='Pg')
        with self.assertRaises(InvalidIdentifierError):
            ds._quote(None, '"')

    def test_whitespace_only_raises(self):
        with self.assertRaises(InvalidIdentifierError):
            self._q('   ')


# ---------------------------------------------------------------------------
# 12. _quote integration — how it appears in generated SQL
# ---------------------------------------------------------------------------

class TestQuoteInSQL(unittest.TestCase):
    """Tests that _quote produces correct output inside full queries."""

    def test_schema_field_in_select(self):
        ds = make_ds()
        q, _ = get_query(ds, columns=[{'field': 'm.doc_type'}])
        self.assertIn('"m"."doc_type"', q)

    def test_schema_field_in_filter(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'm.doc_type', 'operator': '=', 'value': 'CONTRACT'}])
        self.assertIn('"m"."doc_type" = %s', q)

    def test_schema_field_in_order(self):
        ds = make_ds(order=[{'field': 'm.doc_date', 'order': 'desc'}])
        q, _ = get_query(ds)
        self.assertIn('"m"."doc_date" desc', q)

    def test_schema_field_in_update_id(self):
        ds = make_ds()
        q, v = ds.update(id={'m.id': 42}, values={'first_name': 'John'})
        self.assertIn('"m"."id"', q)

    def test_schema_field_in_insert(self):
        ds = make_ds()
        q, v = ds.insert(values={'m.first_name': 'John'})
        self.assertIn('"m"."first_name"', q)

    def test_mysql_backtick_in_select(self):
        ds = sql.Datasource(source='users', dbms='mysql')
        q, _ = ds.select(columns=[{'field': 'first_name'}])
        self.assertIn('`first_name`', q)

    def test_mysql_backtick_in_filter(self):
        ds = sql.Datasource(source='users', dbms='mysql')
        q, v = ds.select(
            columns=[{'field': 'id'}],
            filters=[{'field': 'first_name', 'operator': '=', 'value': 'John'}]
        )
        self.assertIn('`first_name` = ?', q)

    def test_source_quoted_correctly(self):
        ds = make_ds(source='my_table')
        q, _ = get_query(ds)
        self.assertIn('"my_table"', q)

    def test_source_with_schema_quoted_correctly(self):
        ds = make_ds(source='public.documents')
        q, _ = get_query(ds)
        self.assertIn('"public"."documents"', q)


# ---------------------------------------------------------------------------
# 13. debug() — deep tests
# ---------------------------------------------------------------------------

class TestDebug(unittest.TestCase):

    def test_debug_replaces_string_value(self):
        ds = make_ds()
        q, v = ds.where(filters=[{'field': 'first_name', 'operator': '=', 'value': 'John'}])
        debug = ds.debug(q, v)
        self.assertIn("'John'", debug)
        self.assertNotIn('%s', debug)

    def test_debug_replaces_int_value(self):
        ds = make_ds()
        q, v = ds.where(filters=[{'field': 'id', 'operator': '=', 'value': 42}])
        debug = ds.debug(q, v)
        self.assertIn('42', debug)
        self.assertNotIn('%s', debug)

    def test_debug_replaces_none_with_null(self):
        ds = make_ds()
        q, v = ds.where(filters=[{'field': 'deleted_at', 'operator': '=', 'value': None}])
        debug = ds.debug(q, v)
        self.assertIn('null', debug)

    def test_debug_escapes_single_quotes(self):
        """Single quotes in string values must be escaped."""
        ds = make_ds()
        q, v = ds.where(filters=[{'field': 'name', 'operator': '=', 'value': "O'Brien"}])
        debug = ds.debug(q, v)
        self.assertIn("O''Brien", debug)

    def test_debug_replaces_multiple_values_in_order(self):
        ds = make_ds()
        q, v = ds.where(filters=[
            {'field': 'first_name', 'operator': '=', 'value': 'John'},
            {'field': 'last_name',  'operator': '=', 'value': 'Smith'},
        ])
        debug = ds.debug(q, v)
        self.assertIn("'John'", debug)
        self.assertIn("'Smith'", debug)
        self.assertNotIn('%s', debug)

    def test_debug_with_question_mark_placeholder(self):
        ds = sql.Datasource(source='users', dbms='SQLite', placeholder='?')
        q, v = ds.where(filters=[{'field': 'id', 'operator': '=', 'value': 1}])
        debug = ds.debug(q, v)
        self.assertIn('1', debug)
        self.assertNotIn('?', debug)


# ---------------------------------------------------------------------------
# 14. _invert_order — deep tests
# ---------------------------------------------------------------------------

class TestInvertOrder(unittest.TestCase):

    def _inv(self, ord, inv):
        ds = make_ds()
        return ds._invert_order(ord, inv)

    def test_asc_not_inverted(self):
        self.assertEqual(self._inv('asc', False), 'asc')

    def test_desc_not_inverted(self):
        self.assertEqual(self._inv('desc', False), 'desc')

    def test_asc_inverted(self):
        self.assertEqual(self._inv('asc', True), 'desc')

    def test_desc_inverted(self):
        self.assertEqual(self._inv('desc', True), 'asc')

    def test_invalid_order_raises(self):
        with self.assertRaises(ValidationError):
            self._inv('sideways', False)

    def test_invalid_order_even_when_inverted_raises(self):
        with self.assertRaises(ValidationError):
            self._inv('ASCENDING', True)

    def test_backwards_move_inverts_order_in_select(self):
        ds = make_ds(direction='prev', order=[{'field': 'id', 'order': 'asc'}])
        q, _ = get_query(ds)
        self.assertIn('"id" desc', q)

    def test_forwards_move_does_not_invert(self):
        ds = make_ds(direction='next', order=[{'field': 'id', 'order': 'asc'}])
        q, _ = get_query(ds)
        self.assertIn('"id" asc', q)


# ---------------------------------------------------------------------------
# 15. _resolve_source — deep tests
# ---------------------------------------------------------------------------

class TestResolveSource(unittest.TestCase):

    def test_simple_source_quoted(self):
        ds = make_ds(source='users')
        self.assertEqual(ds._resolve_source(), '"users"')

    def test_raw_source_not_quoted(self):
        ds = make_ds(source='(select * from foo) sub', raw_source=True)
        self.assertEqual(ds._resolve_source(), '(select * from foo) sub')

    def test_schema_source_quoted(self):
        ds = make_ds(source='public.users')
        self.assertEqual(ds._resolve_source(), '"public"."users"')

    def test_source_appears_correctly_in_select(self):
        ds = make_ds(source='documents')
        q, _ = get_query(ds)
        self.assertIn('"documents"', q)

    def test_source_appears_correctly_in_insert(self):
        ds = make_ds(source='documents')
        q, _ = ds.insert(values={'title': 'Test'})
        self.assertIn('"documents"', q)

    def test_source_appears_correctly_in_update(self):
        ds = make_ds(source='documents')
        q, _ = ds.update(id={'id': 1}, values={'title': 'Test'})
        self.assertIn('"documents"', q)

    def test_source_appears_correctly_in_delete(self):
        ds = make_ds(source='documents')
        q, _ = ds.delete(id={'id': 1})
        self.assertIn('"documents"', q)

    def test_mysql_source_uses_backtick(self):
        ds = sql.Datasource(source='users', dbms='mysql')
        self.assertEqual(ds._resolve_source(), '`users`')


# ---------------------------------------------------------------------------
# 16. Multi-DBMS operator coverage
# ---------------------------------------------------------------------------

class TestMultiDBMS(unittest.TestCase):
    """Verify key operators work correctly across all DBMS."""

    def _select(self, dbms, filters):
        ds = sql.Datasource(source='t', dbms=dbms)
        return ds.select(columns=[{'field': 'id'}], filters=filters)

    def test_icontains_sqlite_uses_like(self):
        q, _ = self._select('SQLite', [{'field': 'name', 'operator': 'icontains', 'value': 'jo'}])
        self.assertIn('like', q)
        self.assertNotIn('ilike', q)

    def test_icontains_pg_uses_ilike(self):
        q, _ = self._select('Pg', [{'field': 'name', 'operator': 'icontains', 'value': 'jo'}])
        self.assertIn('ilike', q)

    def test_contains_sqlite_uses_glob(self):
        q, _ = self._select('SQLite', [{'field': 'name', 'operator': 'contains', 'value': 'jo'}])
        self.assertIn('glob', q)

    def test_contains_pg_uses_like(self):
        q, _ = self._select('Pg', [{'field': 'name', 'operator': 'contains', 'value': 'jo'}])
        self.assertIn('like', q)
        self.assertNotIn('glob', q)

    def test_regexp_pg(self):
        q, _ = self._select('Pg', [{'field': 'name', 'operator': 'regexp', 'value': '^jo'}])
        self.assertIn('~', q)
        self.assertNotIn('regexp', q)

    def test_regexp_sqlite(self):
        q, _ = self._select('SQLite', [{'field': 'name', 'operator': 'regexp', 'value': '^jo'}])
        self.assertIn('regexp', q)

    def test_regexp_mysql(self):
        q, _ = self._select('mysql', [{'field': 'name', 'operator': 'regexp', 'value': '^jo'}])
        self.assertIn('regexp', q)

    def test_limit_pg_offset(self):
        ds = sql.Datasource(source='t', dbms='Pg')
        q, _ = ds.select(columns=[{'field': 'id'}], limit={'start': 10, 'length': 5})
        self.assertIn('limit 5 offset 10', q)

    def test_limit_sqlite_comma(self):
        ds = sql.Datasource(source='t', dbms='SQLite')
        q, _ = ds.select(columns=[{'field': 'id'}], limit={'start': 10, 'length': 5})
        self.assertIn('limit 10, 5', q)

    def test_mysql_backtick_quote(self):
        ds = sql.Datasource(source='users', dbms='mysql')
        q, _ = ds.select(columns=[{'field': 'first_name'}])
        self.assertIn('`first_name`', q)
        self.assertNotIn('"first_name"', q)

    def test_fts_raises_on_sqlite(self):
        with self.assertRaises(ValidationError):
            self._select('SQLite', [{'field': 'tsv', 'operator': 'fts', 'value': 'test'}])

    def test_fts_raises_on_oracle(self):
        with self.assertRaises(ValidationError):
            self._select('Oracle', [{'field': 'tsv', 'operator': 'fts', 'value': 'test'}])


# ---------------------------------------------------------------------------
# 17. scope
# ---------------------------------------------------------------------------

class TestScope(unittest.TestCase):

    def test_scope_applied_to_select(self):
        ds = make_ds(scope={'tenant_id': 42})
        q, v = get_query(ds)
        self.assertIn('"tenant_id" = %s', q)
        self.assertIn(42, v)

    def test_scope_combined_with_filters(self):
        ds = make_ds(scope={'tenant_id': 42})
        q, v = get_query(ds, filters=[{'field': 'status', 'operator': '=', 'value': 'active'}])
        self.assertIn('"tenant_id" = %s', q)
        self.assertIn('"status" = %s', q)
        self.assertIn(42, v)
        self.assertIn('active', v)

    def test_scope_applied_to_where(self):
        ds = make_ds(scope={'tenant_id': 42})
        clause, v = ds.where()
        self.assertIn('"tenant_id" = %s', clause)
        self.assertIn(42, v)

    def test_scope_applied_to_update(self):
        ds = make_ds(scope={'tenant_id': 42})
        q, v = ds.update(id={'id': 1}, values={'title': 'Test'})
        self.assertIn('"tenant_id" = %s', q)
        self.assertIn(42, v)

    def test_scope_applied_to_delete(self):
        ds = make_ds(scope={'tenant_id': 42})
        q, v = ds.delete(id={'id': 1})
        self.assertIn('"tenant_id" = %s', q)
        self.assertIn(42, v)

    def test_scope_applied_to_insert(self):
        ds = make_ds(scope={'tenant_id': 42})
        q, v = ds.insert(values={'title': 'Test'})
        self.assertIn('"tenant_id"', q)
        self.assertIn(42, v)

    def test_scope_does_not_mutate_caller_filters(self):
        ds = make_ds(scope={'tenant_id': 42})
        caller_filters = [{'field': 'status', 'operator': '=', 'value': 'active'}]
        original_length = len(caller_filters)
        get_query(ds, filters=caller_filters)
        self.assertEqual(len(caller_filters), original_length)

    def test_multiple_scope_fields(self):
        ds = make_ds(scope={'tenant_id': 42, 'company_id': 3})
        q, v = get_query(ds)
        self.assertIn('"tenant_id" = %s', q)
        self.assertIn('"company_id" = %s', q)

    def test_empty_scope_no_extra_filters(self):
        ds = make_ds(scope={})
        q, v = get_query(ds)
        self.assertNotIn('where', q.lower())
        self.assertEqual(v, [])

# ---------------------------------------------------------------------------
# 19. filtersql() convenience function
# ---------------------------------------------------------------------------

class TestFiltersqlFunction(unittest.TestCase):

    def test_select_action(self):
        q, v = sql.filtersql(
            payload={
                'action': 'select',
                'source': 'users',
                'columns': [{'field': 'id'}, {'field': 'first_name'}],
                'filters': [{'field': 'id', 'operator': '=', 'value': 1}],
            },
            dbms='Pg',
            placeholder='%s',
        )
        self.assertIn('select', q.lower())
        self.assertIn('"users"', q)
        self.assertIn('"id" = %s', q)
        self.assertEqual(v, [1])

    def test_insert_action(self):
        q, v = sql.filtersql(
            payload={
                'action': 'insert',
                'source': 'users',
                'values': {'first_name': 'John'},
            },
            dbms='Pg',
            placeholder='%s',
        )
        self.assertIn('insert into', q.lower())
        self.assertEqual(v, ['John'])

    def test_update_action(self):
        q, v = sql.filtersql(
            payload={
                'action': 'update',
                'source': 'users',
                'id': {'id': 42},
                'values': {'first_name': 'John'},
            },
            dbms='Pg',
            placeholder='%s',
        )
        self.assertIn('update', q.lower())
        self.assertIn('set', q.lower())
        self.assertEqual(v, ['John', 42])

    def test_delete_action(self):
        q, v = sql.filtersql(
            payload={
                'action': 'delete',
                'source': 'users',
                'id': {'id': 42},
            },
            dbms='Pg',
            placeholder='%s',
        )
        self.assertIn('delete from', q.lower())
        self.assertEqual(v, [42])

    def test_missing_source_raises(self):
        with self.assertRaises(ValidationError):
            sql.filtersql(payload={'action': 'select'}, dbms='Pg')

    def test_invalid_action_raises(self):
        with self.assertRaises(ValidationError):
            sql.filtersql(payload={'action': 'drop', 'source': 'users'}, dbms='Pg')

    def test_scope_applied_via_function(self):
        q, v = sql.filtersql(
            payload={
                'action': 'select',
                'source': 'users',
                'columns': [{'field': 'id'}],
            },
            dbms='Pg',
            placeholder='%s',
            scope={'tenant_id': 42},
        )
        self.assertIn('"tenant_id" = %s', q)
        self.assertIn(42, v)

    def test_case_insensitive_action(self):
        q, v = sql.filtersql(
            payload={
                'action': 'SELECT',
                'source': 'users',
                'columns': [{'field': 'id'}],
            },
            dbms='Pg',
        )
        self.assertIn('select', q.lower())

# ---------------------------------------------------------------------------
# 18. Cursor Pagination (type='move', seek/next/prev)
# ---------------------------------------------------------------------------

class TestCursorPagination(unittest.TestCase):
    """Test keyset pagination with type='move' filters."""

    def test_next_single_column(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = get_query(ds, 
            filters=[{'field': 'id', 'type': 'move', 'value': 100}],
            direction='next'
        )
        self.assertIn('"id" > %s', q)
        self.assertEqual(v, [100])

    def test_prev_single_column(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = get_query(ds,
            filters=[{'field': 'id', 'type': 'move', 'value': 100}],
            direction='prev'
        )
        self.assertIn('"id" < %s', q)
        self.assertEqual(v, [100])

    def test_seek_single_column(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = get_query(ds,
            filters=[{'field': 'id', 'type': 'move', 'value': 100}],
            direction='seek'
        )
        self.assertIn('"id" = %s', q)
        self.assertEqual(v, [100])

    def test_next_two_column_composite(self):
        ds = make_ds(order=[
            {'field': 'last_name', 'order': 'asc'},
            {'field': 'first_name', 'order': 'asc'}
        ])
        q, v = get_query(ds,
            filters=[
                {'field': 'last_name', 'type': 'move', 'value': 'Smith'},
                {'field': 'first_name', 'type': 'move', 'value': 'John'}
            ],
            direction='next'
        )
        # Expected: (last_name = 'Smith' AND first_name > 'John') OR (last_name > 'Smith')
        self.assertIn('"last_name" = %s', q)
        self.assertIn('"first_name" > %s', q)
        self.assertIn(' or ', q)
        self.assertEqual(v, ['Smith', 'John', 'Smith'])

    def test_prev_two_column_composite(self):
        ds = make_ds(order=[
            {'field': 'last_name', 'order': 'asc'},
            {'field': 'first_name', 'order': 'asc'}
        ])
        q, v = get_query(ds,
            filters=[
                {'field': 'last_name', 'type': 'move', 'value': 'Smith'},
                {'field': 'first_name', 'type': 'move', 'value': 'John'}
            ],
            direction='prev'
        )
        # Expected: (last_name = 'Smith' AND first_name < 'John') OR (last_name < 'Smith')
        self.assertIn('"last_name" = %s', q)
        self.assertIn('"first_name" < %s', q)
        self.assertIn(' or ', q)
        self.assertEqual(v, ['Smith', 'John', 'Smith'])

    def test_next_three_column_composite(self):
        ds = make_ds(order=[
            {'field': 'last_name', 'order': 'asc'},
            {'field': 'first_name', 'order': 'asc'},
            {'field': 'id', 'order': 'asc'}
        ])
        q, v = get_query(ds,
            filters=[
                {'field': 'last_name', 'type': 'move', 'value': 'Smith'},
                {'field': 'first_name', 'type': 'move', 'value': 'John'},
                {'field': 'id', 'type': 'move', 'value': 100}
            ],
            direction='next'
        )
        # Expected: (last_name = 'Smith' AND first_name = 'John' AND id > 100) 
        #         OR (last_name = 'Smith' AND first_name > 'John') 
        #         OR (last_name > 'Smith')
        self.assertIn('"last_name" = %s', q)
        self.assertIn('"first_name" = %s', q)
        self.assertIn('"id" > %s', q)
        self.assertIn(' or ', q)
        self.assertEqual(v, ['Smith', 'John', 100, 'Smith', 'John', 'Smith'])

    def test_cursor_with_search_filters(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = get_query(ds,
            filters=[
                {'field': 'id', 'type': 'move', 'value': 100},
                {'field': 'status', 'operator': '=', 'value': 'active'},
                {'field': 'name', 'operator': 'icontains', 'value': 'john'}
            ],
            direction='next'
        )
        self.assertIn('"id" > %s', q)
        self.assertIn('"status" = %s', q)
        self.assertIn('ilike', q)
        self.assertEqual(v, [100, 'active', 'john'])

    def test_cursor_with_order_direction_inversion(self):
        """When direction='prev', order should be inverted."""
        ds = make_ds(
            order=[{'field': 'id', 'order': 'asc'}],
            direction='prev'
        )
        q, v = get_query(ds,
            filters=[{'field': 'id', 'type': 'move', 'value': 100}]
        )
        self.assertIn('"id" desc', q)  # Order inverted for prev
        self.assertIn('"id" < %s', q)     # And condition uses <

    def test_seek_uses_equality_not_inequality(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = get_query(ds,
            filters=[{'field': 'id', 'type': 'move', 'value': 100}],
            direction='seek'
        )
        self.assertNotIn('>', q)
        self.assertNotIn('<', q)
        self.assertIn('=', q)

    def test_seek_composite(self):
        ds = make_ds(order=[
            {'field': 'last_name', 'order': 'asc'},
            {'field': 'first_name', 'order': 'asc'}
        ])
        q, v = get_query(ds,
            filters=[
                {'field': 'last_name', 'type': 'move', 'value': 'Smith'},
                {'field': 'first_name', 'type': 'move', 'value': 'John'}
            ],
            direction='seek'
        )
        self.assertIn('"last_name" = %s', q)
        self.assertIn('"first_name" = %s', q)
        self.assertNotIn(' or ', q)  # AND for seek
        self.assertEqual(v, ['Smith', 'John'])

    def test_cursor_values_order_preserved(self):
        """Values must match the order of placeholders."""
        ds = make_ds(order=[
            {'field': 'last_name', 'order': 'asc'},
            {'field': 'first_name', 'order': 'asc'}
        ])
        q, v = get_query(ds,
            filters=[
                {'field': 'last_name', 'type': 'move', 'value': 'Smith'},
                {'field': 'first_name', 'type': 'move', 'value': 'John'},
                {'field': 'status', 'operator': '=', 'value': 'active'}
            ],
            direction='next'
        )
        # Values should be: ['Smith', 'John', 'Smith', 'active']
        # Because: (last_name = 'Smith' AND first_name > 'John') OR (last_name > 'Smith')
        self.assertEqual(v[0], 'Smith')  # prefix
        self.assertEqual(v[1], 'John')   # current inequality
        self.assertEqual(v[2], 'Smith')  # second OR condition
        self.assertEqual(v[3], 'active') # search filter

    def test_missing_order_uses_default_asc(self):
        ds = make_ds()  # No order specified
        q, v = get_query(ds,
            filters=[{'field': 'id', 'type': 'move', 'value': 100}],
            direction='next'
        )
        # Should still work with default order
        self.assertIn('"id" > %s', q)

    def test_cursor_with_null_values(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = get_query(ds,
            filters=[
                {'field': 'id', 'type': 'move', 'value': 100},
                {'field': 'deleted_at', 'operator': 'null', 'value': None}
            ],
            direction='next'
        )
        self.assertIn('"id" > %s', q)
        self.assertIn('is null', q)
        self.assertEqual(v, [100])  # null operators don't add values

    def test_invalid_direction_raises(self):
        ds = make_ds()
        with self.assertRaises(ValidationError):
            get_query(ds,
                filters=[{'field': 'id', 'type': 'move', 'value': 100}],
                direction='invalid'
            )

class TestMySQLFts(unittest.TestCase):
    """Test MySQL FTS operators."""

    def test_mysql_fts(self):
        ds = sql.Datasource(source='posts', dbms='mysql')
        q, v = ds.select(
            columns=[{'field': 'id'}],
            filters=[{'field': 'content', 'operator': 'fts', 'value': 'search terms'}]
        )
        self.assertIn('match(`content`)', q)
        self.assertIn('against(? in boolean mode)', q)
        self.assertEqual(v, ['search terms'])

    def test_mysql_fts_query(self):
        ds = sql.Datasource(source='posts', dbms='mysql')
        q, v = ds.select(
            columns=[{'field': 'id'}],
            filters=[{'field': 'content', 'operator': 'fts_query', 'value': 'search'}]
        )
        self.assertIn('match(`content`)', q)
        self.assertIn('against(? in boolean mode)', q)
        self.assertEqual(v, ['search'])

    def test_mysql_fts_combined_with_other_filters(self):
        ds = sql.Datasource(source='posts', dbms='mysql')
        q, v = ds.select(
            columns=[{'field': 'id'}],
            filters=[
                {'field': 'status', 'operator': '=', 'value': 'published'},
                {'field': 'content', 'operator': 'fts', 'value': 'mysql search'}
            ]
        )
        self.assertIn('`status` = ?', q)
        self.assertIn('match(`content`)', q)
        self.assertEqual(v, ['published', 'mysql search'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
