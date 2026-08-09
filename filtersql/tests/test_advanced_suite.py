import sqlite3
import pytest
import sqlglot
from hypothesis import given, settings, strategies as st
from filtersql.sql import Datasource, FilterSQLError

# =====================================================================
# 1. STRATEGIE DI GENERAZIONE HYPOTHESIS
# =====================================================================

# Mappatura tra i DBMS della libreria e i dialetti riconosciuti da sqlglot
DIALECT_MAP = {
    'Pg': 'postgres',
    'SQLite': 'sqlite',
    'mysql': 'mysql',
    'Oracle': 'oracle',
    'DuckDB': 'duckdb'
}

# Filtro foglia semplice
base_filter_st = st.fixed_dictionaries({
    'field': st.text(min_size=1, max_size=80, alphabet=st.characters(categories=['L', 'N'])),
    'operator': st.sampled_from(['=', '!=', '>', '>=', '<', '<=', 'contains', 'icontains']),
    'value': st.one_of(st.text(max_size=80), st.integers(min_value=-2000, max_value=2000))
})

# Generatore RICORSIVO: genera filtri annidati casuali con AND e OR (fino a 4 livelli)
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
# 2. SUITE DI TEST AVANZATI
# =====================================================================

class TestAdvancedDatabaseSuite:

    @settings(max_examples=1000)
    @given(dbms=st.sampled_from(list(DIALECT_MAP.keys())), filters=filters_list_st)
    def test_multi_dbms_ast_syntax(self, dbms, filters):
        """
        TEST 1: Validazione AST dei Dialetti (sqlglot).
        Genera query per Pg, MySQL, Oracle, SQLite, DuckDB con filtri annidati complessi
        e usa un parser AST per verificare che la sintassi SQL sia perfetta per quel DB.
        """
        ds = Datasource(source='users', dbms=dbms, placeholder='?')

        try:
            query, params = ds.select(filters=filters)
        except FilterSQLError:
            return  # Rifiuto controllato da filtersql per input non valido -> CORRETTO

        target_dialect = DIALECT_MAP[dbms]
        
        try:
            # sqlglot analizza la query. Se trova errori di sintassi nel dialetto specifico, lancia ParseError
            sqlglot.parse_one(query, read=target_dialect)
        except sqlglot.errors.ParseError as e:
            pytest.fail(f"SQL non valido generato per {dbms}:\nQuery:\n{query}\nErrore AST: {e}")

    @settings(max_examples=1000)
    @given(
        row_count=st.integers(min_value=10, max_value=150),
        page_size=st.integers(min_value=2, max_value=15)
    )
    def test_keyset_pagination_integrity(self, row_count, page_size):
        """
        TEST 2: Integrità Reale della Keyset Pagination.
        Popola un DB SQLite reale in-memory, poi legge TUTTI i dati pagina per pagina.
        Verifica matematicamente che NESSUNA riga venga mai persa o duplicata.
        """
        conn = sqlite3.connect(":memory:")
        cursor_db = conn.cursor()
        cursor_db.execute("CREATE TABLE items (id INT, score INT)")
        
        # Popoliamo il DB con record ordinati
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
            
            # Imposta il cursore per la pagina successiva usando l'ultima riga letta
            last_row = rows[-1]
            current_cursor = {'id': last_row[0], 'score': last_row[1]}

        conn.close()

        # VERIFICA FONDAMENTALE
        assert collected_rows == expected_data, (
            f"La paginazione ha fallito! Inserite {len(expected_data)} righe, "
            f"recuperate {len(collected_rows)} righe."
        )

    @settings(max_examples=1000)
    @given(split_val=st.integers(min_value=1, max_value=100))
    def test_metamorphic_complementary_logic(self, split_val):
        """
        TEST 3: Test Metamorfico (Invariante Logica).
        Verifica che: |WHERE id <= X| + |WHERE id > X| sia ESATTAMENTE uguale al totale delle righe.
        """
        conn = sqlite3.connect(":memory:")
        cursor_db = conn.cursor()
        cursor_db.execute("CREATE TABLE numbers (id INT)")
        cursor_db.executemany("INSERT INTO numbers VALUES (?)", [(i,) for i in range(1, 101)]) # 100 righe totali

        ds = Datasource(source='numbers', dbms='SQLite')

        # Query 1: id <= split_val
        q1, p1 = ds.select(filters=[{'field': 'id', 'operator': '<=', 'value': split_val}])
        count1 = len(cursor_db.execute(q1, p1).fetchall())

        # Query 2: id > split_val
        q2, p2 = ds.select(filters=[{'field': 'id', 'operator': '>', 'value': split_val}])
        count2 = len(cursor_db.execute(q2, p2).fetchall())

        conn.close()

        assert count1 + count2 == 100, f"Invariante metamorfica fallita per split_val={split_val}"

    # =====================================================================
    # 4. TEST DI TRASFORMAZIONE E INTEGRITÀ DEI VALORI (PARAMS)
    # =====================================================================

    @settings(max_examples=1000)
    @given(
        val=st.text(max_size=50),
        op=st.sampled_from(['contains', 'starts_with', 'ends_with', 'icontains', 'istarts_with', 'iends_with'])
    )
    def test_wildcard_param_transformations(self, val, op):
        """
        TEST 4: Verifica che il parametro generato per gli operatori wildcard
        contenga il valore "pulito" (con soli i caratteri speciali di LIKE
        escaped), SENZA i simboli '%' incollati dentro.

        NOTA DI DESIGN: a differenza di quanto ci si potrebbe aspettare,
        filtersql non incolla mai '%' dentro al parametro (es. '%valore%').
        Il parametro resta il valore originale (con escaping dei caratteri
        speciali %, _, backslash), e i wildcard '%' vengono aggiunti
        direttamente nel testo SQL via concatenazione (es.
        chr(37) || ? || chr(37) su Pg/DuckDB, concat('%', ?, '%') su
        MySQL, '*' || ? || '*' su SQLite GLOB). Questo evita ogni ambiguita'
        tra "wildcard di sintassi" e "contenuto del parametro" ed e' per
        design, non un bug. La correttezza del wrapping SQL stesso e'
        verificata separatamente dal test AST (test_multi_dbms_ast_syntax)
        e dai test di esecuzione reale
        (test_fuzzy_advanced.test_sqlite_execution_validity).
        """
        ds = Datasource(source='users', dbms='Pg')
        query, params = ds.select(filters=[{'field': 'username', 'operator': op, 'value': val}])

        assert len(params) == 1, "Deve essere generato esattamente un parametro"

        # BACKSLASH = un solo carattere backslash, costruito con chr(92)
        # per evitare qualsiasi ambiguita' di escaping nel sorgente stesso.
        BACKSLASH = chr(92)

        # Stesso calcolo di escaping usato in test_wildcard_param_transformations_val:
        # solo i caratteri speciali di LIKE vengono escaped, '%' NON viene
        # aggiunto attorno al valore.
        expected_val = (
            val.replace(BACKSLASH, BACKSLASH * 2)
               .replace('%', BACKSLASH + '%')
               .replace('_', BACKSLASH + '_')
        )

        assert params[0] == expected_val, (
            "Il parametro non deve contenere '%' incollati per op=" + op
            + " | Input: " + repr(val)
            + " | Atteso: " + repr(expected_val)
            + " | Ottenuto: " + repr(params[0])
        )

    @settings(max_examples=200)
    @given(
        val=st.text(max_size=50),
        op=st.sampled_from(['contains', 'starts_with', 'ends_with', 'icontains', 'istarts_with', 'iends_with'])
    )
    def test_wildcard_param_transformations_val(self, val, op):
        r"""
        TEST 4: Verifica la protezione da LIKE Injection nei parametri.
        `filtersql` deve convertire '%', '_' e '\' in '%\%', '\_', '\\' nei parametri
        per garantire la ricerca di stringhe letterali.
        """
        ds = Datasource(source='users', dbms='Pg')
        query, params = ds.select(filters=[{'field': 'username', 'operator': op, 'value': val}])

        assert len(params) == 1, "Deve essere generato esattamente un parametro"

        # Calcoliamo l'escaping atteso per i caratteri speciali di LIKE
        expected_escaped_val = (
            val.replace('\\', '\\\\')
               .replace('%', '\\%')
               .replace('_', '\\_')
        )

        assert params[0] == expected_escaped_val, (
            f"Escaping wildcard errato per op={op}:\n"
            f"Input:    {repr(val)}\n"
            f"Atteso:   {repr(expected_escaped_val)}\n"
            f"Ottenuto: {repr(params[0])}"
        )