import logging
import uuid
import socket
import struct
from enum import Enum
from dataclasses import dataclass
from abc import ABC as AbstractClass, abstractmethod
from DatabaseManager import DatabaseManager
from ResponseBuilder import ResponseBuilder, ResponseData
from config import CLIENT_ID_SIZE, USERNAME_SIZE, PUBLIC_KEY_SIZE, MESSAGE_TYPE_BYTES, CONTENT_LENGTH_BYTES, MESSAGE_HEADER_SIZE
import response_status_codes as response_status

class MessageTypes(Enum):
    SYMMETRIC_KEY_REQUEST = 1
    SYMMETRIC_KEY_SEND = 2
    TEXT_MESSAGE_SEND = 3

@dataclass
class RequestData:
    client_id: bytes = b""
    version: int = 0
    code: int = 0
    payload_size: int = 0
    payload: bytes = b""

class RequestHandler(AbstractClass):
    def __init__(self, code: int, db: DatabaseManager):
        self.code = code
        self.db = db
        self.response = ResponseBuilder()

    @abstractmethod
    def handle(self, request: RequestData, conn: socket.socket):
        pass

    def send_error_response(self, error_code: int, message: bytes, conn: socket.socket) -> None:
        logging.error(message.decode('ascii'))
        res = self.response.build(ResponseData(error_code, len(message), message))
        conn.sendall(res)
    
class RegistrationHandler(RequestHandler):
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn: socket.socket):
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

        if self.db.get_client_by_username(username) is not None:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Username already exists.", conn)
            return
        
        # Create new client UUID (16 bytes)
        new_client_id = uuid.uuid4().bytes
        logging.info(f"Registering new client: {username} with id: {new_client_id.hex()}")
        self.db.add_client(new_client_id, username, public_key_bytes, "Not Available")
        # Respond with code 2100 and the new client id as payload
        res = self.response.build(ResponseData(response_status.REGISTRATION_SUCCESS, len(new_client_id), new_client_id))
        conn.sendall(res)
    
class RetrieveClientsHandler(RequestHandler):
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn: socket.socket):
        client_id = request.client_id
        # For user list (code 601), there is no payload.
        clients: list = self.db.get_clients()
        payload_bytes = b""
        for client in clients:
            cl_id, c_username, _ = client  # c is (ID, UserName, LastSeen)
            if cl_id == client_id:
                continue  # Do not include the requester
            try:
                username_bytes = c_username.encode('ascii')
            except Exception:
                logging.error(f"Error encoding username: {c_username}")
                continue
            # Ensure the username is exactly 255 bytes (padded with null bytes if necessary)
            if len(username_bytes) < USERNAME_SIZE:
                username_bytes = username_bytes + b'\x00' * (USERNAME_SIZE - len(username_bytes))
            elif len(username_bytes) > USERNAME_SIZE:
                username_bytes = username_bytes[:USERNAME_SIZE - 1] + b'\x00'
            payload_bytes += cl_id + username_bytes
        res = self.response.build(ResponseData(response_status.USER_LIST, len(payload_bytes), payload_bytes))
        conn.sendall(res)

class RetrievePublicKeyHandler(RequestHandler):
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn:socket.socket):
        payload = request.payload

        if request.payload_size != CLIENT_ID_SIZE:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid payload size for public key retrieval.", conn)
            return
        
        target_client_id = payload
        
        target_client = self.db.get_client_by_id(target_client_id)
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
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn):
        payload = request.payload
        if request.payload_size < MESSAGE_HEADER_SIZE:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid payload size for message.", conn)
            return
                
        target_client_id = payload[:CLIENT_ID_SIZE]
        message_type_byte = payload[CLIENT_ID_SIZE]
        try:
            message_type = MessageTypes(message_type_byte)
        except ValueError:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid message type.", conn)
            return
        
        start = CLIENT_ID_SIZE + MESSAGE_TYPE_BYTES
        end = start + CONTENT_LENGTH_BYTES
        content_size = struct.unpack("<I", payload[start:end])[0]

        expected_payload_size = MESSAGE_HEADER_SIZE + content_size
        if len(payload) != expected_payload_size:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Payload size does not match content size.", conn)
            return
                
        message_content = payload[MESSAGE_HEADER_SIZE:MESSAGE_HEADER_SIZE+content_size]

        if message_type == MessageTypes.SYMMETRIC_KEY_REQUEST:
            if content_size != 0:
                self.send_error_response(response_status.RESPONSE_ERROR, b"Symmetric key request must not contain any content.", conn)
                return
        elif message_type == MessageTypes.SYMMETRIC_KEY_SEND:
            if content_size == 0:
                self.send_error_response(response_status.RESPONSE_ERROR, b"Symmetric key send must include encrypted key content.", conn)
                return
        elif message_type == MessageTypes.TEXT_MESSAGE_SEND:
            if content_size == 0:
                self.send_error_response(response_status.RESPONSE_ERROR, b"Text message send must include encrypted text content.", conn)
                return
                
        message_id = self.db.add_message(target_client_id, request.client_id, message_type_byte, message_content)
        if message_id is None:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Failed to store message.", conn)
            return
                
        response_payload = target_client_id + struct.pack("<I", message_id)
        res = self.response.build(ResponseData(response_status.MESSAGE_SENT, len(response_payload), response_payload))
        conn.sendall(res)

class RetrievePendingMessageHandler(RequestHandler):
    def __init__(self, code: int, db: DatabaseManager):
        super().__init__(code, db)

    def handle(self, request: RequestData, conn):
        if request.payload_size != 0:
            self.send_error_response(response_status.RESPONSE_ERROR, b"Invalid payload size for retrieving pending messages.", conn)
            return
        
        messages = self.db.get_pending_messages(request.client_id)
        payload_bytes = b""

        for message in messages:
            msg_id, from_client, msg_type, content = message
            content_size = len(content)
            record = from_client + struct.pack("<I", msg_id) + struct.pack("<B", msg_type) + struct.pack("<I", content_size) + content
            payload_bytes += record

        res = self.response.build(ResponseData(response_status.PENDING_MESSAGES_RECEIVED, len(payload_bytes), payload_bytes))
        conn.sendall(res)