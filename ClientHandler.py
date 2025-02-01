class ClientHandler:
    def __init__(self, client_socket, address):
        self.client_socket = client_socket
        self.address = address

    def handle(self):
        print(f"Connected by {self.address}")
        try:
            while True:
                data = self.client_socket.recv(1024)
                if not data:
                    break
                print(f"Received from {self.address}: {data.decode()}")
                self.client_socket.sendall(b"ACK")
        except Exception as e:
            print(f"Error handling client {self.address}: {e}")
        finally:
            self.client_socket.close()
            print(f"Disconnected from {self.address}")
