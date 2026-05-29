# terminal.py

A terminal-based chat client that can run the agent locally or connect to a remote backend over WebSocket.

---

## Requirements

### Local Mode
No additional dependencies beyond the project's existing requirements.

### Remote Mode
Requires the Socket.IO async client:

```bash
pip install "python-socketio[asyncio_client]"
```

> **Windows users:** `readline` (used for up-arrow input history) is not available by default.
> Install `pyreadline3` as a drop-in replacement:
> ```bash
> pip install pyreadline3
> ```

---

## Usage

```bash
python -m backend.terminal [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|---|---|---|---|
| `--debug` | `-d` | `False` | Enables debug mode and prints the session ID on startup |
| `--remote` | `-r` | `False` | Connects to a remote backend via WebSocket instead of running locally |
| `--host HOST` | | `localhost` | Remote backend host (only used with `--remote`) |
| `--port PORT` | | `8000` | Remote backend port (only used with `--remote`) |

---

## Local Mode

Spins up the agent process directly on your machine. No server required.

```bash
# Standard
python -m backend.terminal

# With debug output
python -m backend.terminal --debug
```

---

## Remote Mode

Connects to a running instance of `web_socket.py` on a remote (or local) server.
The agent runs on the server -- your machine only handles input/output.

```bash
# Connect to a server on the local network (default port)
python terminal.py --remote --host 192.168.1.100

# Connect with a custom port
python terminal.py --remote --host 192.168.1.100 --port 8080

# Connect to localhost (e.g. testing against a locally running server)
python terminal.py --remote

# Remote with debug
python terminal.py --remote --host 192.168.1.100 --debug
```

The remote backend must be running before you connect:

```bash
python -m backend.transport.start_web_socket
```

---

## Chat Commands

Once the client is running, the following commands are available at the `Message:` prompt:

| Command | Alias | Description |
|---|---|---|
| `/help` | `/h` | Lists available commands |
| `/save` | `/s` | Saves chat history to a `.txt` file |
| `/save txt` | `/s txt` | Saves chat history as plain text |
| `/save md` | `/s md` | Saves chat history as a Markdown file |
| `/save json` | `/s json` | Saves chat history as a JSON file |
| `/quit` | `/exit`, `/q` | Ends the session and exits |

### Save File Format

Save files are written to the current working directory and named using the session ID and a timestamp:

```text
chat_<session_id>_<YYYYMMDD_HHMMSS>.<ext>
```

Example: `chat_a1b2c3d4_20260506_170000.json`

#### JSON structure

```json
{
  "session_id": "a1b2c3d4",
  "date": "2026-05-06",
  "messages": [
    {
      "sender": "User",
      "message": "Hello",
      "timestamp": "17:00:00"
    },
    {
      "sender": "ChatBot",
      "message": "Hi, how can I help?",
      "timestamp": "17:00:01"
    }
  ]
}
```

---

## Input History

Press the **up/down arrow keys** at the `Message:` prompt to scroll through previously sent messages within the current session. History resets when the program exits.