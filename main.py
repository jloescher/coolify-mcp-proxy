import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
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
# MCP Server Definition
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
# FastAPI + MCP (Correct SSE mounting)
# =====================
app = FastAPI(title="Coolify MCP Proxy")


@app.get("/health")
async def health():
    return {"status": "ok"}


# Proper SSE setup for MCP
sse = SseServerTransport("/mcp/messages/")


async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )


# Mount MCP routes
app.router.routes.append(Route("/mcp/sse", endpoint=handle_sse))
app.router.routes.append(Mount("/mcp/messages/", app=sse.handle_post_message))