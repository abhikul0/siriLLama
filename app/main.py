from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from app.ollama_client import OllamaClient
from app.database import SessionLocal, ChatHistory
from app.tasks import TaskManager
from app.functions_endpoint import scrape_clean_text
from app.functions_endpoint import functions_router  # Import the functions router
from sqlalchemy.orm import Session
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChatRequest(BaseModel):
    model: str
    messages: list
    stream: bool = False

class EmbedRequest(BaseModel):
    model: str
    input: list
    truncate: bool = True

class SiriRequest(BaseModel):
    type: str
    model: str
    messages: list
    stream: bool = False
    url: str = None
    options: dict = None
    images: list = None
    searchQ: str

app = FastAPI()
ollama_client = OllamaClient()
task_manager = TaskManager()

# Include the functions router
app.include_router(functions_router, prefix="/functions", tags=["functions"])

@app.get("/")
async def read_root():
    logging.debug("Root endpoint accessed")
    return {"message": "Ollama Backend is running"}

@app.get("/api/tags")
async def list_models():
    logging.debug("List models endpoint accessed")
    return await ollama_client.list_models()

@app.post("/api/chat")
async def generate_chat(request: ChatRequest):
    db = SessionLocal()
    try:
        session_id = str(uuid.uuid4())
        chat_history = ChatHistory(session_id=session_id, messages=request.messages)
        db.add(chat_history)
        db.commit()
        logging.debug(f"Chat request received with session_id {session_id}")
        response = await ollama_client.generate_chat(request.dict())
        chat_history.messages.append(response)
        db.commit()
        logging.debug(f"Chat response generated for session_id {session_id}: {response}")
        return response
    except Exception as e:
        logging.error(f"Error processing chat request: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/embed")
async def generate_embeddings(request: EmbedRequest):
    logging.debug("Embedding request received")
    response = await ollama_client.generate_embeddings(request.dict())
    logging.debug("Embedding response generated")
    return response

@app.post("/siri")
async def siri_post(request: SiriRequest):
    task_id = str(uuid.uuid4())
    task_data = {
        "model": request.model,
        "messages": request.messages,
        "stream": request.stream,
    }
    if request.type == "summarize_url":
        task_data["url"] = request.url
    if request.type == "search_web":
        task_data["searchQ"] = request.searchQ
    if request.options:
        task_data["options"] = request.options
    if request.images:
        task_data["images"] = request.images
    task_manager.add_task(task_id, request.type, task_data)
    logging.debug(f"Siri task {task_id} added with type {request.type}")
    return {
        "received": True,
        "url": f"http://localhost:8000/siri/status/{task_id}",
        "task_id": task_id,
        "status": "scheduled"
    }

@app.get("/siri/status/{task_id}")
async def siri_status(task_id: str):
    status = task_manager.get_task_status(task_id)
    logging.debug(f"Siri status checked for task_id {task_id}: {status['status']}")
    return status

@app.post("/functions")
async def functions(request: dict):
    # Basic structure to handle custom functions
    logging.debug("Functions endpoint accessed")
    return {"status": "received", "data": request}

if __name__ == "__main__": 
    uvicorn.run(app, host="0.0.0.0", port=8000)