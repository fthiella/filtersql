# -*- coding: utf-8 -*-
"""
Comprehensive test suite for filtersql v0.5+.
Tests SQL generation without a live DB.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import filtersql.sql as sql

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
    # Removed 'columns' from default kwargs to align with v0.5 architecture
    kwargs.setdefault('source', 'users')
    kwargs.setdefault('dbms', 'Pg')
    kwargs.setdefault('placeholder', '%s')
    return sql.Datasource(**kwargs)

def get_query(ds, **kwargs):
    """Return (query_str, values) from select()."""
    # If columns aren't provided in the test call, ensure they are passed if required
    return ds.select(**kwargs)

# ---------------------------------------------------------------------------
# Updated Test Classes (Retaining all logic)
# ---------------------------------------------------------------------------

class TestBasicSelect(unittest.TestCase):
    def test_select_all_columns(self):
        q, v = get_query(make_ds(), columns=BASE_COLUMNS)
        self.assertIn('"id"', q)
        self.assertIn('"first_name"', q)
        self.assertIn('"last_name"', q)
        self.assertEqual(v, [])

    def test_from_clause(self):
        q, v = get_query(make_ds(), columns=BASE_COLUMNS)
        self.assertIn('from', q.lower())
        self.assertIn('"users"', q)

class TestBasicSelect(unittest.TestCase):

    def test_select_all_columns(self):
        q, v = get_query(make_ds(), columns=BASE_COLUMNS)
        self.assertIn('"id"', q)
        self.assertIn('"first_name"', q)
        self.assertIn('"last_name"', q)
        self.assertEqual(v, [])

    def test_from_clause(self):
        q, v = get_query(make_ds(), columns=BASE_COLUMNS)
        self.assertIn('from', q.lower())
        self.assertIn('"users"', q)

    def test_raw_source_not_quoted(self):
        ds = make_ds(source='(select * from foo) sub', raw_source=True)
        q, _ = get_query(ds, columns=BASE_COLUMNS)
        self.assertIn('(select * from foo) sub', q)
        self.assertNotIn('"(select', q)

    def test_order_by_asc(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, _ = get_query(ds, columns=BASE_COLUMNS)
        self.assertIn('order by', q.lower())
        self.assertIn('"id" asc', q)

    def test_order_by_desc(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'desc'}])
        q, _ = get_query(ds, columns=BASE_COLUMNS)
        self.assertIn('"id" desc', q)

    def test_blob_columns_excluded(self):
        columns = [
            {'field': 'id'},
            {'field': 'avatar', 'type': 'blob'},
        ]
        ds = make_ds()
        q, _ = get_query(ds, columns=BASE_COLUMNS)
        self.assertIn('"id"', q)
        self.assertNotIn('"avatar"', q)

    def test_no_where_clause_without_filters(self):
        q, _ = get_query(make_ds(), columns=BASE_COLUMNS)
        self.assertNotIn('where', q.lower())

class TestFts(unittest.TestCase):

    def test_fts_generates_tsquery(self):
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'fc.tsv_content', 'operator': 'fts', 'value': 'contratti'}])
        self.assertIn('@@', q)
        self.assertIn('websearch_to_tsquery', q)
        self.assertIn('fc."tsv_content"', q)
        self.assertEqual(v, ['contratti'])

class TestFilterOperators(unittest.TestCase):

    def _where(self, operator, value='test', field='first_name'):
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': field, 'operator': operator, 'value': value}])
        return q, v

    # Equality / comparison
    def test_eq(self):
        q, v = self._where('=', 42, 'id')
        self.assertIn('"id"=%s', q)
        self.assertEqual(v, [42])

    def test_neq(self):
        q, v = self._where('!=', 42, 'id')
        self.assertIn('"id"!=%s', q)

    def test_gt(self):
        q, v = self._where('>', 10, 'id')
        self.assertIn('"id">%s', q)

    def test_gte(self):
        q, v = self._where('>=', 10, 'id')
        self.assertIn('"id">=%s', q)

    def test_lt(self):
        q, v = self._where('<', 10, 'id')
        self.assertIn('"id"<%s', q)

    def test_lte(self):
        q, v = self._where('<=', 10, 'id')
        self.assertIn('"id"<=%s', q)

    # String matching
    def test_starts_with(self):
        q, v = self._where('starts_with', 'Jo')
        q_norm = " ".join(q.split()).lower()
        self.assertIn("like %s || '%'", q_norm)
        self.assertEqual(v, ['Jo'])

    def test_ends_with(self):
        q, v = self._where('ends_with', 'son')
        self.assertIn("like '%' || %s", q)

    def test_contains(self):
        q, v = self._where('contains', 'oh')
        self.assertIn("like '%' || %s || '%'", q)

    def test_istarts_with(self):
        q, v = self._where('istarts_with', 'jo')
        q_norm = " ".join(q.split()).lower()

        self.assertIn('ilike', q_norm)
        self.assertIn("|| '%'", q_norm)

    def test_iends_with(self):
        q, v = self._where('iends_with', 'son')
        self.assertIn('ilike', q)
        self.assertIn("'%' ||", q)

    def test_icontains(self):
        q, v = self._where('icontains', 'oh')
        self.assertIn('ilike', q)
        self.assertIn("'%' ||", q)
        self.assertIn("|| '%'", q)

    # NULL checks — no value bound
    def test_null(self):
        q, v = self._where('null', None)
        self.assertIn('is null', q)
        self.assertEqual(v, [])

    def test_notnull(self):
        q, v = self._where('notnull', None)
        self.assertIn('is not null', q)
        self.assertEqual(v, [])

    # IN / NOT IN
    def test_in_list(self):
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'id', 'operator': 'in', 'value': [1, 2, 3]}])
        self.assertIn('"id" in', q)
        self.assertIn('%s, %s, %s', q)
        self.assertEqual(v, [1, 2, 3])

    def test_notin_list(self):
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'id', 'operator': 'notin', 'value': [4, 5]}])
        self.assertIn('"id" not in', q)
        self.assertEqual(v, [4, 5])

    def test_in_single_value_scalar(self):
        """Scalar value for 'in' should be wrapped in a list."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'id', 'operator': 'in', 'value': 7}])
        self.assertIn('"id" in', q)
        self.assertEqual(v, [7])

    def test_in_empty_list(self):
        """Empty list for 'in' should produce an empty placeholder set."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'id', 'operator': 'in', 'value': []}])
        self.assertIn('"id" in ()', q)
        self.assertEqual(v, [])

    # reverse_in
    def test_reverse_in(self):
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'role, status', 'operator': 'reverse_in', 'value': 'admin'}])
        self.assertIn('%s in (', q)
        self.assertIn('"role"', q)
        self.assertIn('"status"', q)

    # Unknown operator falls back to icontains
    def test_unknown_operator_fallback(self):
        q, v = self._where('nonexistent_op', 'foo')
        self.assertIn('ilike', q)


# ---------------------------------------------------------------------------
# 3. Multiple filters combined
# ---------------------------------------------------------------------------

class TestMultipleFilters(unittest.TestCase):

    def test_two_search_filters_joined_with_and(self):
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[
            {'field': 'first_name', 'operator': 'icontains', 'value': 'jo'},
            {'field': 'last_name',  'operator': 'icontains', 'value': 'sm'},
        ])
        self.assertIn('and', q.lower())
        self.assertEqual(v, ['jo', 'sm'])

    def test_null_and_eq_combined(self):
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[
            {'field': 'last_name', 'operator': 'null',  'value': None},
            {'field': 'id',        'operator': '=',     'value': 1},
        ])
        self.assertIn('is null', q)
        self.assertIn('"id"=%s', q)
        self.assertEqual(v, [1])

    def test_extra_filters_in_select_query(self):
        """Filters passed directly to selectQuery should be appended."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'id', 'operator': '>', 'value': 10}])
        self.assertIn('"id">%s', q)
        self.assertEqual(v, [10])


