"""
@file ResponseBuilder.py
@brief Provides functionality to build binary responses.
@details This module defines the ResponseData dataclass and ResponseBuilder class used to construct
         binary responses according to the MessageU protocol.
@version 2.0
@author Dmitriy Gorodov
@id 342725405
@date 19/03/2025
"""

import struct
from config import SERVER_VERSION
from response_status_codes import RESPONSE_ERROR
from dataclasses import dataclass

@dataclass
class ResponseData:
    """
    @brief Data structure representing a server response.
    
    Contains the response code, payload size, payload, and server version.
    """
    code: int = 0
    payload_size: int = 0
    payload: bytes = b""
    version: int = SERVER_VERSION

class ResponseBuilder:
    """
    @brief Builds binary responses for the MessageU project.
    
    Constructs the response header and concatenates it with the payload.
    """
    def build(self, response: ResponseData):
        """
        @brief Constructs a binary response.
        @param response A ResponseData instance containing the response details.
        @return A bytes object representing the complete binary response.
        """
        header = struct.pack("<B H I", response.version, response.code, response.payload_size)
        if response.code == RESPONSE_ERROR:
            return header
        return header + response.payload