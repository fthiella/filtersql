from flask import Flask, request, jsonify, render_template
import sqlite3
from filtersql import filtersql, FilterSQLError

# WARNING: this example has no authentication and no authorization.
# It is intended for local development only. Do not expose it to a network.

app = Flask(__name__)

DB_FILE = 'demo.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    # Enable name-based access to columns (similar to RealDictCursor in Postgres)
    conn.row_factory = sqlite3.Row 
    return conn

@app.route('/')
def index():
    return render_template('edit.html')

@app.route('/api/<source>/<action>', methods=['POST'])
def api_gateway(source, action):
    
    # 1. Security Whitelist
    # Hardcoded definitions to prevent arbitrary table access or execution
    allowed_tables = ['users', 'contracts', 'resolutions']
    allowed_actions = ['select', 'insert', 'update', 'delete']
    
    if source not in allowed_tables or action not in allowed_actions:
        return jsonify({'status': 'error', 'message': 'Endpoint or operation not allowed'}), 403

    # 2. Payload Extraction
    payload = request.json or {}
    
    try:
        # 3. Call filtersql for SQLite
        # Note: Specifying 'SQLite' ensures the engine uses the correct text search 
        # syntax (GLOB) and positional parameter binding (?)
        query, params = filtersql(
            {**payload, 'action': action, 'source': source},
            dbms='SQLite'
        )

        # 4. Database Execution
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            
            # LOGICAL FORK: Read vs. Write operations
            if action == 'select':
                # Convert SQLite Row objects to standard Python dictionaries for JSON serialization
                records = [dict(row) for row in cur.fetchall()]
                
                return jsonify({
                    'status': 'ok',
                    'data': records,
                    'debug_sql': query,    # unsafe, remove in production
                    'debug_params': params # unsafe, remove in production
                })
                
            else:
                # Commit mutations (Insert/Update/Delete) and fetch affected rows
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
        # Validation / Configuration errors - the payload was rejected.
        # This is the client's fault.
        return jsonify({'status': 'error', 'message': str(e)}), 400

    except sqlite3.IntegrityError as e:
        # Constraint violation (UNIQUE, FK, NOT NULL) - the payload
        # conflicts with the current database state.
        return jsonify({
            'status': 'error',
            'message': 'Database integrity violation.',
            'details': str(e)
        }), 400

    except Exception:
        # Anything else is a bug or an infrastructure failure on our side.
        # Log the traceback for debugging, return a generic message to
        # the client (don't leak internal details).
        app.logger.exception("unhandled error in /api/%s/%s", source, action)
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True)