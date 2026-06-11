import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from mcp.server.fastapi import create_mcp_app
from mcp.server import Server
from mcp.types import Tool, TextContent

load_dotenv()

COOLIFY_API_URL = os.getenv("COOLIFY_API_URL", "https://deploy.quantyralabs.cc").rstrip("/")
COOLIFY_API_TOKEN = os.getenv("COOLIFY_API_TOKEN")

if not COOLIFY_API_TOKEN:
    raise RuntimeError("COOLIFY_API_TOKEN is not set")

# =====================
# Coolify API Helper
# =====================
async def coolify_request(method: str, path: str, **kwargs) -> dict:
    headers = {
        "Authorization": f"Bearer {COOLIFY_API_TOKEN}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method, f"{COOLIFY_API_URL}/api/v1{path}", headers=headers, **kwargs
        )
        response.raise_for_status()
        return response.json()


# =====================
# MCP Tools (Read-only)
# =====================
server = Server("coolify-mcp")

@server.call_tool()
async def list_applications() -> list[TextContent]:
    data = await coolify_request("GET", "/applications")
    return [TextContent(type="text", text=str(data))]

@server.call_tool()
async def get_application_details(application_id: str) -> list[TextContent]:
    data = await coolify_request("GET", f"/applications/{application_id}")
    return [TextContent(type="text", text=str(data))]

@server.call_tool()
async def get_application_logs(application_id: str, lines: int = 100) -> list[TextContent]:
    data = await coolify_request(
        "GET", 
        f"/applications/{application_id}/logs", 
        params={"lines": lines}
    )
    return [TextContent(type="text", text=str(data))]

@server.call_tool()
async def list_servers() -> list[TextContent]:
    data = await coolify_request("GET", "/servers")
    return [TextContent(type="text", text=str(data))]

@server.call_tool()
async def list_deployments(application_id: str | None = None) -> list[TextContent]:
    params = {"application_id": application_id} if application_id else {}
    data = await coolify_request("GET", "/deployments", params=params)
    return [TextContent(type="text", text=str(data))]

@server.call_tool()
async def get_environment_variables(application_id: str) -> list[TextContent]:
    data = await coolify_request("GET", f"/applications/{application_id}/envs")
    return [TextContent(type="text", text=str(data))]


# =====================
# OAuth Discovery (Required by Grok)
# =====================
app = FastAPI(title="Coolify MCP Proxy")

@app.get("/.well-known/oauth-protected-resource")
async def protected_resource():
    return {
        "resource": "https://coolify-mcp.quantyralabs.cc",
        "authorization_servers": ["https://coolify-mcp.quantyralabs.cc"],
    }

@app.get("/.well-known/oauth-authorization-server")
async def authorization_server():
    return {
        "issuer": "https://coolify-mcp.quantyralabs.cc",
        "authorization_endpoint": "https://coolify-mcp.quantyralabs.cc/oauth/authorize",
        "token_endpoint": "https://coolify-mcp.quantyralabs.cc/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp"],
    }

# Simple OAuth endpoints (personal use - can be hardened later)
@app.get("/oauth/authorize")
async def authorize(request: Request):
    # For personal use - auto approve
    return {"message": "Authorization granted. Use the token endpoint."}

@app.post("/oauth/token")
async def token(request: Request):
    # Return a simple token for now (you can improve this)
    return {
        "access_token": "coolify-mcp-personal-token",
        "token_type": "Bearer",
        "expires_in": 86400,
    }


# Mount MCP server
mcp_app = create_mcp_app(server)
app.mount("/mcp", mcp_app)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "coolify-mcp-proxy"}