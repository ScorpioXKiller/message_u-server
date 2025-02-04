import socket
import selectors
import threading #uses threading module to create a separate thread for the shutdown_listener method
import logging
from DatabaseManager import DatabaseManager 

PORT_FILE = "myport.info"
DEFAULT_PORT = 1357
MAX_CONNECTIONS = 100

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Server:
    def __init__(self):
        self.port = self.get_port()
        self.selector = selectors.DefaultSelector()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.running = True
        self.db = DatabaseManager()

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
        
    def accept(self, sock, _):
        try:
            conn, addr = sock.accept()
            conn.setblocking(False)
            logging.info(f"Accepted connection from {addr}")
            with self.clients_lock:
                self.clients.add(conn)
            self.selector.register(conn, selectors.EVENT_READ, self.read)
        except OSError:
            logging.error("Error accepting new connection")

    def read(self, conn, _):
        try:
            data = conn.recv(1024)
            if data:
                logging.info(f"Recieved from {conn.getpeername()}: {data.decode()}")
                self.db.add_message(b"client_id", b"server", 3, data)
                conn.sendall(b"Message received and stored.")
            else:
                self.close_connection(conn)
        except ConnectionResetError:
            logging.warning(f"Connection reset by peer {conn.getpeername()}")
            self.close_connection(conn)
        except Exception as e:
            logging.error(f"Unexpected error with {conn.getpeername()}: {e}")
            self.close_connection(conn)
            
    def register_client(self, client_id, username, public_key):
        logging.info(f"Registering client {username} with ID {client_id}")
        self.db.add_client(client_id, username, public_key, "Not Available")
        return b"Client registered successfully."
    
    def retrieve_clients(self):
        clients = self.db.get_clients()
        return str(clients).encode()

    def close_connection(self, conn):
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