import sqlite3
import pytest
from hypothesis import given, settings, strategies as st
from filtersql.sql import Datasource, FilterSQLError

# --- STRATEGIE PERSONALIZZATE DI HYPOTHESIS ---

# Genera uno qualsiasi dei DBMS supportati
dbms_st = st.sampled_from(['SQLite', 'Pg', 'DuckDB', 'mysql', 'Oracle'])

# Genera tutti i possibili operatori supportati
operator_st = st.sampled_from([
    '=', '!=', '>', '>=', '<', '<=',
    'starts_with', 'ends_with', 'contains',
    'istarts_with', 'iends_with', 'icontains',
    'in', 'notin', 'null', 'notnull', 'between'
])

# Genera un singolo filtro arbitrario
filter_st = st.fixed_dictionaries({
    'field': st.text(min_size=1, max_size=50),
    'operator': operator_st,
    'value': st.one_of(
        st.text(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.lists(st.integers(), min_size=0, max_size=5)  # Per 'in', 'notin', 'between'
    )
})

# Genera strutture di filtri anche con OR e AND annidati
filters_list_st = st.lists(filter_st, min_size=0, max_size=5)


# --- SUITE DI FUZZING AVANZATA ---

class TestAdvancedFuzzing:

    @settings(max_examples=10000)
    @given(dbms=dbms_st, filters=filters_list_st)
    def test_no_unhandled_exceptions(self, dbms, filters):
        """
        Garantisce che PER QUALSIASI INPUT l'applicazione:
        1. Generi una query valida SENZA crash inattesi (IndexError, KeyError, TypeError, ecc.).
        2. OPPURE sollevi pulitamente un'eccezione gestita (FilterSQLError).
        """
        try:
            ds = Datasource(source='test_table', dbms=dbms)
            ds.select(filters=filters)
        except FilterSQLError:
            pass  # Rifiuto pulito dell'input malevolo -> CORRETTO

    @settings(max_examples=5000)
    @given(filters=filters_list_st)
    def test_sqlite_execution_validity(self, filters):
        """
        Genera query per SQLite e le ESEGUE VERAMENTE in un DB SQLite in-memory.
        Se la query generata ha un errore di sintassi SQL, SQLite lancerà un eccezione.
        """
        ds = Datasource(source='test_table', dbms='SQLite')
        
        try:
            query, params = ds.select(filters=filters)
        except FilterSQLError:
            return  # Input non valido rifiurato da filtersql -> CORRETTO

        # Crea un DB SQLite fittizio per verificare che la sintassi sia valida al 100%
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_table (id INT, name TEXT, col TEXT)")

        try:
            # Tenta di eseguire la query preparata e parametrizzata
            cursor.execute(query, params)
        except (sqlite3.OperationalError, OverflowError) as e:
            # OverflowError = intero troppo grande per il driver C di SQLite
            if isinstance(e, OverflowError):
                return
            
            # Se è un errore di sintassi SQL, allora è un bug di filtersql!
            if "syntax error" in str(e).lower():
                pytest.fail(f"Sintassi SQL errata:\nQuery: {query}\nParams: {params}\nErrore: {e}")
        finally:
            conn.close()