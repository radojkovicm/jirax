"""SQLite persistence layer for JiraX Time Tracker."""
import sqlite3

DEFAULT_CATEGORIES = [
    'Business Central', 'Pantheon', 'iWare', 'SQL',
    'Laptops', 'Hardware', 'Meeting', 'Other',
]


class Database:
    """Owns the SQLite connection and schema for the time tracker."""

    def __init__(self, db_path='time_tracker.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute('PRAGMA encoding="UTF-8"')
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            user_id INTEGER,
            category_id INTEGER,
            task_name TEXT NOT NULL,
            description TEXT,
            hours_spent REAL NOT NULL,
            start_time TEXT,
            end_time TEXT,
            priority TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY,
            task_name TEXT NOT NULL,
            user_id INTEGER,
            category_id INTEGER,
            description TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category_id)')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS future_tasks (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            user_id INTEGER,
            category_id INTEGER,
            task_name TEXT NOT NULL,
            description TEXT,
            priority TEXT,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_future_tasks_date ON future_tasks(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_future_tasks_completed ON future_tasks(completed)')

        try:
            for category in DEFAULT_CATEGORIES:
                cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def close(self):
        self.conn.close()
