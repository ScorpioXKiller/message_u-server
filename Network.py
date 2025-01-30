import socket
from abc import ABC as abstract, abstractmethod

class Network(abstract):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        
    @abstractmethod
    def send_message(self, message):
        pass
    
    @abstractmethod
    def receive_message(self):
        pass
    
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))