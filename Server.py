import socket
import selectors
import threading
from ClientHandler import ClientHandler

PORT_FILE = "myport.info"
DEFAULT_PORT = 1357

class Server:
    def __init__(self):
        self.port = self.get_port()
        self.selector = selectors.DefaultSelector()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.running = True

    def get_port(self):
        try: 
            with open(PORT_FILE, "r") as file:
                port_data = file.read().strip()
                if not port_data:
                    print("Warning: Port file is empty. Using default port.") 
                    return DEFAULT_PORT
                return int(port_data) if port_data else DEFAULT_PORT
        except (FileNotFoundError):
            print("Warning: Port file not found. Using default port.")
            return DEFAULT_PORT
        except (ValueError):
            print("Warning: Port file contains invalid data. Using default port.")
            return DEFAULT_PORT
        
    def start(self):
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen()
        print(f"Server listening on port {self.port}")

        threading.Thread(target=self.shutdown, daemon=True).start()

        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_handler = ClientHandler(client_socket, address)
                threading.Thread(target=client_handler.handle, daemon=True).start()
                self.clients.append(client_handler)
                print(f"Number of clients: {len(self.clients)}")
            except OSError as e:
                print(f"Error accepting client: {e}")
                break

    def shutdown(self):
        while self.running:
            if input().strip().lower() == "q":
                self.running = False
                self.server_socket.close()
                print("Server shutting down...")
                break