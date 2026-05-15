import json
import time
import asyncio
from aiohttp import web
from opc_manager.progress_emitter import ProgressEmitter, ProgressEvent, EventType

MAX_SSE_CONNECTIONS = 100
_active_sse_connections = 0
_connection_lock = asyncio.Lock()

def _validate_session_id(session_id: str) -> bool:
    if not session_id or not isinstance(session_id, str):
        return False
    if len(session_id) < 32 or len(session_id) > 128:
        return False
    return True

async def sse_handler(request: web.Request) -> web.StreamResponse:
    global _active_sse_connections
    session_id = request.query.get("session_id", "")
    
    if not _validate_session_id(session_id):
        return web.Response(text="Invalid session_id format", status=400)
    
    async with _connection_lock:
        if _active_sse_connections >= MAX_SSE_CONNECTIONS:
            return web.Response(text="Too many SSE connections", status=503)
        _active_sse_connections += 1
    
    try:
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )
    await response.prepare(request)
    
    emitter = ProgressEmitter()
    queue = asyncio.Queue()
    
    def on_event(sse_data: str):
        try:
            queue.put_nowait(sse_data)
        except asyncio.QueueFull:
            pass
    
    emitter.subscribe(session_id, on_event)
    
    try:
        initial_events = emitter.get_history(session_id)
        for ev in initial_events:
            await response.write(ev.get("sse_data", json.dumps(ev) + "\n\n").encode())
        
        heartbeat_interval = 15
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                await response.write(data.encode() if isinstance(data, str) else data)
            except asyncio.TimeoutError:
                await response.write(f": heartbeat\n\n".encode())
    except ConnectionResetError:
        pass
    finally:
        emitter.unsubscribe(session_id)
        async with _connection_lock:
            _active_sse_connections -= 1
    
    return response

def create_event_app() -> web.Application:
    app = web.Application()
    app.router.add_get('/api/events', sse_handler)
    return app
