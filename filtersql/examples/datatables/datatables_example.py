# -*- coding: utf-8 -*-
"""
DataTables + filtersql + parseDatatableArgs
============================================
Usa il tuo utils.py per parsare automaticamente i parametri!
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
from filtersql import filtersql
from filtersql.utils import parseDatatableArgs

app = Flask(__name__)
DB_FILE = 'demo.db'

# ============================================================================
# COLONNE DEL DATASET
# ============================================================================

COLUMNS = [
    {'field': 'id'},
    {'field': 'first_name'},
    {'field': 'last_name'},
    {'field': 'email'},
    {'field': 'age'},
    {'field': 'status'},
    {'field': 'role'},
]

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# ENDPOINT DATATABLES - SUPER SEMPLICE!
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/users')
def api_users():
    # 1. Parsa automaticamente i parametri DataTables!
    dt = parseDatatableArgs(request.args)
    
    # 2. Estrai i valori
    draw = int(dt.get('draw', 1))
    start = int(dt.get('start', 0))
    length = int(dt.get('length', 10))
    
    # 3. Costruisci i filtri da dt
    filters = []
    
    # Filtri per colonna (search per colonna)
    columns = dt.get('columns', {})
    for idx, col_data in columns.items():
        search_value = col_data.get('search', {}).get('value', '').strip()
        if search_value:
            col_idx = int(idx)
            filters.append({
                'field': COLUMNS[col_idx]['field'],
                'operator': 'icontains',
                'value': search_value
            })
    
    # Filtro globale
    global_search = dt.get('search', {}).get('value', '').strip()
    if global_search:
        filters.append({
            'or': [
                {'field': 'first_name', 'operator': 'icontains', 'value': global_search},
                {'field': 'last_name', 'operator': 'icontains', 'value': global_search},
                {'field': 'email', 'operator': 'icontains', 'value': global_search},
                {'field': 'status', 'operator': 'icontains', 'value': global_search},
                {'field': 'role', 'operator': 'icontains', 'value': global_search},
            ]
        })
    
    # 4. Costruisci ORDER
    order = []
    order_data = dt.get('order', {})
    for idx, ord_info in order_data.items():
        col_idx = int(ord_info.get('column', 0))
        col_dir = ord_info.get('dir', 'asc')
        order.append({
            'field': COLUMNS[col_idx]['field'],
            'order': col_dir
        })
    
    if not order:
        order = [{'field': 'id', 'order': 'asc'}]
    
    # 5. Conta totale
    q_total, p_total = filtersql({
        'action': 'select',
        'source': 'users',
        'columns': [{'field': 'COUNT(*) as total', 'raw': True}],
    }, dbms='SQLite', placeholder='?')
    
    # 6. Conta filtrati
    q_filtered, p_filtered = filtersql({
        'action': 'select',
        'source': 'users',
        'columns': [{'field': 'COUNT(*) as total', 'raw': True}],
        'filters': filters,
    }, dbms='SQLite', placeholder='?')
    
    # 7. Dati
    q_data, p_data = filtersql({
        'action': 'select',
        'source': 'users',
        'columns': COLUMNS,
        'filters': filters,
        'order': order,
        'limit': {'start': start, 'length': length},
    }, dbms='SQLite', placeholder='?')
    
    # 8. Esegui
    with get_db() as conn:
        cur = conn.cursor()
        
        cur.execute(q_total, p_total)
        records_total = cur.fetchone()['total']
        
        cur.execute(q_filtered, p_filtered)
        records_filtered = cur.fetchone()['total']
        
        cur.execute(q_data, p_data)
        data = [dict(row) for row in cur.fetchall()]
    
    return jsonify({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })

# ============================================================================
# AVVIA
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)