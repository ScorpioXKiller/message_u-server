# MessageU Server

## Overview

The MessageU Server is a Python-based TCP server that implements a stateless, binary protocol for a secure client–server messaging system. It handles multiple concurrent client connections using non-blocking sockets and the `selectors` module. The server supports various request types such as registration, client list retrieval, public key requests, message sending, and pending messages retrieval.

## Features

- **Stateless Protocol:** Processes each client request independently.
- **Non-blocking I/O:** Uses Python’s `selectors` module and non-blocking sockets.
- **Threading:** A separate thread is used to listen for a shutdown command.
- **Database Integration:** Uses SQLite (via `sqlite3`) to store client and message data.
- **Modular Design:** Request handling is delegated to specialized handler classes.
- **Logging:** Detailed logging is provided for monitoring server activity.

## Prerequisites

- **Python 3.x**
- Required Python modules:
  - `socket`
  - `selectors`
  - `threading`
  - `sqlite3`
  - `logging`
  - `struct`
  - `time`
- A valid `myport.info` file in the server’s folder containing the port number (if not, the default port 1357 is used).
- A configuration file (`config.py`) that defines constants (e.g., `DEFAULT_PORT`, `HEADER_SIZE`, etc.).

## Setup and Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd <repository-folder>/server
   ```

2. **(Optional) Create a virtual environment and install dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Ensure that the configuration file (`config.py`) and port file (`myport.info`) are in the server folder.**

## Running the Server

Start the server by running:

```bash
python main.py
```

The server will listen on the port specified in `myport.info` (or the default port 1357). Press `q` followed by Enter in the console to shut down the server.

## Project Structure

- **Server.py:** Main server implementation handling connections and request dispatching.
- **DatabaseManager.py:** Contains classes for managing the SQLite database (clients and messages tables).
- **RequestsHandler.py:** Implements various request handlers for processing different client requests.
- **ResponseBuilder.py:** Builds responses according to the protocol.
- **config.py:** Contains configuration constants used throughout the server.
- **main.py:** Entry point for starting the server.

## Documentation

Doxygen-style documentation is provided within the source files. To generate the documentation:

1. Run `doxygen -g` to create a default Doxyfile.
2. Configure the INPUT paths to include the server source files.
3. Run `doxygen` to generate the documentation.

## Known Issues / Future Work

- Further enhancements for robust error handling and rate limiting.
- Potential improvements in key management and replay attack prevention.
- Performance tuning for handling large payloads.
