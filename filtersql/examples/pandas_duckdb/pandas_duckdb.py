"""
Cookbook: filtersql + Pandas + DuckDB
Query DataFrame with SQL using filtersql
"""

import pandas as pd
import duckdb
from filtersql import filtersql

df = pd.DataFrame({
    'id': [1, 2, 3, 4, 5],
    'first_name': ['John', 'Robert', 'Brian', 'Mick', 'Paul'],
    'last_name': ['White', 'Smith', 'Page', 'Gray', 'Jones'],
    'age': [32, 28, 45, 34, 29],
    'status': ['active', 'active', 'inactive', 'active', 'active']
})

print("Original DataFrame:")
print(df)
print("\n" + "="*50 + "\n")

conn = duckdb.connect()
conn.register('users', df)

def query_to_df(payload, **kwargs):
    """Helper: filtersql → DuckDB → DataFrame"""
    query, params = filtersql(payload, dbms='DuckDB', **kwargs)
    print(query)
    print(params)
    return conn.execute(query, params).fetchdf()

print("1. Active users:\n")
result = query_to_df({
    'action': 'select',
    'source': 'users',
    'columns': ['id', 'first_name', 'last_name'],
    'filters': [{'field': 'status', 'operator': '=', 'value': 'active'}]
})
print(result)
print("\n" + "-"*30 + "\n")


print("2. Active users, age >= 30:\n")
result = query_to_df({
    'action': 'select',
    'source': 'users',
    'columns': ['first_name', 'last_name', 'age'],
    'filters': [
        {'field': 'status', 'operator': '=', 'value': 'active'},
        {'field': 'age', 'operator': '>=', 'value': 30}
    ],
    'order': [{'field': 'age', 'order': 'desc'}]
})
print(result)
print("\n" + "-"*30 + "\n")


print("3. Count by status:\n")
result = query_to_df({
    'action': 'select',
    'source': 'users',
    'columns': [
        {'field': 'status', 'alias': 'status_group'},
        {'field': 'COUNT(*)', 'raw': True, 'alias': 'count'}
    ],
    'group_by': ['status'],
    'order': [{'field': 'count', 'order': 'desc'}]
})
print(result)
print("\n" + "-"*30 + "\n")

print("4. AI generated filters (simulation):\n")
ai_filters = [
    {'field': 'first_name', 'operator': 'icontains', 'value': 'john'},
    {'field': 'age', 'operator': '>=', 'value': 30}
]

result = query_to_df({
    'action': 'select',
    'source': 'users',
    'columns': ['first_name', 'last_name', 'age'],
    'filters': ai_filters
})
print(result)
