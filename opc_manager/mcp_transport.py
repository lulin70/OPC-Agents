"""
MCP Transport Layer — EXPERIMENTAL

This module is experimental and not yet integrated into the main application flow.
It may be removed or significantly changed in future versions.

SSE + stdio 传输层：

为MCPServer提供两种传输方式：
1. SSE (Server-Sent Events) — HTTP长连接，适合Web客户端
2. stdio — 标准输入输出，适合本地进程间通信

启动方式：
  # SSE模式
  uvicorn opc_manager.mcp_transport:create_sse_app --host 127.0.0.1 --port 8901

  # stdio模式
  python -m opc_manager.mcp_transport --transport stdio
"""

import asyncio
import hmac
import json
import logging
import os
import sys
from typing import Dict, Any, Optional

from .version import __version__

logger = logging.getLogger(__name__)

SSE_AVAILABLE = False
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    from sse_starlette.sse import EventSourceResponse

    SSE_AVAILABLE = True
except ImportError:
    pass

from .mcp_protocol import MCPServer


def create_mcp_server() -> MCPServer:
    from .task_engine_v3 import task_engine_v3
    from .skill_registry import SkillRegistry

    skill_registry = SkillRegistry()
    return MCPServer(task_engine=task_engine_v3, skill_registry=skill_registry)


if SSE_AVAILABLE:

    def create_sse_app() -> FastAPI:
        mcp_server = create_mcp_server()
        app = FastAPI(title="OPC-Agents MCP SSE Endpoint", version=__version__)

        MCP_API_KEY = os.environ.get("MCP_API_KEY", "")

        def _check_auth(request: Request):
            """Check MCP_API_KEY authentication. Returns error response or None."""
            if not MCP_API_KEY:
                from fastapi.responses import JSONResponse

                logger.error(
                    "MCP_API_KEY not configured — rejecting unauthenticated request"
                )
                return JSONResponse(
                    status_code=401,
                    content={"error": "MCP_API_KEY not configured — authentication required"},
                )
            auth = request.headers.get("Authorization", "")
            token = (
                auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
            )
            if not hmac.compare_digest(token, MCP_API_KEY):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=401, content={"error": "Unauthorized"}
                )
            return None

        @app.get("/sse")
        async def sse_endpoint(request: Request):
            auth_error = _check_auth(request)
            if auth_error:
                return auth_error

            async def event_generator():
                yield {
                    "event": "endpoint",
                    "data": json.dumps({"type": "endpoint", "url": "/messages"}),
                }
                while True:
                    if await request.is_disconnected():
                        break
                    await asyncio.sleep(30)
                    yield {"event": "ping", "data": ""}

            return EventSourceResponse(event_generator())

        @app.post("/messages")
        async def handle_message(request: Request):
            auth_error = _check_auth(request)
            if auth_error:
                return auth_error
            body = await request.json()
            result = mcp_server.handle_request(body)
            return result

        @app.get("/health")
        async def health():
            return {"status": "ok", "transport": "sse", "version": __version__}

        return app


class StdioTransport:

    def __init__(self, mcp_server: Optional[MCPServer] = None):
        self.mcp_server = mcp_server or create_mcp_server()
        self._shutdown = False

    def shutdown(self) -> None:
        self._shutdown = True

    def run(self) -> None:
        mcp_api_key = os.environ.get("MCP_API_KEY", "")
        if not mcp_api_key:
            logger.warning(
                "MCP_API_KEY is empty — stdio endpoint is open without authentication (development mode only)"
            )
        logger.info("MCP stdio transport started")
        while not self._shutdown:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                request = json.loads(line)
                response = self.mcp_server.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                logger.error("stdio transport error: %s", e)
                if not self._shutdown:
                    break
        logger.info("MCP stdio transport stopped")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="OPC-Agents MCP Transport")
    parser.add_argument("--transport", choices=["sse", "stdio"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8901)
    args = parser.parse_args()

    if args.transport == "stdio":
        transport = StdioTransport()
        transport.run()
    elif args.transport == "sse":
        if SSE_AVAILABLE:
            import uvicorn

            app = create_sse_app()
            start_sse_server(app, host=args.host, port=args.port)
        else:
            logger.warning(
                "SSE transport requires: pip install fastapi uvicorn sse-starlette"
            )
            sys.exit(1)


def start_sse_server(app, host: str = "127.0.0.1", port: int = 8901):
    """Start SSE server with security checks.

    Security rules:
    - Default binding to 127.0.0.1 (localhost only)
    - If MCP_HOST env var is set to a non-localhost address, log WARNING
    - If host is not localhost and MCP_API_KEY is not set, refuse to start
    """
    # Check MCP_HOST environment variable for non-localhost binding
    mcp_host_env = os.environ.get("MCP_HOST", "")
    if mcp_host_env and mcp_host_env not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "MCP_HOST is set to '%s' (non-localhost) — SSE endpoint will be "
            "accessible from external networks. Ensure MCP_API_KEY is configured.",
            mcp_host_env,
        )

    # Security check: refuse to start if binding to non-localhost without API key
    localhost_addresses = {"127.0.0.1", "localhost", "::1"}
    if host not in localhost_addresses and not os.environ.get("MCP_API_KEY"):
        error_msg = (
            f"SECURITY: Refusing to start SSE server on {host} without MCP_API_KEY. "
            "Binding to a non-localhost address without authentication exposes the "
            "MCP endpoint to the network. Set MCP_API_KEY environment variable or "
            "bind to 127.0.0.1 instead."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    import uvicorn

    logger.info("Starting SSE server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
