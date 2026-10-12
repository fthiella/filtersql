import sqlite3
import pytest
import sqlglot
from hypothesis import given, settings, strategies as st
from filtersql.sql import Datasource, FilterSQLError

# =====================================================================
# 1. HYPOTHESIS GENERATION STRATEGIES
# =====================================================================

# Mapping between library DBMS and sqlglot recognized dialects
DIALECT_MAP = {
    'Pg': 'postgres',
    'SQLite': 'sqlite',
    'mysql': 'mysql',
    'Oracle': 'oracle',
    'DuckDB': 'duckdb'
}

# Simple leaf filter
base_filter_st = st.fixed_dictionaries({
    'field': st.text(min_size=1, max_size=80, alphabet=st.characters(categories=['L', 'N'])),
    'operator': st.sampled_from(['=', '!=', '>', '>=', '<', '<=', 'contains', 'icontains']),
    'value': st.one_of(st.text(max_size=80), st.integers(min_value=-2000, max_value=2000))
})

# RECURSIVE generator: generates random nested filters with AND and OR (up to 4 levels)
nested_filters_st = st.recursive(
    base_filter_st,
    lambda children: st.one_of(
        st.fixed_dictionaries({'and': st.lists(children, min_size=1, max_size=3)}),
        st.fixed_dictionaries({'or': st.lists(children, min_size=1, max_size=3)})
    ),
    max_leaves=5
)

filters_list_st = st.lists(nested_filters_st, min_size=1, max_size=3)


# =====================================================================
# 2. ADVANCED TEST SUITE
# =====================================================================

class TestAdvancedDatabaseSuite:

    @settings(max_examples=1000)
    @given(dbms=st.sampled_from(list(DIALECT_MAP.keys())), filters=filters_list_st)
    def test_multi_dbms_ast_syntax(self, dbms, filters):
        """
        TEST 1: Dialect AST Validation (sqlglot).
        Generates queries for Pg, MySQL, Oracle, SQLite, DuckDB with complex nested filters
        and uses an AST parser to verify that the SQL syntax is perfect for that DB.
        """
        ds = Datasource(source='users', dbms=dbms, placeholder='?')

        try:
            query, params = ds.select(filters=filters)
        except FilterSQLError:
            return  # Controlled rejection by filtersql for invalid input -> CORRECT

        target_dialect = DIALECT_MAP[dbms]
        
        try:
            # sqlglot parses the query. If it finds syntax errors in the specific dialect, it raises ParseError
            sqlglot.parse_one(query, read=target_dialect)
        except sqlglot.errors.ParseError as e:
            pytest.fail(f"Invalid SQL generated for {dbms}:\nQuery:\n{query}\nAST Error: {e}")

    @settings(max_examples=1000)
    @given(
        row_count=st.integers(min_value=10, max_value=150),
        page_size=st.integers(min_value=2, max_value=15)
    )
    def test_keyset_pagination_integrity(self, row_count, page_size):
        """
        TEST 2: Real Keyset Pagination Integrity.
        Populates a real in-memory SQLite DB, then reads ALL data page by page.
        Mathematically verifies that NO rows are ever lost or duplicated.
        """
        conn = sqlite3.connect(":memory:")
        cursor_db = conn.cursor()
        cursor_db.execute("CREATE TABLE items (id INT, score INT)")
        
        # Populate the DB with sorted records
        expected_data = [(i, i * 5) for i in range(1, row_count + 1)]
        cursor_db.executemany("INSERT INTO items VALUES (?, ?)", expected_data)

        ds = Datasource(
            source='items', 
            dbms='SQLite',
            order=[{'field': 'score', 'order': 'asc'}, {'field': 'id', 'order': 'asc'}],
            limit={'length': page_size}
        )

        collected_rows = []
        current_cursor = None

        while True:
            direction = 'next' if current_cursor else None
            query, params = ds.select(cursor=current_cursor, direction=direction)
            
            rows = cursor_db.execute(query, params).fetchall()
            if not rows:
                break
                
            collected_rows.extend(rows)
            
            # Set the cursor for the next page using the last read row
            last_row = rows[-1]
            current_cursor = {'id': last_row[0], 'score': last_row[1]}

        conn.close()

        # FUNDAMENTAL VERIFICATION
        assert collected_rows == expected_data, (
            f"Pagination failed! Inserted {len(expected_data)} rows, "
            f"retrieved {len(collected_rows)} rows."
        )

    @settings(max_examples=1000)
    @given(split_val=st.integers(min_value=1, max_value=100))
    def test_metamorphic_complementary_logic(self, split_val):
        """
        TEST 3: Metamorphic Testing (Logic Invariant).
        Verifies that: |WHERE id <= X| + |WHERE id > X| is EXACTLY equal to the total rows.
        """
        conn = sqlite3.connect(":memory:")
        cursor_db = conn.cursor()
        cursor_db.execute("CREATE TABLE numbers (id INT)")
        cursor_db.executemany("INSERT INTO numbers VALUES (?)", [(i,) for i in range(1, 101)]) # 100 total rows

        ds = Datasource(source='numbers', dbms='SQLite')

        # Query 1: id <= split_val
        q1, p1 = ds.select(filters=[{'field': 'id', 'operator': '<=', 'value': split_val}])
        count1 = len(cursor_db.execute(q1, p1).fetchall())

        # Query 2: id > split_val
        q2, p2 = ds.select(filters=[{'field': 'id', 'operator': '>', 'value': split_val}])
        count2 = len(cursor_db.execute(q2, p2).fetchall())

        conn.close()

        assert count1 + count2 == 100, f"Metamorphic invariant failed for split_val={split_val}"

    # =====================================================================
    # 4. VALUE TRANSFORMATION AND ESCAPING TESTS
    # =====================================================================

    @settings(max_examples=1000)
    @given(
        val=st.text(max_size=50),
        op=st.sampled_from(['contains', 'starts_with', 'ends_with', 'icontains', 'istarts_with', 'iends_with'])
    )
    def test_wildcard_param_transformations(self, val, op):
        """
        TEST 4: Wildcard Param Transformation & Escaping.
        Verifies that `filtersql` correctly escapes LIKE special characters (%, _, \\)
        in the bound parameter and correctly wraps the parameter in the appropriate
        wildcard symbols (%) according to the operator.
        """
        ds = Datasource(source='users', dbms='Pg')
        query, params = ds.select(filters=[{'field': 'username', 'operator': op, 'value': val}])

        assert len(params) == 1, "Exactly one parameter must be generated"

        # 1. Calculate the expected escaping for LIKE special characters
        escaped_val = (
            val.replace('\\', '\\\\')
               .replace('%', '\\%')
               .replace('_', '\\_')
        )

        # 2. Apply the expected wildcard wrapping for the new v1.3 architecture
        if 'starts_with' in op:
            expected_param = f"{escaped_val}%"
        elif 'ends_with' in op:
            expected_param = f"%{escaped_val}"
        elif 'contains' in op:
            expected_param = f"%{escaped_val}%"
        else:
            expected_param = escaped_val

        assert params[0] == expected_param, (
            f"Incorrect wildcard transformation for op={op}:\n"
            f"Input:    {repr(val)}\n"
            f"Expected: {repr(expected_param)}\n"
            f"Obtained: {repr(params[0])}"
        )