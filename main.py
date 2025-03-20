"""
@file main.py
@brief Entry point for the MessageU server.
       This module initializes logging and starts the server.
@version 2.0
@author Dmitriy Gorodov
@id 342725405
@date 19/03/2025
"""

import logging
from Server import Server

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    server = Server()
    
    try:
        server.start()
    except KeyboardInterrupt:
        logging.info("Server stopped manually.")

if __name__ == "__main__":
    main()