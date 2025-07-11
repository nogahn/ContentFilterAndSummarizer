import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()
        logger.info("WebSocketManager initialized.")

    async def connect(self, websocket: WebSocket, request_id: str):
        await websocket.accept()
        async with self.lock:
            self.active_connections.setdefault(request_id, set()).add(websocket)
        logger.info(f"WebSocket connected for request_id: {request_id}. Total connections for {request_id}: {len(self.active_connections[request_id])}")

    async def disconnect(self, websocket: WebSocket, request_id: str):
        async with self.lock:
            if request_id in self.active_connections:
                self.active_connections[request_id].discard(websocket)
                if not self.active_connections[request_id]:
                    del self.active_connections[request_id]
        logger.info(f"WebSocket disconnected for request_id: {request_id}. Remaining connections for {request_id}: {len(self.active_connections.get(request_id, []))}")


    async def send_to_request(self, request_id: str, message: dict):
        async with self.lock:
            connections_to_send = self.active_connections.get(request_id, set()).copy()
        
        if not connections_to_send:
            logger.debug(f"No active WebSocket connections for request_id: {request_id}. Message not sent.")
            return
        
        connections_to_remove = []
        for connection in connections_to_send:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket for request_id {request_id}: {e}. Marking connection for removal.")
                connections_to_remove.append(connection)  
        
        if connections_to_remove:
            async with self.lock:
                if request_id in self.active_connections:
                    for connection in connections_to_remove:
                        self.active_connections[request_id].discard(connection)
                    if not self.active_connections[request_id]:
                        del self.active_connections[request_id]
            logger.info(f"Removed {len(connections_to_remove)} unresponsive connections for request_id: {request_id}.")