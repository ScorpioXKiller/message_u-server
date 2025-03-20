"""
@file DatabaseManager.py
@brief Provides database management for the MessageU project.
@details This module defines classes to manage the SQLite database, including the clients 
         and messages tables. It handles operations such as creating tables, adding clients,
         retrieving client data, updating the LastSeen timestamp, and managing messages.
@version 2.0
@author Dmitriy Gorodov
@id 342725405
@date 19/03/2025
"""

import sqlite3
import logging
import threading
from config import (
    DATABASE_FILE, 
    CLIENT_ID_SIZE, 
    USERNAME_SIZE,
    PUBLIC_KEY_SIZE,
    MESSAGE_TYPE_MAX
)

class ClientsTable:
    """
    @brief Manages operations on the clients table.
    
    This class provides functions to create the clients table, add a client,
    retrieve client data, and update the LastSeen timestamp.
    """
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock) -> None:
        self.conn = conn
        self.cursor = conn.cursor()
        self.lock = lock

    def create_table(self) -> None:
        """
        @brief Creates the clients table if it does not exist.
        """
        with self.lock:
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS clients(
                ID CHAR(16) NOT NULL PRIMARY KEY,
                UserName CHAR(255) NOT NULL,
                PublicKey CHAR(160) NOT NULL,
                LastSeen DATE
            )''')
            self.conn.commit()
            logging.info("Clients table initialized.")

    def validate_client(self, client_id: bytes, username: str, public_key: str, last_seen: str) -> bool:
        """
        @brief Validates the provided client data.
        @param client_id The client's unique identifier.
        @param username The client's username.
        @param public_key The client's public key.
        @param last_seen The last seen timestamp.
        @return True if the data is valid, False otherwise.
        """
        if not client_id or len(client_id) != CLIENT_ID_SIZE:
            return False
        if not username or len(username) >= USERNAME_SIZE:
            return False
        if not public_key or len(public_key) != PUBLIC_KEY_SIZE:
            return False
        if not last_seen:
            return False
        return True

    def add_client(self, client_id: bytes, username: str, public_key: str, last_seen: str) -> bool:
        """
        @brief Adds a new client to the clients table.
        @param client_id The client's unique identifier.
        @param username The client's username.
        @param public_key The client's public key.
        @param last_seen The current timestamp.
        @return True on success, False on failure.
        """
        if not self.validate_client(client_id, username, public_key, last_seen):
            logging.error("Client validation failed.")
            return False
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT INTO clients (ID, UserName, PublicKey, LastSeen) VALUES (?, ?, ?, ?)",
                    (client_id, username, public_key, last_seen)
                )
                self.conn.commit()
                return True
            except sqlite3.IntegrityError as e:
                logging.error(f"Integrity error adding client: {e}")
                return False

    def get_clients(self):
        """
        @brief Retrieves all clients from the database.
        @return A list of tuples containing client data.
        """
        with self.lock:
            self.cursor.execute("SELECT ID, UserName, LastSeen FROM clients")
            return self.cursor.fetchall()

    def get_client_by_username(self, username: str):
        """
        @brief Retrieves a client by username.
        @param username The client's username.
        @return A tuple with the client's data if found, otherwise None.
        """
        with self.lock:
            self.cursor.execute("SELECT ID FROM clients WHERE UserName = ?", (username,))
            return self.cursor.fetchone()

    def get_client_by_id(self, client_id: bytes):
        """
        @brief Retrieves a client by its unique identifier.
        @param client_id The client's unique identifier.
        @return A tuple with the client's data if found, otherwise None.
        """
        with self.lock:
            self.cursor.execute("SELECT ID, UserName, PublicKey, LastSeen FROM clients WHERE ID = ?", (client_id,))
            return self.cursor.fetchone()

    def update_last_seen(self, client_id: bytes) -> None:
        """
        @brief Updates the LastSeen timestamp for a client.
        @param client_id The client's unique identifier.
        """
        with self.lock:
            self.cursor.execute(
                "UPDATE clients SET LastSeen = datetime('now', 'localtime') WHERE ID = ?",
                (client_id,)
            )
            self.conn.commit()


# Class handling operations on the "messages" table
class MessagesTable:
    """
    @brief Manages operations on the messages table.
    
    Provides functions to create the messages table, add messages,
    retrieve pending messages, and remove messages.
    """
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock) -> None:
        self.conn = conn
        self.cursor = conn.cursor()
        self.lock = lock

    def create_table(self) -> None:
        """
        @brief Creates the messages table if it does not exist.
        """
        with self.lock:
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS messages(
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ToClient CHAR(16) NOT NULL,
                FromClient CHAR(16) NOT NULL,
                Type CHAR(1) NOT NULL,
                Content BLOB,
                FOREIGN KEY(ToClient) REFERENCES clients(ID),
                FOREIGN KEY(FromClient) REFERENCES clients(ID)
            )''')
            self.conn.commit()
            logging.info("Messages table initialized.")

    def validate_message(self, to_client: bytes, from_client: bytes, msg_type: int) -> bool:
        """
        @brief Validates the message data.
        @param to_client The target client's unique identifier.
        @param from_client The sender client's unique identifier.
        @param msg_type The message type.
        @return True if valid, False otherwise.
        """
        if not to_client or len(to_client) != CLIENT_ID_SIZE:
            return False
        if not from_client or len(from_client) != CLIENT_ID_SIZE:
            return False
        if not msg_type or msg_type > MESSAGE_TYPE_MAX:
            return False
        return True

    def add_message(self, to_client: bytes, from_client: bytes, msg_type: int, content: bytes):
        """
        @brief Adds a message to the messages table.
        @param to_client The target client's unique identifier.
        @param from_client The sender client's unique identifier.
        @param msg_type The message type.
        @param content The message content (encrypted).
        @return The last inserted message ID on success, or None on failure.
        """
        if not self.validate_message(to_client, from_client, msg_type):
            logging.error("Message validation failed.")
            return None
        with self.lock:
            self.cursor.execute(
                "INSERT INTO messages (ToClient, FromClient, Type, Content) VALUES (?, ?, ?, ?)",
                (to_client, from_client, msg_type, content)
            )
            self.conn.commit()
            return self.cursor.lastrowid

    def get_pending_messages(self, client_id: bytes):
        """
        @brief Retrieves pending messages for a client.
        @param client_id The client's unique identifier.
        @return A list of message tuples.
        """
        with self.lock:
            self.cursor.execute(
                "SELECT ID, FromClient, Type, Content FROM messages WHERE ToClient = ?",
                (client_id,)
            )
            messages = self.cursor.fetchall()
            return messages

    def remove_messages(self, client_id: bytes) -> None:
        """
        @brief Removes all messages for a given client.
        @param client_id The client's unique identifier.
        """
        with self.lock:
            self.cursor.execute(
                "DELETE FROM messages WHERE ToClient = ?",
                (client_id,)
            )
            self.conn.commit()

    def remove_messages_by_ids(self, message_ids: list[int]) -> None:
        """
        @brief Removes messages with the specified message IDs.
        @param message_ids A list of message IDs to delete.
        """
        with self.lock:
            placeholders = ",".join("?" for _ in message_ids)
            query = f"DELETE FROM messages WHERE ID IN ({placeholders})"
            self.cursor.execute(query, message_ids)
            self.conn.commit()

class DatabaseManager:
    """
    @brief Singleton class that manages the SQLite database.
    
    This class provides a shared database connection and encapsulates the table management
    for both clients and messages.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._init_db()
        return cls._instance

    def _init_db(self) -> None:
        """
        @brief Initializes the database connection and creates the necessary tables.
        """
        self.conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        self.lock = threading.Lock()
        self.clients_table = ClientsTable(self.conn, self.lock)
        self.messages_table = MessagesTable(self.conn, self.lock)
        self.clients_table.create_table()
        self.messages_table.create_table()