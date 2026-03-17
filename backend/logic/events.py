from typing import List, Dict, Any
from fastapi import WebSocket
import asyncio
import json

class ConnectionManager:
    def __init__(self):
        # active_connections tracks all currently connected WebSockets
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcasts a message to all connected clients.
        Message should be a serializable dictionary.
        """
        if not self.active_connections:
            return

        message_str = json.dumps(message)
        
        # We use asyncio.gather to broadcast simultaneously
        # Note: In a production 1000+ user scenario, this should be handled by a queue,
        # but for an indie game with <100 concurrent users, this in-memory set is optimal for 1GB RAM.
        tasks = []
        for connection in list(self.active_connections):
            tasks.append(self.send_personal_message(message_str, connection))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception:
            # If sending fails, the client probably disconnected
            self.disconnect(websocket)

# Global manager instance
event_manager = ConnectionManager()
