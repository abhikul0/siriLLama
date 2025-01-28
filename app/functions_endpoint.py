import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import random
import logging
from pydantic import BaseModel
from fastapi import APIRouter, Request, HTTPException
import trafilatura
from aiohttp.client_exceptions import ClientError
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEARXNG_URL = "http://localhost:4000/search"  # Adjust this URL to your SearXng instance
LLM_ENDPOINT = "http://localhost:11434"  # Adjust this URL to your LLM endpoint

# Define a Pydantic model for input JSON
class ScrapeRequest(BaseModel):
    url: str

class SearchQuery(BaseModel):
    search_query: str

functions_router = APIRouter()

async def search_with_searxng(query, session):
    params = {
        'q': query,
        'categories_general': 'general',
        'language': 'en',
        'format': 'json'
    }
    async with session.get(SEARXNG_URL, params=params) as response:
        if response.status == 200:
            return await response.json()
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch results from SearXng")

async def fetch_url_with_timeout(url, timeout=4):
    loop = asyncio.get_running_loop()
    try:
        downloaded = await loop.run_in_executor(ThreadPoolExecutor(), trafilatura.fetch_url, url)
        return downloaded
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None

async def scrape_trafilatura(url, max_tokens=1024, max_retries=3, retry_delay=2, session=None):
    """
    Scrapes the content from a URL using trafilatura and handles errors and anti-scraping measures.
    If trafilatura fails, it falls back to BeautifulSoup for content extraction.

    :param url: The URL to scrape.
    :param max_tokens: The maximum number of tokens to return.
    :param max_retries: The maximum number of retries in case of a request failure.
    :param retry_delay: The delay between retries in seconds.
    :param session: An aiohttp session to reuse.
    :return: A string containing the truncated text.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            # Fetch the URL with a timeout
            downloaded = await asyncio.wait_for(fetch_url_with_timeout(url), timeout=4)
            if downloaded is None:
                raise Exception("Timeout occurred while fetching the URL using trafilatura.")
            
            # Extract the content
            result = trafilatura.extract(downloaded)
            
            if not result:
                raise ValueError("No content found at the URL using trafilatura.")
            
            # Tokenize the extracted content using basic string operations
            tokens = result.split()
            
            # Truncate the tokens to the specified number
            truncated_tokens = tokens[:max_tokens]
            
            # Convert tokens back to string
            truncated_text = ' '.join(truncated_tokens)
            
            return truncated_text
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout occurred while fetching URL {url}. Moving to the next URL...")
            break  # Move to the next URL
        
        except ClientError as e:
            logger.error(f"Request failed: {e}. Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
        
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}. Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
        
        attempt += 1
        # Introduce a random delay between 0 and 2 seconds to mimic human behavior
        await asyncio.sleep(random.uniform(0, 2))
    
    raise Exception("Failed to retrieve data after several attempts.")

async def search_xng(query, session):
    try:
        searxng_results = await search_with_searxng(query, session)
        results = []
        
        for idx, item in enumerate(searxng_results['results'][:3]):
            url = item['url']
            try:
                content = await scrape_trafilatura(url, session=session)
            except Exception as e:
                logger.error(f"Failed to scrape URL {url}: {e}. Skipping to the next URL...")
                continue
            results.append({
                "number": idx + 1,
                "title": item['title'],
                "url": url,
                "content": content
            })
        
        # datetime object containing current date and time
        now = datetime.now()
        # dd/mm/YY H:M:S
        dateTime = now.strftime("%d/%m/%Y %H:%M:%S")
        
        # Prepare the prompt for the LLM
        prompt = f"""You are a web research assistant. Answer the following question based on the provided sources denoted by <id[number]>. Always cite your sources with the <id[number]> AND <url> used from the sources. If the Question is answerable in a short sentence, do that.
        If you have knowledge to supplement the answer, do it but don't do it if that knowledge is not current. Keep in mind that the current date and time is {dateTime}.\n\nQuestion: {query}\n\nSources:\n"""
        for result in results:
            prompt += f"id:[{result['number']}.] - url:{result['url']}\ncontent:{result['content']}\n\n"

        return prompt
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def random_user_agent():
    """Generate a random user agent string."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/91.0.4472.77 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Mobile Safari/537.36",
        # Add more user agents as needed
    ]
    return random.choice(user_agents)

async def scrape_clean_text(url, max_retries=3, delay=5, timeout=10, session=None):
    """
    Scrapes the provided URL for clean textual content and favicon, handling errors gracefully and retrying on failures.

    Parameters:
    url (str): The URL of the webpage to scrape.
    max_retries (int): Maximum number of retries. Default is 3.
    delay (float): Delay between retries in seconds. Default is 5 seconds.
    timeout (float): Timeout for the request in seconds. Default is 10 seconds.
    session (aiohttp.ClientSession): An aiohttp session to reuse.

    Returns:
    dict: A dictionary containing 'url', 'cleaned_html', and optionally 'favicon'.
    """
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    headers = {
        'User-Agent': random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',  # Optional to mimic a persistent connection
    }

    for attempt in range(max_retries + 1):
        try:
            if session:
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    response.raise_for_status()  # Raise an exception for HTTP errors
                    html = await response.text()
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=timeout) as response:
                        response.raise_for_status()  # Raise an exception for HTTP errors
                        html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')

            # Remove script tags and comments
            for unwanted_elements in soup(["script", "style"]):
                unwanted_elements.decompose()  # Remove scripts and styles etc

            cleaned_html = soup.get_text(separator='\n', strip=True)

            # Attempt to fetch favicon from meta tags
            favicon_link = None
            for link in soup.find_all('link', rel=lambda x: x and ('favicon' in x.lower() or 'shortcut icon' in x.lower())):
                href = link.get('href')
                if href:
                    favicon_link = urljoin(base_url, href)
                    break

            # If favicon not found in meta tags, try a common favicon path
            if not favicon_link:
                favicon_link = urljoin(base_url, '/favicon.ico')

            result = {
                "url": url,
                "cleaned_html": cleaned_html,
                "favicon": favicon_link
            }
            return result

        except ClientError as e:
            logger.error(f"HTTP error occurred while scraping {url}: {e}")
            raise HTTPException(status_code=e.status, detail=str(e))
        except Exception as e:
            logger.error(f"An error occurred while scraping {url}: {e}")
            if attempt < max_retries:
                delay_time = random.uniform(0.5, delay)  # Random delay between retries
                logger.info(f"Retrying in {delay_time:.2f} seconds...")
                await asyncio.sleep(delay_time)
            else:
                raise HTTPException(status_code=500, detail=str(e))
    return None

@functions_router.post('/scrape')
async def scrape_endpoint(request: ScrapeRequest):
    """
    Handle POST requests to scrape URLs and return scraped data.
    """
    try:
        async with aiohttp.ClientSession() as session:
            scraped_data = await scrape_clean_text(request.url, session=session)
        return scraped_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 

@functions_router.post('/searx')
async def searx_endpoint(input: SearchQuery):
    try:
        query = input.search_query
        async with aiohttp.ClientSession() as session:
            searxng_results = await search_with_searxng(query, session)
            results = []
            
            for idx, item in enumerate(searxng_results['results'][:3]):
                url = item['url']
                try:
                    content = await scrape_trafilatura(url, session=session)
                except Exception as e:
                    logger.error(f"Failed to scrape URL {url}: {e}. Skipping to the next URL...")
                    continue
                results.append({
                    "number": idx + 1,
                    "title": item['title'],
                    "url": url,
                    "content": content
                })
            
            # Prepare the prompt for the LLM
            prompt = f"""You are a web research assistant. Answer the following question based on the provided sources denoted by <id[number]>. Always cite your sources based on the provided id.\n\nQuestion: {query}\n\nSources:\n"""
            for result in results:
                prompt += f"id:[{result['number']}.]\ncontent:{result['content']}\n\n"
                logger.debug("PROMPT SENT:", prompt)
            
            # Send the prompt to the LLM
            llm_response = await session.post(LLM_ENDPOINT, json={"model":"gemma2:2b-instruct-q6_K","prompt": prompt,"stream":False,"options":{"num_ctx":8192}})
            if llm_response.status == 200:
                answer = await llm_response.json()
                answer = answer.get("response", "No answer generated.")
            else:
                answer = "Failed to generate an answer from the LLM."
            
            return {
                "question": query,
                "sources": results,
                "answer": answer
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@functions_router.get("/")
async def function_get():
    return {"message": "Function endpoint not yet implemented"}