import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_gateway import ws_gateway, snapshot_payload
from app.services.market_ingest import market_ingest

router = APIRouter(tags=["Real-time Streaming"])

MAX_CLIENT_MESSAGE = 4096  # PING / subscribe commands are tiny


@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    if ws_gateway.is_full:
        # 1013 = "try again later"; the client reconnects after 5s.
        await websocket.close(code=1013)
        return

    await websocket.accept()
    try:
        # Initial full quote snapshot first, then join the shared broadcaster
        # (so a TICK never arrives before INITIAL_SNAPSHOT). This handler only
        # reads commands after that.
        initial = await asyncio.to_thread(market_ingest.get_tick_snapshot)
        await websocket.send_text(snapshot_payload("INITIAL_SNAPSHOT", initial.values()))
        ws_gateway.register(websocket)

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
        ws_gateway.disconnect(websocket)
