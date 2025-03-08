import socket
import selectors
import threading #uses threading module to create a separate thread for the shutdown_listener method
import logging
import struct
from DatabaseManager import DatabaseManager
from RequestsHandler import (
    RequestData,
    RequestHandler, 
    RegistrationHandler, 
    RetrieveClientsHandler, 
    RetrievePublicKeyHandler,
    SendMessageHandler,
    RetrievePendingMessageHandler
)
from config import PORT_FILE, DEFAULT_PORT, MAX_CONNECTIONS, HEADER_SIZE
import request_status_codes as request_status

class Server:
    def __init__(self):
        self.port = self.get_port()
        self.selector = selectors.DefaultSelector()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.running = True
        self.db = DatabaseManager()

        # request dispathcer dictionary to handle different requests
        self.request_handlers = {
            request_status.REGISTER_CLIENT: RegistrationHandler(request_status.REGISTER_CLIENT, self.db),
            request_status.LIST_ALL_CLIENTS: RetrieveClientsHandler(request_status.LIST_ALL_CLIENTS, self.db),
            request_status.FETCH_PUBLIC_KEY: RetrievePublicKeyHandler(request_status.FETCH_PUBLIC_KEY, self.db),
            request_status.SEND_MESSAGE: SendMessageHandler(request_status.SEND_MESSAGE, self.db),
            request_status.LIST_PENDING_MESSAGES: RetrievePendingMessageHandler(request_status.LIST_PENDING_MESSAGES, self.db)
        }

    def get_port(self):
        try: 
            with open(PORT_FILE, "r") as file:
                port_data = file.read().strip()
                if not port_data:
                    logging.warning(f"Port file is empty. Using default port {DEFAULT_PORT}")
                    return DEFAULT_PORT
                return int(port_data) # if port_data else DEFAULT_PORT
        except (FileNotFoundError):
            logging.warning("Port file not found. Using default port.")
            return DEFAULT_PORT
        except (ValueError):
            logging.warning("Port file contains invalid data. Using default port.")
            return DEFAULT_PORT
        
    def accept(self, sock: socket.socket, _):
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

            while len(payload) < payload_size:
                chunk = conn.recv(payload_size - len(payload))
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

            self.db.update_last_seen(client_id)
        except Exception as e:
            logging.error(f"Error reading request: {e}")
            self.close_connection(conn)

    def close_connection(self, conn: socket.socket):
        try:
            logging.info(f"Closing connection to {conn.getpeername()}")
            self.selector.unregister(conn)
            with self.clients_lock:
                self.clients.discard(conn)
            conn.close()
        except Exception as e:
            logging.error(f"Error closing connection: {e}")

    def shutdown_listener(self):
        while self.running:
            if input().strip().lower() == "q":
                self.running = False
                break

    def start(self):
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