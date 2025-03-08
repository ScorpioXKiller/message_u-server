import logging
from Server import Server

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    server = Server()
    
    try:
        server.start()
    except KeyboardInterrupt:
        logging.info("Servrt stopped manually.")

if __name__ == "__main__":
    main()