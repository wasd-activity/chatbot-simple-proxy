import os
import uvicorn
import sys
import dotenv
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# config
dotenv.load_dotenv()
PROXY_API_KEY = os.getenv("PROXY_API_KEY")
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY")
UPSTREAM_CHAT_COMPLETIONS_URL = "https://api.poe.com/v1/chat/completions"
PORT = int(os.getenv("PORT", "3002"))

if not PROXY_API_KEY:
    print("Error: PROXY_API_KEY not found in environment variables.", file=sys.stderr)
    sys.exit(1)

if not UPSTREAM_API_KEY:
    print("Error: UPSTREAM_API_KEY not found in environment variables.", file=sys.stderr)
    sys.exit(1)

# over all Client
http_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create client
    global http_client
    http_client = httpx.AsyncClient(timeout=60.0)  # set reasonable timeout
    yield
    await http_client.aclose()

app = FastAPI(lifespan=lifespan)
security = HTTPBearer()  # 用于处理 Bearer Token

FIXED_PAYLOAD_BASE = {
    "model": "Gemini-3-Pro",
    "temperature": 1,
    "extra_body": {
        "thinking_level": "high",
    },
    "stream": True,
}


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not PROXY_API_KEY:
        return False
    if credentials.credentials != PROXY_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@app.post("/v1/chat/completions")
async def ai_proxy(request: Request, token: str = Depends(verify_token)):
    try:
        body = await request.json()
        print("JSON Payload:")
        print(json.dumps(body, indent=4, ensure_ascii=False))
    except json.JSONDecodeError:
        print("Body is not valid JSON format")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format"
        )
    except Exception as e:
        print(f"Error when read Body: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_NOT_IMPLEMENTED,
            detail=f"Server error: {str(e)}"
        )

    # get payload
    user_messages = extract_messages(body)
    upstream_payload = build_fixed_payload(user_messages)

    # stream response
    return StreamingResponse(
        stream_upstream(upstream_payload),
        media_type="text/event-stream",
    )


def extract_messages(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_GATEWAY, detail="'messages' must be a list")
    return messages


def build_fixed_payload(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    # get new dict
    return {
        **FIXED_PAYLOAD_BASE,
        "messages": messages,
        # independent copy
        "extra_body": FIXED_PAYLOAD_BASE["extra_body"].copy()
    }


async def stream_upstream(payload: Dict[str, Any]) -> AsyncGenerator[bytes, None]:
    headers = {
        "Authorization": f"Bearer {UPSTREAM_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    if http_client is None:
        raise HTTPException(status_code=status.HTTP_500_BAD_GATEWAY, detail="Error Internal")

    try:
        # use global client
        async with http_client.stream(
            "POST",
            UPSTREAM_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                error_content = await response.aread()
                print(f"Upstream Error {response.status_code}: {error_content}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Upstream error: {error_content.decode('utf-8', errors='ignore')}"
                )

            async for chunk in response.aiter_bytes():
                try:
                    # print
                    print(chunk.decode("utf-8", errors="replace"), end="", flush=True)
                except Exception as e:
                    print(f"[Log Error: {e}]", end="")
                print("\n--- Current Stream Finished ---\n")
                yield chunk

    except httpx.RequestError as exc:
        print(f"Connection error: {exc}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Error connecting to upstream API")

if __name__ == "__main__":
    # use uvicorn start service
    print(f"FastAPI Server Start: http://localhost:{PORT}/v1/chat/completions")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
