from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager

TARGET_API = "https://open.xiaojingai.com"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a single AsyncClient instance to be reused
http_client = httpx.AsyncClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create the httpx client
    global http_client
    http_client = httpx.AsyncClient()
    yield
    # Shutdown: close the httpx client
    await http_client.aclose()

app = FastAPI(lifespan=lifespan)

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"\nRequest: {request.method} {request.url} - Response Time: {process_time:.4f}s - Status: {response.status_code}")
        return response

app.add_middleware(TimingMiddleware)

# Create a single AsyncClient instance to be reused
http_client = httpx.AsyncClient()

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def redirect_api(request: Request, path: str):
    target_url = f"{TARGET_API}/{path}"

    # Forward the request to the target API
    response = await http_client.request(
        method=request.method,
        url=target_url,
        headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
        content=await request.body(),
        cookies=request.cookies,
        follow_redirects=False,
    )

    # Create a streaming response
    async def generate():
        async for chunk in response.aiter_bytes():
            yield chunk

    # Prepare headers
    excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
    headers = {k: v for k, v in response.headers.items() if k.lower() not in excluded_headers}

    return StreamingResponse(
        generate(),
        status_code=response.status_code,
        headers=headers,
        media_type=response.headers.get("content-type")
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)
