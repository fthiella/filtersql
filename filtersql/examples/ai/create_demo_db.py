# create_demo_db.py
import sqlite3
import random
from filtersql import Datasource

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
    'Green', 'Adams', 'Baker', 'Gonzalez', 'Carter', 'Mitchell', 'Perez', 'Roberts', 'Turner', 'Phillips'
]

ROLES = ['admin', 'editor', 'viewer']

STATUSES = ['active', 'inactive']

PROVIDERS = [
    'demo.net', 'example.com', 'test.org', 'null.org',
    'mockmail.com', 'fakemail.net', 'sample.org', 'devmail.local',
    'sandbox.com', 'testing.net', 'void.org', 'local.host',
    'noreply.com', 'dummy.net', 'temp.org', 'corp.local',
    'company.com', 'testbed.net', 'lab.org', 'internal.net'
]

conn = sqlite3.connect('demo.db')
conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name  TEXT NOT NULL,
        email      TEXT NOT NULL,
        age        INTEGER,
        status     TEXT,
        role       TEXT
    )
''')
conn.commit()

ds = Datasource(source='users', dbms='SQLite', placeholder='?')

for i in range(500):
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    query, values = ds.insert(values={
        'first_name': first,
        'last_name':  last,
        'email':      f'{first.lower()}.{last.lower()}{i}@example.com',
        'age':        random.randint(20, 65),
        'status':     random.choice(STATUSES),
        'role':       random.choice(ROLES),
    })
    print(ds.debug(query, values))
    conn.execute(query, values)

conn.commit()
conn.close()
print("demo.db created with 500 rows")