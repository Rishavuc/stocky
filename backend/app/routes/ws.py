import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_gateway import ws_gateway, snapshot_payload, MAX_CONNECTIONS
from app.services.market_ingest import market_ingest

router = APIRouter(tags=["Real-time Streaming"])

MAX_CLIENT_MESSAGE = 4096  # PING / subscribe commands are tiny

# Sockets accepted but not yet registered (still waiting on their snapshot).
# Counted toward the cap so a burst of connections cannot overshoot it.
_pending = 0


@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    global _pending
    if len(ws_gateway.active_connections) + _pending >= MAX_CONNECTIONS:
        # 1013 = "try again later"; the client reconnects after 5s.
        await websocket.close(code=1013)
        return

    _pending += 1
    registered = False
    try:
        await websocket.accept()
        # Initial full quote snapshot first, then join the shared broadcaster
        # (so a TICK never arrives before INITIAL_SNAPSHOT). This handler only
        # reads commands after that.
        initial = await asyncio.to_thread(market_ingest.get_tick_snapshot)
        await websocket.send_text(snapshot_payload("INITIAL_SNAPSHOT", initial.values()))
        ws_gateway.register(websocket)
        _pending -= 1
        registered = True

        while True:
            data = await websocket.receive_text()
            if len(data) > MAX_CLIENT_MESSAGE:
                continue
            try:
                msg = json.loads(data)
            except ValueError:
                continue  # ignore junk instead of dropping the connection
            if isinstance(msg, dict) and msg.get("action") == "PING":
                await websocket.send_text(json.dumps({"type": "PONG"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS Client Warning]: {e}")
    finally:
        if not registered:
            _pending -= 1
        ws_gateway.disconnect(websocket)
