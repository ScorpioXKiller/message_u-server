"""
@file Server.py
@brief Implements the TCP server for the MessageU project.
@details This server uses non-blocking sockets and a selector to handle multiple client
         connections concurrently. It processes binary protocol requests from clients,
         dispatches them to the appropriate request handlers, and updates each client's 
         LastSeen timestamp.
@version 2.0
@author Dmitriy Gorodov
@id 342725405
@date 19/03/2025
@note The server is designed to run on Windows.
"""

import socket
import selectors
import threading  # Uses threading module to create a separate thread for the shutdown listener.
import logging
import struct
import time
from DatabaseManager import DatabaseManager
from RequestsHandler import (
    RequestData,
    RequestHandler, 
    RegistrationHandler, 
    RetrieveClientsHandler, 
    RetrievePublicKeyHandler,
    SendMessageHandler,
    RetrievePendingMessageHandler,
)
from config import (
    PORT_FILE, 
    DEFAULT_PORT, 
    MAX_CONNECTIONS, 
    HEADER_SIZE,
    CHUNK_SIZE,
    TIME_DELAY
)
import request_status_codes as request_status

class Server:
    """
    @brief Main server class for the MessageU project.

    This class handles the initialization of the server socket, accepts incoming
    client connections, reads and processes requests, dispatches them to the 
    corresponding request handlers, and updates the client's LastSeen timestamp.
    """

    def __init__(self):
        """
        @brief Constructs a new Server instance.

        Initializes the listening port, selector, database, and request handler dictionary.
        """
        self.port = self.get_port()
        self.selector = selectors.DefaultSelector()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.running = True
        self.db = DatabaseManager()

        # Request dispatcher dictionary to handle different requests.
        self.request_handlers = {
            request_status.REGISTER_CLIENT: RegistrationHandler(request_status.REGISTER_CLIENT, self.db),
            request_status.LIST_ALL_CLIENTS: RetrieveClientsHandler(request_status.LIST_ALL_CLIENTS, self.db),
            request_status.FETCH_PUBLIC_KEY: RetrievePublicKeyHandler(request_status.FETCH_PUBLIC_KEY, self.db),
            request_status.SEND_MESSAGE: SendMessageHandler(request_status.SEND_MESSAGE, self.db),
            request_status.LIST_PENDING_MESSAGES: RetrievePendingMessageHandler(request_status.LIST_PENDING_MESSAGES, self.db),
        }

    def get_port(self):
        """
        @brief Retrieves the server port from a file.
        
        Reads the port number from the file specified by PORT_FILE. If the file does not exist,
        is empty, or contains invalid data, returns DEFAULT_PORT.
        
        @return int The port number to bind the server socket.
        """
        try: 
            with open(PORT_FILE, "r") as file:
                port_data = file.read().strip()
                if not port_data:
                    logging.warning(f"Port file is empty. Using default port {DEFAULT_PORT}")
                    return DEFAULT_PORT
                return int(port_data)
        except (FileNotFoundError):
            logging.warning("Port file not found. Using default port.")
            return DEFAULT_PORT
        except (ValueError):
            logging.warning("Port file contains invalid data. Using default port.")
            return DEFAULT_PORT
        
    def accept(self, sock: socket.socket, _):
        """
        @brief Accepts a new client connection.

        Accepts a connection from the listening socket, sets it to non-blocking mode,
        and registers it with the selector.
        
        @param sock The listening socket.
        @param _ Unused selector mask.
        """
        try:
            conn, addr = sock.accept()
            conn.setblocking(False)
            logging.info(f"Accepted connection from {addr}")
            with self.clients_lock:
                self.clients.add(conn)
            self.selector.register(conn, selectors.EVENT_READ, self.read)
        except OSError:
            logging.error("Error accepting new connection")

    def read(self, conn: socket.socket, _):
        """
        @brief Reads and processes a request from a client.
        
        This method reads a fixed-size header, then reads the payload based on the header's
        payload size field. If the full payload is not received, the connection is closed.
        The request is then dispatched to the appropriate handler based on the request code,
        and the client's LastSeen timestamp is updated.
        
        @param conn The client socket.
        @param _ Unused selector mask.
        """
        try:
            header_data = conn.recv(HEADER_SIZE)
            if not header_data:
                self.close_connection(conn)
                return
            if len(header_data) < HEADER_SIZE:
                logging.error("Incomplete header received.")
                self.close_connection(conn)
                return
            
            header_format = "<16s B H I"
            client_id, version, code, payload_size = struct.unpack(header_format, header_data)
            payload = b""

            # Read payload in chunks up to CHUNK_SIZE and handle non-blocking socket delays.
            while len(payload) < payload_size:
                try:
                    to_read = min(payload_size - len(payload), CHUNK_SIZE)
                    chunk = conn.recv(to_read)
                except OSError as e:
                    if hasattr(e, "errno") and e.errno == 10035:
                        time.sleep(TIME_DELAY)
                        continue
                    else:
                        raise
                if not chunk:
                    break
                payload += chunk

            if len(payload) != payload_size:
                logging.error("Incomplete payload received.")
                self.close_connection(conn)
                return
            
            logging.info(f"Received request: client_id: {client_id.hex()}, version: {version}, code: {code}, payload size: {payload_size}")

            # Dispatch request to the appropriate handler based on the request code.
            if (code not in self.request_handlers):
                raise ValueError(f"Invalid request code: {code}")
    
            handler: RequestHandler = self.request_handlers.get(code)
            handler.handle(RequestData(client_id, version, code, payload_size, payload), conn)

            self.db.clients_table.update_last_seen(client_id)
        except Exception as e:
            logging.error(f"Error reading request: {e}")
            self.close_connection(conn)

    def close_connection(self, conn: socket.socket):
        """
        @brief Closes a client connection and unregisters it from the selector.
        
        @param conn The client socket to close.
        """
        try:
            logging.info(f"Closing connection to {conn.getpeername()}")
            self.selector.unregister(conn)
            with self.clients_lock:
                self.clients.discard(conn)
            conn.close()
        except Exception as e:
            logging.error(f"Error closing connection: {e}")

    def shutdown_listener(self):
        """
        @brief Listens for the shutdown command from the console.
        
        When the user enters "q" and presses enter, the server stops running.
        """
        while self.running:
            try:
                if input().strip().lower() == "q":
                    self.running = False
                    break
            except EOFError: 
                logging.error("Cntrl+C has been pressed.")
            
    def start(self):
        """
        @brief Starts the server.
        
        Binds the server socket to the specified port, begins listening for incoming connections,
        and processes events using a selector. The server continues to run until shutdown is requested.
        """
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(MAX_CONNECTIONS)
        self.server_socket.setblocking(False)
        self.selector.register(self.server_socket, selectors.EVENT_READ, self.accept)
        logging.info(f"Server is listening on port {self.port}... Press 'q' to shutdown.")

        threading.Thread(target=self.shutdown_listener, daemon=True).start()

        while self.running:
            events = self.selector.select(timeout=1)
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
            
        logging.info("Server shutting down...")
        self.selector.close()
        self.server_socket.close()