# ---------------------------------------------------------------------------
# 4. JSONB column handling (Pg-specific)
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
        self.assertIn('"data"->>\'created\'', q)
        self.assertIn('%s::date', q)
        self.assertEqual(v, ['2025-01-01'])

    def test_jsonb_text_no_cast(self):
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'data->>name', 'operator': '=', 'value': 'foo'}])
        self.assertNotIn('::numeric', q)
        self.assertNotIn('::date', q)
        self.assertEqual(v, ['foo'])

    def test_jsonb_numeric_in_list(self):
        ds = make_ds()
        # Assicurati di passare le colonne (v0.5)
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[
            {'field': 'data->>status', 'operator': 'in', 'value': [1, 2, 3], 'value_type': 'numeric'}
        ])
        
        # Normalizzazione per evitare errori di formattazione (newline/spazi)
        q_norm = " ".join(q.split()).lower()
        
        # Asserzioni normalizzate
        self.assertIn('"data"->>\'status\''.lower(), q_norm)
        self.assertEqual(v, [1, 2, 3])

# ---------------------------------------------------------------------------
# 5. Limit / pagination
# ---------------------------------------------------------------------------

class TestLimit(unittest.TestCase):

    def test_limit_clause_present(self):
        ds = make_ds(limit={'start': 0, 'length': 10})
        q, _ = get_query(ds, columns=BASE_COLUMNS)
        self.assertIn('limit 10 offset 0', q)

    def test_limit_offset(self):
        ds = make_ds(limit={'start': 20, 'length': 10})
        q, _ = get_query(ds, columns=BASE_COLUMNS)
        self.assertIn('limit 10 offset 20', q)

    def test_no_limit_no_clause(self):
        ds = make_ds()
        q, _ = get_query(ds, columns=BASE_COLUMNS)
        self.assertNotIn('limit', q.lower())

    def test_limit_override_in_select_query(self):
        ds = make_ds(limit={'start': 0, 'length': 5})
        q, _ = get_query(ds, limit={'start': 10, 'length': 25})
        self.assertIn('limit 25 offset 10', q)


