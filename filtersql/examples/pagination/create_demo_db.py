# create_demo_db.py
import sqlite3
import random
from filtersql import Datasource

random.seed(42)

FIRST_NAMES = [
    'John', 'Jane', 'Alice', 'Bob', 'Carlo', 'Maria', 'Luca', 'Sara', 'Cliff', 'Thomas',
    'Emma', 'Oliver', 'Sophia', 'Liam', 'Isabella', 'Mason', 'Mia', 'Ethan', 'Amelia', 'Logan',
    'Giulia', 'Matteo', 'Chiara', 'Alessandro', 'Francesca', 'Lorenzo', 'Martina', 'Andrea', 'Elena', 'Giovanni',
    'David', 'Sarah', 'Michael', 'Emily', 'James', 'Jessica', 'William', 'Ashley', 'Robert', 'Amanda',
    'Daniel', 'Chloe', 'Matthew', 'Grace', 'Anthony', 'Lily', 'Mark', 'Ella', 'Steven', 'Aria'
]

LAST_NAMES = [
    'Smith', 'Rossi', 'Bianchi', 'Jones', 'Ferrari', 'Brown', 'Reed', 'Nelson', 'Baker',
    'Taylor', 'Williams', 'Davis', 'Miller', 'Wilson', 'Moore', 'Anderson', 'Thomas', 'Jackson', 'White',
    'Esposito', 'Ricci', 'Romano', 'Colombo', 'Gallo', 'Conti', 'Costa', 'Giordano', 'Rizzo', 'Lombardi',
    'Clark', 'Lewis', 'Walker', 'Hall', 'Allen', 'Young', 'King', 'Wright', 'Hill', 'Scott',
    'Green', 'Adams', 'Hughes', 'Gonzalez', 'Carter', 'Mitchell', 'Perez', 'Roberts', 'Turner', 'Phillips'
]

ROLES = ['admin', 'editor', 'viewer']
STATUSES = ['active', 'inactive']
PROVIDERS = ['demo.net', 'example.com', 'test.org', 'null.org', 'mockmail.com']

conn = sqlite3.connect('demo.db')
conn.execute('DROP TABLE IF EXISTS users')
conn.execute('''
    CREATE TABLE users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id     INTEGER NOT NULL,
        first_name    TEXT NOT NULL,
        last_name     TEXT NOT NULL,
        email         TEXT NOT NULL,
        age           INTEGER,
        status        TEXT,
        role          TEXT,
        password_hash TEXT
    )
''')
conn.commit()

ds = Datasource(source='users', dbms='sqlite')

for i in range(500):
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    tenant = 42 if random.random() < 0.9 else 99
    
    query, values = ds.insert(values={
        'tenant_id':    tenant,
        'first_name':   first,
        'last_name':    last,
        'email':        f'{first.lower()}.{last.lower()}{i}@{random.choice(PROVIDERS)}',
        'age':          random.randint(20, 65),
        'status':       random.choice(STATUSES),
        'role':         random.choice(ROLES),
        'password_hash': f'hash_{i}'
    })
    conn.execute(query, values)

conn.commit()
conn.close()
print("demo.db successfully created with 500 rows (distributed between tenant 42 and 99).")