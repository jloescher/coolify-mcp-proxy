import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route

load_dotenv()

COOLIFY_API_URL = os.getenv("COOLIFY_API_URL", "https://deploy.quantyralabs.cc").rstrip("/")
COOLIFY_API_TOKEN = os.getenv("COOLIFY_API_TOKEN")

if not COOLIFY_API_TOKEN:
    raise RuntimeError("COOLIFY_API_TOKEN is missing")

# =====================
# Coolify API Helper
# =====================
async def coolify_get(path: str, params: dict = None):
    headers = {
        "Authorization": f"Bearer {COOLIFY_API_TOKEN}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{COOLIFY_API_URL}/api/v1{path}", headers=headers, params=params)
        r.raise_for_status()
        return r.json()


# =====================
# MCP Server + Tools
# =====================
server = Server("coolify-mcp")

@server.call_tool()
async def list_applications():
    data = await coolify_get("/applications")
    return [{"type": "text", "text": str(data)}]

@server.call_tool()
async def get_application_details(application_id: str):
    data = await coolify_get(f"/applications/{application_id}")
    return [{"type": "text", "text": str(data)}]

@server.call_tool()
async def get_application_logs(application_id: str, lines: int = 100):
    data = await coolify_get(f"/applications/{application_id}/logs", {"lines": lines})
    return [{"type": "text", "text": str(data)}]

@server.call_tool()
async def list_servers():
    data = await coolify_get("/servers")
    return [{"type": "text", "text": str(data)}]


# =====================
# FastAPI + MCP Setup
# =====================
app = FastAPI(title="Coolify MCP Proxy")

# Health endpoint (for Coolify)
@app.get("/health")
async def health():
    return {"status": "ok"}

# Mount MCP over SSE
sse = SseServerTransport("/messages/")
app.router.routes.append(Mount("/mcp", app=Starlette(routes=[Mount("/sse", app=sse.handle_request)])))

# OAuth discovery endpoints (needed by Grok)
@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected():
    return {
        "resource": "https://coolify-mcp.quantyralabs.cc",
        "authorization_servers": ["https://coolify-mcp.quantyralabs.cc"],
    }

@app.get("/.well-known/oauth-authorization-server")
async def oauth_server():
    return {
        "issuer": "https://coolify-mcp.quantyralabs.cc",
        "authorization_endpoint": "https://coolify-mcp.quantyralabs.cc/oauth/authorize",
        "token_endpoint": "https://coolify-mcp.quantyralabs.cc/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
    }