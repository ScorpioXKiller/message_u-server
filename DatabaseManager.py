import sqlite3
import logging
import os
import threading

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()
    db_file = "defensive.db"

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS clients(
            ID BLOB PRIMARY KEY,
            UserName TEXT NOT NULL,
            LastSeen TEXT
        )''')

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS messages(
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ToClient BLOB NOT NULL,
            FromClient BLOB NOT NULL,
            Type INTEGER NOT NULL,
            Content BLOB NOT NULL
        )''')

        self.conn.commit()
        logging.info("Database initialized.")

    def add_client(self, client_id, username, last_seen):
        with self._lock:
            self.cursor.execute("INSERT INTO clients (ID, UserName, LastSeen) VALUES (?, ?, ?)", (client_id, username, last_seen))
            self.conn.commit()

    def get_clients(self):
        with self._lock:
            self.cursor.execute("SELECT ID, UserName, LastSeen FROM clients")
            return self.cursor.fetchall()
        
    def add_message(self, to_client, from_client, msg_type, content):
        with self._lock:
            self.cursor.execute("INSERT IMTO messages (ToClient, FromClient, Type, Content) VALUES (?, ?, ?, ?)", (to_client, from_client, msg_type, content))
            self.conn.commit()

    def get_pending_messages(self, client_id):
        with self._lock:
            self.cursor.execute("SELECT ID, FromClient, Type, Content FROM messages WHERE ToClient = ?", (client_id,))
            messages = self.cursor.fetchall()
            self.cursor.execute("DELETE FROM messages WHERE ToClient = ?", (client_id,))
            self.conn.commit()
            return messages