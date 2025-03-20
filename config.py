"""
@file config.py
@brief General configuration constants for the MessageU project.
@details Defines various constants used throughout the project, including server settings,
         data sizes, and protocol-specific parameters.
@version 2.0
@author Dmitriy Gorodov
@id 342725405
@date 19/03/2025
"""

# General server configuration
SERVER_VERSION: int = 2
PORT_FILE: str = "myport.info"
DATABASE_FILE: str = "defensive.db"
DEFAULT_PORT: int = 1357
MAX_CONNECTIONS: int = 100
HEADER_SIZE: int = 23
MESSAGE_TYPE_MAX: int = 255
CHUNK_SIZE: int = 4096
TIME_DELAY: float = 0.01  # 10 ms

# Request/Response data sizes
CLIENT_ID_SIZE: int = 16
USERNAME_SIZE: int = 255
PUBLIC_KEY_SIZE: int = 160
MESSAGE_TYPE_BYTES: int = 1
CONTENT_LENGTH_BYTES: int = 4
MESSAGE_HEADER_SIZE: int = CLIENT_ID_SIZE + MESSAGE_TYPE_BYTES + CONTENT_LENGTH_BYTES