# -*- coding: utf-8 -*-
"""
Focused test suite for filtersql cursor / keyset pagination.
Covers ASC, DESC, mixed directions, seek/next/prev, and validation.
"""

import unittest
from filtersql import Datasource, ValidationError


def make_ds(order=None, **kwargs):
    kwargs.setdefault('source', 'users')
    kwargs.setdefault('dbms', 'Pg')
    kwargs.setdefault('placeholder', '%s')
    if order is not None:
        kwargs['order'] = order
    return Datasource(**kwargs)


def select(ds, **kwargs):
    kwargs.setdefault('columns', [{'field': 'id'}])
    return ds.select(**kwargs)


class TestCursorBasic(unittest.TestCase):
    """Single-column, ASC (the classic case)."""

    def test_next_asc(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = select(ds, cursor={'id': 100}, direction='next')
        self.assertIn('"id" > %s', q)
        self.assertEqual(v, [100])

    def test_prev_asc(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = select(ds, cursor={'id': 100}, direction='prev')
        self.assertIn('"id" < %s', q)
        self.assertIn('"id" desc', q)          # order inverted
        self.assertEqual(v, [100])

    def test_seek_asc(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = select(ds, cursor={'id': 100}, direction='seek')
        self.assertIn('"id" = %s', q)
        self.assertNotIn('>', q)
        self.assertNotIn('<', q)
        self.assertEqual(v, [100])


class TestCursorDesc(unittest.TestCase):
    """Single-column DESC – the case that was previously broken."""

    def test_next_desc(self):
        # ORDER BY created_at DESC  →  next means older records → <
        ds = make_ds(order=[{'field': 'created_at', 'order': 'desc'}])
        q, v = select(ds, cursor={'created_at': '2026-07-20'}, direction='next')
        self.assertIn('"created_at" < %s', q)
        self.assertEqual(v, ['2026-07-20'])

    def test_prev_desc(self):
        # prev means newer records → >
        ds = make_ds(order=[{'field': 'created_at', 'order': 'desc'}])
        q, v = select(ds, cursor={'created_at': '2026-07-20'}, direction='prev')
        self.assertIn('"created_at" > %s', q)
        self.assertIn('"created_at" asc', q)   # order inverted
        self.assertEqual(v, ['2026-07-20'])

    def test_seek_desc(self):
        ds = make_ds(order=[{'field': 'created_at', 'order': 'desc'}])
        q, v = select(ds, cursor={'created_at': '2026-07-20'}, direction='seek')
        self.assertIn('"created_at" = %s', q)
        self.assertEqual(v, ['2026-07-20'])


class TestCursorMixed(unittest.TestCase):
    """Multi-column with mixed ASC/DESC."""

    def test_next_mixed(self):
        # ORDER BY last_name ASC, created_at DESC
        ds = make_ds(order=[
            {'field': 'last_name',  'order': 'asc'},
            {'field': 'created_at', 'order': 'desc'},
        ])
        q, v = select(ds,
            cursor={'last_name': 'Smith', 'created_at': '2026-07-20'},
            direction='next'
        )
        # Expected:
        # (last_name > 'Smith')
        # OR (last_name = 'Smith' AND created_at < '2026-07-20')
        self.assertIn('"last_name" > %s', q)
        self.assertIn('"created_at" < %s', q)
        self.assertIn(' or ', q.lower())
        self.assertEqual(v, ['Smith', '2026-07-20', 'Smith'])

    def test_prev_mixed(self):
        ds = make_ds(order=[
            {'field': 'last_name',  'order': 'asc'},
            {'field': 'created_at', 'order': 'desc'},
        ])
        q, v = select(ds,
            cursor={'last_name': 'Smith', 'created_at': '2026-07-20'},
            direction='prev'
        )
        # Expected:
        # (last_name < 'Smith')
        # OR (last_name = 'Smith' AND created_at > '2026-07-20')
        self.assertIn('"last_name" < %s', q)
        self.assertIn('"created_at" > %s', q)
        self.assertEqual(v, ['Smith', '2026-07-20', 'Smith'])

    def test_three_column_mixed(self):
        ds = make_ds(order=[
            {'field': 'a', 'order': 'asc'},
            {'field': 'b', 'order': 'desc'},
            {'field': 'c', 'order': 'asc'},
        ])
        q, v = select(ds,
            cursor={'a': 1, 'b': 2, 'c': 3},
            direction='next'
        )
        # (a > 1)
        # OR (a = 1 AND b < 2)
        # OR (a = 1 AND b = 2 AND c > 3)
        self.assertIn('"a" > %s', q)
        self.assertIn('"b" < %s', q)
        self.assertIn('"c" > %s', q)
        self.assertEqual(v, [1, 2, 3, 1, 2, 1])


class TestCursorValidation(unittest.TestCase):
    """Strict checks introduced by the fix."""

    def test_cursor_field_missing_from_order_raises(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        with self.assertRaises(ValidationError) as cm:
            select(ds, cursor={'unknown': 100}, direction='next')
        self.assertIn('unknown', str(cm.exception))
        self.assertIn('must be present in', str(cm.exception))

    def test_no_order_at_all_raises(self):
        ds = make_ds()                       # no order
        with self.assertRaises(ValidationError):
            select(ds, cursor={'id': 100}, direction='next')

    def test_invalid_direction_raises(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        with self.assertRaises(ValidationError):
            select(ds, cursor={'id': 100}, direction='sideways')

    def test_cursor_without_direction_raises(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        with self.assertRaises(ValidationError):
            select(ds, cursor={'id': 100})   # missing direction

    def test_direction_without_cursor_is_allowed(self):
        """A direction without a cursor is legal; it only inverts ORDER BY."""
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        # must not raise
        q, v = select(ds, direction='prev')
        self.assertIn('"id" desc', q)   # order was inverted
        self.assertEqual(v, [])


class TestCursorWithFilters(unittest.TestCase):
    """Cursor + ordinary filters together."""

    def test_cursor_and_filters_combined(self):
        ds = make_ds(order=[{'field': 'id', 'order': 'asc'}])
        q, v = select(ds,
            filters=[
                {'field': 'status', 'operator': '=', 'value': 'active'},
            ],
            cursor={'id': 50},
            direction='next'
        )
        self.assertIn('"id" > %s', q)
        self.assertIn('"status" = %s', q)
        self.assertEqual(v, [50, 'active'])


class TestCursorOrderInversion(unittest.TestCase):
    """ORDER BY must be inverted on 'prev'."""

    def test_prev_inverts_order(self):
        ds = make_ds(order=[
            {'field': 'last_name', 'order': 'asc'},
            {'field': 'id',        'order': 'desc'},
        ])
        q, _ = select(ds,
            cursor={'last_name': 'Smith', 'id': 10},
            direction='prev'
        )
        # original ASC → DESC, original DESC → ASC
        self.assertIn('"last_name" desc', q)
        self.assertIn('"id" asc', q)


if __name__ == '__main__':
    unittest.main(verbosity=2)