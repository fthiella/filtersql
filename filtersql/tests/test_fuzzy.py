from hypothesis import given, strategies as st
import unittest
from filtersql.sql import Datasource, FilterSQLError

class TestFuzzing(unittest.TestCase):

    @given(st.text())
    def test_field_never_breaks_quoting(self, field_value):
        try:
            ds = Datasource(source='users', dbms='Pg')
            query, _ = ds.select(columns=[field_value])
        except FilterSQLError:
            return

        self.assertEqual(query.count('"') % 2, 0)
