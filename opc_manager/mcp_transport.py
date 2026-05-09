"""
MCP Transport — SSE + stdio 传输层

为MCPServer提供两种传输方式：
1. SSE (Server-Sent Events) — HTTP长连接，适合Web客户端
2. stdio — 标准输入输出，适合本地进程间通信

启动方式：
  # SSE模式
  uvicorn opc_manager.mcp_transport:create_sse_app --host 0.0.0.0 --port 8901
  
  # stdio模式
  python -m opc_manager.mcp_transport --transport stdio
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, Optional

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
    from .task_engine_adapter import TaskEngineAdapter
    from .task_engine_v3 import task_engine_v3
    adapter = TaskEngineAdapter(task_engine=task_engine_v3)
    return MCPServer(task_engine_adapter=adapter)


if SSE_AVAILABLE:
    def create_sse_app() -> FastAPI:
        mcp_server = create_mcp_server()
        app = FastAPI(title="OPC-Agents MCP SSE Endpoint", version="0.1.9-delta")

        @app.get("/sse")
        async def sse_endpoint(request: Request):
            async def event_generator():
                yield {"event": "endpoint", "data": json.dumps({"type": "endpoint", "url": "/messages"})}
                while True:
                    if await request.is_disconnected():
                        break
                    await asyncio.sleep(30)
                    yield {"event": "ping", "data": ""}

            return EventSourceResponse(event_generator())

        @app.post("/messages")
        async def handle_message(request: Request):
            body = await request.json()
            result = mcp_server.handle_request(body)
            return result

        @app.get("/health")
        async def health():
            return {"status": "ok", "transport": "sse", "version": "0.1.9-delta"}

        return app


class StdioTransport:

    def __init__(self, mcp_server: Optional[MCPServer] = None):
        self.mcp_server = mcp_server or create_mcp_server()

    def run(self) -> None:
        logger.info("MCP stdio transport started")
        while True:
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
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"}
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                logger.error(f"stdio transport error: {e}")
                break
        logger.info("MCP stdio transport stopped")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OPC-Agents MCP Transport")
    parser.add_argument("--transport", choices=["sse", "stdio"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8901)
    args = parser.parse_args()

    if args.transport == "stdio":
        transport = StdioTransport()
        transport.run()
    elif args.transport == "sse":
        if SSE_AVAILABLE:
            import uvicorn
            app = create_sse_app()
            uvicorn.run(app, host=args.host, port=args.port)
        else:
            print("SSE transport requires: pip install fastapi uvicorn sse-starlette")
            sys.exit(1)


if __name__ == "__main__":
    main()
