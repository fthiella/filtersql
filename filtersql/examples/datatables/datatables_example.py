# -*- coding: utf-8 -*-
"""
DataTables + filtersql + parseDatatableArgs
============================================
Uses your utils.py to parse DataTables parameters automatically.
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
from filtersql import filtersql
from filtersql.utils import parseDatatableArgs

app = Flask(__name__)
DB_FILE = 'demo.db'

# ============================================================================
# DATASET COLUMNS
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
# DATATABLES ENDPOINT
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/users')
def api_users():
    # 1. Automatically parse DataTables parameters
    dt = parseDatatableArgs(request.args)
    
    # 2. Extract values
    draw = int(dt.get('draw', 1))
    start = int(dt.get('start', 0))
    length = int(dt.get('length', 10))
    
    # 3. Build filters from DataTables payload
    filters = []
    
    # Per-column search filters
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
    
    # Global search filter
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
    
    # 4. Build ORDER
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
    
    # 5. Count all
    q_total, p_total = filtersql({
        'action': 'select',
        'source': 'users',
        'columns': [{'field': 'COUNT(*) as total', 'raw': True}],
    }, dbms='SQLite', placeholder='?', allow_raw_fields=True)
    
    # 6. Count filtered
    q_filtered, p_filtered = filtersql({
        'action': 'select',
        'source': 'users',
        'columns': [{'field': 'COUNT(*) as total', 'raw': True}],
        'filters': filters,
    }, dbms='SQLite', placeholder='?', allow_raw_fields=True)
    
    # 7. Fetch page data
    q_data, p_data = filtersql({
        'action': 'select',
        'source': 'users',
        'columns': COLUMNS,
        'filters': filters,
        'order': order,
        'limit': {'start': start, 'length': length},
    }, dbms='SQLite', placeholder='?')
    
    # 8. Execute
    conn = get_db()
    try:
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
    finally:
        conn.close()

# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)