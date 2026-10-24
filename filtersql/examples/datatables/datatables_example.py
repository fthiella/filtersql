# -*- coding: utf-8 -*-
"""
DataTables + filtersql + parseDatatableArgs
==============================================================
Demonstrates secure server-side processing using filtersql allowlists
and server-side tenant scoping.
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
from filtersql import filtersql
from filtersql.utils import parseDatatableArgs

app = Flask(__name__)
DB_FILE = 'demo.db'

# ============================================================================
# DATASET COLUMNS & SECURITY POLICY
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

# Exact allowlist of columns clients are permitted to filter or sort by
ALLOWED_COLUMNS = {col['field'] for col in COLUMNS}

# Server-side multi-tenant boundary (never trusted from the client payload)
TENANT_ID = 42

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

# DataTables uses length=-1 to mean "All". filtersql rejects non-positive
# limits (limit 0, -1 is nonsense), so we cap "All" at the server's max
# page size. Keep in sync with filtersql.MAX_LIMIT_LENGTH.
MAX_DT_LENGTH = 10_000

@app.route('/api/users')
def api_users():
    dt = parseDatatableArgs(request.args)

    # 1. Numeric args: reject garbage with 400, don't let int() crash.
    try:
        draw   = int(dt.get('draw',   1))
        start  = int(dt.get('start',  0))
        length = int(dt.get('length', 10))
    except (ValueError, TypeError):
        return jsonify({'error': "Invalid 'draw'/'start'/'length'"}), 400

    # 2. Translate "All" (-1) to the max page size instead of failing.
    if length < 0:
        length = MAX_DT_LENGTH

    filters = []
    for idx, col_data in dt.get('columns', {}).items():
        search_value = col_data.get('search', {}).get('value', '').strip()
        if not search_value:
            continue
        try:
            field = COLUMNS[int(idx)]['field']
        except (ValueError, IndexError):
            continue
        filters.append({
            'field':    field,
            'operator': 'icontains',
            'value':    search_value,
        })

    global_search = dt.get('search', {}).get('value', '').strip()
    if global_search:
        filters.append({
            'or': [
                {'field': 'first_name', 'operator': 'icontains', 'value': global_search},
                {'field': 'last_name',  'operator': 'icontains', 'value': global_search},
                {'field': 'email',      'operator': 'icontains', 'value': global_search},
                {'field': 'status',     'operator': 'icontains', 'value': global_search},
                {'field': 'role',       'operator': 'icontains', 'value': global_search},
            ]
        })

    order = []
    for _, ord_info in dt.get('order', {}).items():
        try:
            field = COLUMNS[int(ord_info.get('column', 0))]['field']
        except (ValueError, IndexError):
            continue
        direction = ord_info.get('dir', 'asc')
        if direction not in ('asc', 'desc'):
            direction = 'asc'
        order.append({'field': field, 'order': direction})

    if not order:
        order = [{'field': 'id', 'order': 'asc'}]

    try:
        q_total, p_total = filtersql({
            'action': 'select',
            'source': 'users',
            'columns': [{'field': 'COUNT(*) as total', 'raw': True}],
        }, dbms='sqlite', scope={'tenant_id': TENANT_ID}, allow_raw_fields=True)

        q_filtered, p_filtered = filtersql({
            'action': 'select',
            'source': 'users',
            'columns': [{'field': 'COUNT(*) as total', 'raw': True}],
            'filters': filters,
        }, dbms='sqlite', scope={'tenant_id': TENANT_ID}, allow_raw_fields=True)

        q_data, p_data = filtersql({
            'action': 'select',
            'source': 'users',
            'columns': COLUMNS,
            'filters': filters,
            'order': order,
            'limit': {'start': start, 'length': length},
        }, dbms='sqlite', scope={'tenant_id': TENANT_ID}, allowed_columns=ALLOWED_COLUMNS)

    except (filtersql.ValidationError, filtersql.ConfigurationError) as e:
        return jsonify({'error': str(e)}), 400

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
            'draw':            draw,
            'recordsTotal':    records_total,
            'recordsFiltered': records_filtered,
            'data':            data,
        })
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)