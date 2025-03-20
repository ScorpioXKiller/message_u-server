"""
@file RequestsHandler.py
@brief Implements request handlers for the MessageU project.
@details This module defines the RequestData dataclass and the abstract RequestHandler base class,
         along with concrete implementations for handling registration, retrieving clients, fetching
         public keys, sending messages, and retrieving pending messages.
@version 2.0
@author Dmitriy Gorodov
@id 342725405
@date 19/03/2025
"""
import logging
import uuid
import socket
import struct
from dataclasses import dataclass
from abc import ABC as AbstractClass, abstractmethod
from DatabaseManager import DatabaseManager
from ResponseBuilder import ResponseBuilder, ResponseData
from config import (
    CLIENT_ID_SIZE, 
    USERNAME_SIZE, 
    PUBLIC_KEY_SIZE, 
    MESSAGE_TYPE_BYTES, 
    CONTENT_LENGTH_BYTES, 
    MESSAGE_HEADER_SIZE
)
import response_status_codes as response_status

@dataclass
class RequestData:
    """
    @brief Data structure representing an incoming client request.
    
    Contains the client ID, version, request code, payload size, and the actual payload.
    """
    client_id: bytes = b""
    version: int = 0
    code: int = 0
    payload_size: int = 0
    payload: bytes = b""

class RequestHandler(AbstractClass):
    """
    @brief Abstract base class for all request handlers.
    
    Subclasses must implement the handle() method to process specific request types.
    """
    def __init__(self, code: int, db: DatabaseManager):
        self.code = code
        self.db = db
        self.response = ResponseBuilder()

    @abstractmethod
    def handle(self, request: RequestData, conn: socket.socket):
        """
        @brief Processes the client request.
        @param request The request data.
        @param conn The client socket connection.
        """
        pass

    def send_error_response(self, error_code: int, message: bytes, conn: socket.socket) -> None:
        """
        @brief Sends an error response to the client.
        @param error_code The error response code.
        @param message The error message.
        @param conn The client socket.
        """
        logging.error(message.decode('ascii'))
        res = self.response.build(ResponseData(error_code))
        conn.sendall(res)
    
class RegistrationHandler(RequestHandler):
    """
    @brief Handles registration requests (code 600).
    """
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn: socket.socket):
        """
        @brief Processes a registration request.
        @param request The request data.
        @param conn The client socket.
        """
        payload = request.payload
        expected_payload_size = USERNAME_SIZE + PUBLIC_KEY_SIZE
        if request.payload_size != expected_payload_size:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid payload size for registration.", conn)
            return
        
        username_bytes: bytes = payload[:USERNAME_SIZE]
        public_key_bytes: bytes = payload[USERNAME_SIZE:]

        try:
            username = username_bytes.decode('ascii').rstrip('\x00')
        except Exception:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Username decode error.", conn)
            return

        if self.db.clients_table.get_client_by_username(username) is not None:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Username already exists.", conn)
            return
        
        new_client_id = uuid.uuid4().bytes
        logging.info(f"Registering new client: {username} with id: {new_client_id.hex()}")
        self.db.clients_table.add_client(new_client_id, username, public_key_bytes, "Not Available")
        res = self.response.build(ResponseData(response_status.REGISTRATION_SUCCESS, len(new_client_id), new_client_id))
        conn.sendall(res)
    
class RetrieveClientsHandler(RequestHandler):
    """
    @brief Handles requests for retrieving the client list (code 601).
    """
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn: socket.socket):
        """
        @brief Processes a request to retrieve the list of clients.
        @param request The request data.
        @param conn The client socket.
        """
        client_id = request.client_id
        clients: list = self.db.clients_table.get_clients()
        payload_bytes = b""
        for client in clients:
            cl_id, c_username, _ = client
            if cl_id == client_id:
                continue
            try:
                username_bytes = c_username.encode('ascii')
            except Exception:
                logging.error(f"Error encoding username: {c_username}")
                continue

            if len(username_bytes) < USERNAME_SIZE:
                username_bytes = username_bytes + b'\x00' * (USERNAME_SIZE - len(username_bytes))
            elif len(username_bytes) > USERNAME_SIZE:
                username_bytes = username_bytes[:USERNAME_SIZE - 1] + b'\x00'
            payload_bytes += cl_id + username_bytes
        res = self.response.build(ResponseData(response_status.USER_LIST, len(payload_bytes), payload_bytes))
        conn.sendall(res)

class RetrievePublicKeyHandler(RequestHandler):
    """
    @brief Handles requests for retrieving a client's public key (code 602).
    """
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn:socket.socket):
        """
        @brief Processes a public key request.
        @param request The request data.
        @param conn The client socket.
        """
        payload = request.payload

        if request.payload_size != CLIENT_ID_SIZE:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid payload size for public key retrieval.", conn)
            return
        
        target_client_id = payload
        
        target_client = self.db.clients_table.get_client_by_id(target_client_id)
        if target_client is None:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Client not found.", conn)
            return
        
        target_id, _, public_key, _ = target_client
        if len(public_key) != PUBLIC_KEY_SIZE:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid public key size.", conn)
            return
        
        reponse_payload = target_id + public_key
        res = self.response.build(ResponseData(response_status.PUBLIC_KEY, len(reponse_payload), reponse_payload))
        conn.sendall(res)

class SendMessageHandler(RequestHandler):
    """
    @brief Handles sending messages to clients (code 603).
    """
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn):
        """
        @brief Processes a send message request.
        @param request The request data.
        @param conn The client socket.
        """
        payload = request.payload
        if request.payload_size < MESSAGE_HEADER_SIZE:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid payload size for message.", conn)
            return
                
        target_client_id = payload[:CLIENT_ID_SIZE]
        message_type = payload[CLIENT_ID_SIZE]
        
        start = CLIENT_ID_SIZE + MESSAGE_TYPE_BYTES
        end = start + CONTENT_LENGTH_BYTES
        content_size = struct.unpack("<I", payload[start:end])[0]

        expected_payload_size = MESSAGE_HEADER_SIZE + content_size

        if len(payload) != expected_payload_size:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Payload size does not match content size.", conn)
            return
                
        message_content = payload[MESSAGE_HEADER_SIZE:MESSAGE_HEADER_SIZE+content_size]

        if content_size == 0:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Empty message content.", conn)
            return
                
        message_id = self.db.messages_table.add_message(target_client_id, request.client_id, message_type, message_content)
        if message_id is None:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Failed to store message.", conn)
            return
                
        response_payload = target_client_id + struct.pack("<I", message_id)
        res = self.response.build(ResponseData(response_status.MESSAGE_SENT, len(response_payload), response_payload))
        conn.sendall(res)

class RetrievePendingMessageHandler(RequestHandler):
    """
    @brief Handles requests for retrieving pending messages (code 604).
    """
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn):
        """
        @brief Processes a request for pending messages.
        @param request The request data.
        @param conn The client socket.
        """
        if request.payload_size != 0:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid payload size for retrieving pending messages.", conn)
            return
        
        messages = self.db.messages_table.get_pending_messages(request.client_id)
        payload_bytes = b""

        for message in messages:
            msg_id, from_client, msg_type, content = message
            content_size = len(content)
            record = from_client + struct.pack("<I", msg_id) + struct.pack("<B", int(msg_type)) + struct.pack("<I", content_size) + content
            payload_bytes += record

        res = self.response.build(ResponseData(response_status.PENDING_MESSAGES_RECEIVED, len(payload_bytes), payload_bytes))
        self.db.messages_table.remove_messages(request.client_id)
        conn.sendall(res)