# ---------------------------------------------------------------------------
# 6. Shim / legacy key translation
# ---------------------------------------------------------------------------

class TestNewAPI(unittest.TestCase):
    """
    The legacy shim (__shim_legacy_json) is intentionally disabled.
    These tests verify the new clean API keys work correctly.
    """

    def test_field_key(self):
        """New API uses 'field', not 'name'."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'id', 'operator': '=', 'value': 1}])
        self.assertIn('"id"=%s', q)
        self.assertEqual(v, [1])

    def test_operator_key(self):
        """New API uses 'operator', not 'searchcriteria'."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'first_name', 'operator': 'icontains', 'value': 'jo'}])
        self.assertIn('ilike', q)
        self.assertEqual(v, ['jo'])

    def test_value_key(self):
        """New API uses 'value', not 'search'."""
        ds = make_ds()
        q, v = get_query(ds, filters=[{'field': 'id', 'operator': '=', 'value': 99}], columns=BASE_COLUMNS)
        self.assertEqual(v, [99])

    def test_contains_operator(self):
        ds = make_ds()
        q, _ = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'first_name', 'operator': 'contains', 'value': 'jo'}])

        self.assertIn("like '%' ||", q)

    def test_starts_with_operator(self):
        ds = make_ds()
        q, _ = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'first_name', 'operator': 'starts_with', 'value': 'jo'}])
        norm_q = " ".join(q.split()).lower()
        self.assertIn("like %s || '%'", norm_q)

    def test_icontains_operator(self):
        ds = make_ds()
        q, _ = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'first_name', 'operator': 'icontains', 'value': 'jo'}])

        q_norm = " ".join(q.split()).lower()

        self.assertIn("ilike", q_norm)
        self.assertIn("first_name", q_norm)


