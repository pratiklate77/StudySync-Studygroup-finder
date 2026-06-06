import asyncio
import json
import logging
from uuid import UUID
from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, redis: Redis):
        self.active_connections: dict[UUID, list[WebSocket]] = {}
        self.redis = redis
        self.pubsub_task: asyncio.Task | None = None
        self.channel_name = "notification_ws_broadcast"

    async def connect(self, user_id: UUID, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(self, user_id: UUID, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_personal_message(self, user_id: UUID, message: dict):
        """Send locally if the user is on this instance, otherwise broadcast via Redis"""
        payload = json.dumps({"user_id": str(user_id), "data": message})
        await self.redis.publish(self.channel_name, payload)

    async def _push_to_local(self, user_id: UUID, data: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error sending local WS message: {e}")

    async def start_pubsub_listener(self):
        """Listener for cross-instance notification broadcasting"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.channel_name)
        
        async def listen():
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        payload = json.loads(message["data"])
                        user_id = UUID(payload["user_id"])
                        await self._push_to_local(user_id, payload["data"])
            except Exception as e:
                logger.error(f"WebSocket PubSub failure: {e}")
            finally:
                await pubsub.unsubscribe(self.channel_name)

        self.pubsub_task = asyncio.create_task(listen())

    async def stop(self):
        if self.pubsub_task:
            self.pubsub_task.cancel()