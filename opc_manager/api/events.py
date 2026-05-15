import json
import time
import asyncio
from aiohttp import web
from opc_manager.progress_emitter import ProgressEmitter, ProgressEvent, EventType

async def sse_handler(request: web.Request) -> web.StreamResponse:
    session_id = request.query.get("session_id", "")
    if not session_id:
        return web.Response(text="session_id required", status=400)
    
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
    
    return response

def create_event_app() -> web.Application:
    app = web.Application()
    app.router.add_get('/api/events', sse_handler)
    return app
