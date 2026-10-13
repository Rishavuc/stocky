import asyncio
import json
from typing import Set
from fastapi import WebSocket
from app.services.market_ingest import market_ingest

class WebSocketGateway:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast_tick(self, data: dict):
        if not self.active_connections:
            return
        payload = json.dumps(data)
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                disconnected.append(conn)
        for dead in disconnected:
            self.disconnect(dead)

ws_gateway = WebSocketGateway()
