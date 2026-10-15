import asyncio
import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_gateway import ws_gateway
from app.services.market_ingest import market_ingest

router = APIRouter(tags=["Real-time Streaming"])

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await ws_gateway.connect(websocket)
    try:
        # Send initial full quote snapshot
        initial_quotes = market_ingest.get_all_quotes()
        await websocket.send_text(json.dumps({
            "type": "INITIAL_SNAPSHOT",
            "data": [q.dict() for q in initial_quotes]
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
                # Send updated tick
                ticks = market_ingest.simulate_tick()
                # Rotate the sampled symbols each tick to mimic live exchange throughput
                symbols = list(ticks.keys())
                if symbols:
                    start = int(time.time() // 2) % len(symbols)
                    sample_syms = [symbols[(start + i) % len(symbols)] for i in range(min(6, len(symbols)))]
                else:
                    sample_syms = []
                tick_payload = {
                    "type": "TICK",
                    "data": [ticks[s].dict() for s in sample_syms]
                }
                await websocket.send_text(json.dumps(tick_payload, default=str))
    except (WebSocketDisconnect, Exception):
        ws_gateway.disconnect(websocket)