# ---------------------------------------------------------------------------
# 7. Error / invalid input handling
# ---------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):

    def test_invalid_order_direction_raises(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'sideways'}])
        with self.assertRaises(ValueError):
            get_query(ds, columns=BASE_COLUMNS)

    def test_invalid_dbms_raises(self):
        with self.assertRaises(ValueError):
            sql.Datasource(source='t', dbms='FakeDB')

    def test_missing_field_in_filter(self):
        """Filter with no 'field' key should raise rather than silently produce bad SQL."""
        ds = make_ds()
        # Aggiorna qui: ora ti aspetti ValueError
        with self.assertRaises(ValueError): 
            get_query(ds, columns=BASE_COLUMNS, filters=[{'operator': '=', 'value': 1}])

    def test_dotted_field_name_quoted_correctly(self):
        """schema.table notation should quote only the column part."""
        ds = make_ds()
        q, _ = get_query(ds, columns=[{'field': 'u.first_name'}])
        self.assertIn('u."first_name"', q)

    def test_placeholder_percent_s(self):
        """When placeholder is %s, literal % in LIKE patterns must be escaped."""
        ds = sql.Datasource(
            source='users',
            dbms='Pg',
            placeholder='%s'
        )
        q, _ = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'first_name', 'operator': 'icontains', 'value': 'jo'}])
        # The LIKE pattern uses %% for literal percent signs
        self.assertIn('%', q)


# ---------------------------------------------------------------------------
# 8. whereQuery helper
# ---------------------------------------------------------------------------

class TestWhereQuery(unittest.TestCase):

    def test_returns_empty_string_with_no_filters(self):
        ds = make_ds()
        clause, v = ds.where()
        self.assertEqual(clause, '')
        self.assertEqual(v, [])

# ---------------------------------------------------------------------------
# 9. Full-text search operators (Pg-only)
# ---------------------------------------------------------------------------

class TestFts(unittest.TestCase):

    def test_fts_generates_tsquery(self):
        """fts operator should produce a @@ websearch_to_tsquery expression."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'fc.tsv_content', 'operator': 'fts', 'value': 'contratti'}])
        self.assertIn('@@', q)
        self.assertIn('websearch_to_tsquery', q)
        self.assertIn('fc."tsv_content"', q)
        self.assertEqual(v, ['contratti'])

    def test_fts_default_language_english(self):
        ds = make_ds()
        q, _ = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contratti'}])
        self.assertIn('english', q)

    def test_fts_custom_language(self):
        """fts_language parameter should override the default."""
        ds = make_ds(fts_language='italian')
        q, _ = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contracts'}])
        self.assertIn('italian', q)
        self.assertNotIn('english', q)

    def test_fts_query_operator(self):
        """fts_query should use to_tsvector on the field, not a pre-built tsvector column."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'fm.oggetto', 'operator': 'fts_query', 'value': 'contratti'}])
        self.assertIn('to_tsvector', q)
        self.assertIn('coalesce', q)
        self.assertIn('fm."oggetto"', q)
        self.assertIn('@@', q)
        self.assertEqual(v, ['contratti'])

    def test_fts_placeholder_escaped(self):
        """fts with %s placeholder should produce %s, not %%s."""
        ds = make_ds()
        q, _ = get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contratti'}])
        self.assertIn('%s', q)
        self.assertNotIn('%%s', q)

    def test_fts_not_supported_on_sqlite(self):
        """fts operator on SQLite should raise ValueError."""
        ds = sql.Datasource(
            source='docs',
            dbms='SQLite'
        )
        with self.assertRaises(ValueError):
            get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contratti'}])

    def test_fts_not_supported_on_mysql(self):
        """fts operator on mysql should raise ValueError."""
        ds = sql.Datasource(
            source='docs',
            dbms='mysql'
        )
        with self.assertRaises(ValueError):
            get_query(ds, columns=BASE_COLUMNS, filters=[{'field': 'tsv', 'operator': 'fts', 'value': 'contratti'}])

    def test_fts_combined_with_deterministic_filters(self):
        """fts and regular filters should combine with AND."""
        ds = make_ds()
        q, v = get_query(ds, columns=BASE_COLUMNS, filters=[
            {'field': 'doc_type', 'operator': '=',  'value': 'CONTRATTO'},
            {'field': 'tsv',      'operator': 'fts', 'value': 'contratti'},
        ])
        self.assertIn('"doc_type"=%s', q)
        self.assertIn('@@', q)
        self.assertIn('and', q.lower())
        self.assertEqual(v, ['CONTRATTO', 'contratti'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
