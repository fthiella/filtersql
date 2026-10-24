# -*- coding: utf-8 -*-
"""
filtersql + Cursor Pagination & CRUD Editor
=============================================================
Demonstrates cursor-based pagination and safe CRUD operations via a generic API gateway.
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
from filtersql import filtersql, FilterSQLError

app = Flask(__name__)
DB_FILE = 'demo.db'

# ============================================================================
# SECURITY POLICY & ALLOWLISTS (filtersql 1.3.1)
# ============================================================================

ALLOWED_TABLES = {
    'users': {'id', 'first_name', 'last_name', 'email', 'age', 'status', 'role', 'tenant_id'},
#    'contracts': {'id', 'tenant_id', 'contract_number', 'amount', 'status', 'created_at'},
#    'resolutions': {'id', 'tenant_id', 'title', 'body', 'date'}
}

# Server-side multi-tenant boundary example (optional, can be adapted per session/auth)
DEFAULT_TENANT_ID = 42

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

@app.route('/')
def index():
    return render_template('edit.html')

@app.route('/api/<source>/<action>', methods=['POST'])
def api_gateway(source, action):
    
    # 1. Security Table & Action Whitelist
    if source not in ALLOWED_TABLES or action not in ('select', 'insert', 'update', 'delete'):
        return jsonify({'status': 'error', 'message': 'Endpoint or operation not allowed'}), 403

    # 2. Payload Extraction
    payload = request.json or {}
    
    # Restrict columns allowed for this table using filtersql 1.3.1 allowlists
    table_allowed_columns = ALLOWED_TABLES[source]
    
    # FIX: When allowed_columns is active, SELECT * is disallowed. 
    # If the client did not send explicit columns for a select action, provide all allowed columns as default.
    if action == 'select' and not payload.get('columns'):
        payload['columns'] = list(table_allowed_columns)
    
    try:
        # 3. Call filtersql with strict allowlists and scope enforcement
        query, params = filtersql(
            {**payload, 'action': action, 'source': source},
            dbms='sqlite',
            allowed_columns=table_allowed_columns,
            scope={'tenant_id': DEFAULT_TENANT_ID}
        )

        # 4. Database Execution
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            
            # LOGICAL FORK: Read vs. Write operations
            if action == 'select':
                records = [dict(row) for row in cur.fetchall()]
                
                return jsonify({
                    'status': 'ok',
                    'data': records,
                    'debug_sql': query,
                    'debug_params': params
                })
                
            else:
                conn.commit()
                rows_affected = cur.rowcount
                
                return jsonify({
                    'status': 'ok',
                    'message': f'Operation {action.upper()} successfully completed on {source}.',
                    'rows_affected': rows_affected,
                    'debug_sql': query,
                    'debug_params': params
                })
                
    except FilterSQLError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

    except sqlite3.IntegrityError as e:
        return jsonify({
            'status': 'error',
            'message': 'Database integrity violation.',
            'details': str(e)
        }), 400

    except Exception:
        app.logger.exception("unhandled error in /api/%s/%s", source, action)
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    # use_reloader=False prevents watchdog from crashing/reloading on third-party site-packages changes
    app.run(debug=True, use_reloader=False, port=5000)