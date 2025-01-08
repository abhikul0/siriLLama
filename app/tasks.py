import asyncio
import aiohttp
import logging
from app.ollama_client import OllamaClient
from app.functions_endpoint import scrape_clean_text, search_xng

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG to capture all levels of logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.ollama_client = OllamaClient()
        logging.debug("TaskManager initialized")

    def add_task(self, task_id, task_type, data):
        self.tasks[task_id] = {"type": task_type, "data": data, "status": "scheduled", "result": None}
        asyncio.create_task(self.execute_task(task_id))
        logging.debug(f"Task {task_id} added with type {task_type}")

    async def execute_task(self, task_id):
        task = self.tasks[task_id]
        task["status"] = "running"
        logging.debug(f"Task {task_id} started")
        try:
            async with aiohttp.ClientSession() as session:
                if task["type"] == "summarize_url":
                    scraped_data = await scrape_clean_text(task["data"]["url"], session=session)
                    if scraped_data:
                        cleaned_html = scraped_data["cleaned_html"]
                        original_message = task["data"]["messages"][0]
                        original_message["content"] = original_message["content"] + "\n" + cleaned_html
                        request_data = {
                            "model": task["data"]["model"],
                            "messages": [original_message],
                            "stream": task["data"]["stream"]
                        }
                        if "options" in task["data"]:
                            request_data["options"] = task["data"]["options"]
                        if "images" in task["data"]:
                            request_data["images"] = task["data"]["images"]
                        result = await self.ollama_client.generate_chat(request_data)
                        task["status"] = "done"
                        task["result"] = result
                        logging.debug(f"Task {task_id} completed successfully with result: {result}")
                    else:
                        task["status"] = "failed"
                        task["result"] = {"error": "Failed to scrape URL"}
                        logging.error(f"Task {task_id} failed with error: Failed to scrape URL")

                elif task["type"] == "search_web":
                    search_result = await search_xng(task["data"]["searchQ"], session=session)
                    if search_result:
                        request_data = {
                            "model": task["data"]["model"],
                            "messages": [{"role":"user","content":search_result}],
                            "stream": task["data"]["stream"],
                            "options": {"num_ctx":8192}
                        }
                        result = await self.ollama_client.generate_chat(request_data)
                        task["status"] = "done"
                        task["result"] = result
                        logging.debug(f"Task {task_id} completed successfully with result: {result}")

                elif task["type"] == "embed":
                    result = await self.ollama_client.generate_embeddings(task["data"])
                else:
                    result = {"error": "Unknown task type"}
                task["status"] = "done"
                task["result"] = result
                logging.info(f"Task {task_id} completed successfully with result: {result}")
        except Exception as e:
            task["status"] = "failed"
            task["result"] = {"error": str(e)}
            logging.error(f"Task {task_id} failed with error: {e}")

    def get_task_status(self, task_id):
        if task_id in self.tasks:
            logging.debug(f"Task {task_id} status requested: {self.tasks[task_id]['status']}")
            return self.tasks[task_id]
        else:
            logging.warning(f"Task {task_id} not found")
            return {"error": "Task not found"}