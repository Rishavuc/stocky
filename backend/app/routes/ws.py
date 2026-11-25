import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_gateway import ws_gateway
from app.services.market_ingest import market_ingest

router = APIRouter(tags=["Real-time Streaming"])

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await ws_gateway.connect(websocket)
    try:
        # Send initial full quote snapshot
        initial_quotes = (await asyncio.to_thread(market_ingest.get_tick_snapshot)).values()
        await websocket.send_text(json.dumps({
            "type": "INITIAL_SNAPSHOT",
            "data": [q.model_dump() for q in initial_quotes]
        }, default=str))

        while True:
            # Listen for client messages (e.g. subscribe / unsubscribe) with short timeout
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.5)
                # Client commands if sent
                msg = json.loads(data)
                if msg.get("action") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG"}))
            except asyncio.TimeoutError:
                # Send the authoritative provider snapshot. No simulated drift.
                ticks = await asyncio.to_thread(market_ingest.get_tick_snapshot)
                tick_payload = {
                    "type": "TICK",
                    "data": [q.model_dump() for q in ticks.values()]
                }
                await websocket.send_text(json.dumps(tick_payload, default=str))
    except (WebSocketDisconnect, Exception):
        ws_gateway.disconnect(websocket)
