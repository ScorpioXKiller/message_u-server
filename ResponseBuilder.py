import struct
from config import SERVER_VERSION
from dataclasses import dataclass

@dataclass
class ResponseData:
    code: int = 0
    payload_size: int = 0
    payload: bytes = b""
    version: int = SERVER_VERSION

class ResponseBuilder:
    def build(self, response: ResponseData):
        header = struct.pack("<B H I", response.version, response.code, response.payload_size)
        return header + response.payload