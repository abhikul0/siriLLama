# siriLLama

## Project Structure
```
siriLLama/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── ollama_client.py
│   ├── database.py
│   └── tasks.py
│   └── functions_endpoint.py
├── README.md
└── requirements.txt
```

## Features

- Implements functionality to interact with the Ollama API endpoints (`/api/tags`, `/api/chat`, `/api/embed`).
- Scalable and modular backend with separate functions for Ollama interaction and main app.
- Robust with a simple database to store chat history.
- Includes a `siri` endpoint to interact with Siri shortcuts on iOS devices.
- Includes a `functions` endpoint for handling custom functions.
- Logging for debugging and monitoring.

## Usage Instructions

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the backend:**
   ```bash
   uvicorn --host 0.0.0.0 app.main:app --reload
   ```
   **OR**
   use the run.cmd/run.sh

## Siri Shortcut
   https://www.icloud.com/shortcuts/dc4fc0a6edbd4813af5ad456e3eb9623
## Endpoints:
   - /api/tags: List models available locally.
   - /api/chat: Generate a chat completion.
   - /api/embed: Generate embeddings from a model.
   - /siri: Interact with Siri shortcuts.
   - /siri/status/{task_id}: Check status of a scheduled task.
   - /functions: Handle custom functions.

## Logging
   Logging is configured to provide detailed information about the operations performed by the backend. Logs are output to the console and include timestamps, log levels, and messages. This helps in debugging and monitoring the backend operations.

   **Log Levels**
   - DEBUG: Captures detailed information, typically of interest only when diagnosing problems.
   - INFO: Confirms that things are working as expected.
   - WARNING: An indication that something unexpected happened, or indicative of some problem in the near future (e.g., ‘disk space low’). The software is still working as expected.
   - ERROR: Due to a more serious problem, the software has not been able to perform some function.
   - CRITICAL: A very serious error, indicating that the program itself may be unable to continue running.
