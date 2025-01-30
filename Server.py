import socket
import threading
from Network import Network

class Server(Network):
    def __init__(self, host, port):
        super().__init__(host, port)
        self.client = {} # dictionary to store client socket objects. For each client, we store the client socket object in the dictionary, with the client's address as the key and the client socket object as the value.
        
    def handle_client(self, client_socket: socket, client_address):
        # Handle each client connection in a separate thread
        
        try:
            while True:
                data = client_socket.socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                print(f"Received data from {client_address}: {data}")
                
                command, *args = data.split("|")
                
                if command == "send":
                    receiver, encrypted_message = args
        
        except:
            pass
        finally:
            client_socket.close()