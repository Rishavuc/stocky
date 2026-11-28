"""Single shared broadcaster for the market tick stream.

Previously every websocket client ran its own loop that called
``get_tick_snapshot`` in a worker thread every 1.5s. With a handful of tabs
open that filled the small default thread pool on a 1-CPU instance, and a slow
provider stalled every client. Now one background task builds the snapshot,
serialises it once and fans it out; per-client handlers only read messages.
"""

import asyncio
import json
import time
from typing import Optional, Set

from fastapi import WebSocket

from app.services.market_ingest import market_ingest

TICK_INTERVAL = 2.0          # seconds between snapshot checks
KEEPALIVE_INTERVAL = 15.0    # resend an unchanged snapshot this often
SEND_TIMEOUT = 5.0           # a client that cannot take a frame in 5s is dropped
MAX_CONNECTIONS = 200        # protect the 512 MB instance


def snapshot_payload(msg_type: str, quotes) -> str:
    return json.dumps(
        {"type": msg_type, "data": [q.model_dump() for q in quotes]},
        default=str,
    )


class WebSocketGateway:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._broadcaster: Optional[asyncio.Task] = None

    @property
    def is_full(self) -> bool:
        return len(self.active_connections) >= MAX_CONNECTIONS

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.register(websocket)

    def register(self, websocket: WebSocket) -> None:
        """Start receiving TICK broadcasts (call after the initial snapshot)."""
        self.active_connections.add(websocket)
        self._ensure_broadcaster()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    def _ensure_broadcaster(self) -> None:
        if self._broadcaster is None or self._broadcaster.done():
            self._broadcaster = asyncio.create_task(self._broadcast_loop())

    async def _send(self, conn: WebSocket, payload: str) -> bool:
        try:
            await asyncio.wait_for(conn.send_text(payload), timeout=SEND_TIMEOUT)
            return True
        except Exception:
            return False

    async def broadcast_text(self, payload: str) -> None:
        # Copy first: connects/disconnects during the awaits below would
        # otherwise raise "Set changed size during iteration".
        conns = list(self.active_connections)
        if not conns:
            return
        results = await asyncio.gather(*(self._send(c, payload) for c in conns))
        for conn, ok in zip(conns, results):
            if not ok:
                self.disconnect(conn)
                try:
                    await conn.close()
                except Exception:
                    pass

    async def broadcast_tick(self, data: dict):
        await self.broadcast_text(json.dumps(data, default=str))

    async def _broadcast_loop(self) -> None:
        last_payload = None
        last_sent = 0.0
        try:
            while self.active_connections:
                try:
                    ticks = await asyncio.to_thread(market_ingest.get_tick_snapshot)
                    payload = snapshot_payload("TICK", ticks.values())
                    now = time.monotonic()
                    if payload != last_payload or (now - last_sent) >= KEEPALIVE_INTERVAL:
                        await self.broadcast_text(payload)
                        last_payload, last_sent = payload, now
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # A provider or serialisation error must not kill the stream.
                    print(f"[WS Broadcast Warning]: {e}")
                await asyncio.sleep(TICK_INTERVAL)
        finally:
            self._broadcaster = None

    async def shutdown(self) -> None:
        task = self._broadcaster
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        for conn in list(self.active_connections):
            try:
                await conn.close()
            except Exception:
                pass
        self.active_connections.clear()


ws_gateway = WebSocketGateway()
