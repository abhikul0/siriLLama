import aiohttp
import asyncio

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    async def list_models(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/api/tags") as response:
                return await response.json()

    async def generate_chat(self, payload):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/api/chat", json=payload) as response:
                return await response.json()

    async def generate_embeddings(self, payload):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/api/embed", json=payload) as response:
                return await response.json()