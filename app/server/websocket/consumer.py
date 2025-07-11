import asyncio
import json
import logging
from typing import TYPE_CHECKING
from aio_pika import IncomingMessage
from app.common.queue_utils import AsyncQueueManager, StatusUpdateMessage
from app.common.config import QUEUE_STATUS_UPDATES

if TYPE_CHECKING:
    from app.server.websocket.manager import WebSocketManager

logger = logging.getLogger(__name__)

class WebSocketConsumer:
    def __init__(self, websocket_manager: "WebSocketManager"):
        self.websocket_manager = websocket_manager
        self.queue_manager = AsyncQueueManager()
        self.consumer_task = None
        self._running = False

    async def start(self):
        """Start consuming messages from the status updates queue"""
        if self._running:
            logger.warning("WebSocketConsumer is already running")
            return
        
        self._running = True
        await self.queue_manager.init()
        
        self.consumer_task = asyncio.create_task(self._consume_status_updates())
        logger.info("WebSocketConsumer started")

    async def stop(self):
        """Stop the consumer"""
        self._running = False
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
        
        await self.queue_manager.close()
        logger.info("WebSocketConsumer stopped")

    async def _consume_status_updates(self):
        """Consume status update messages and send them via WebSocket"""
        try:
            await self.queue_manager.consume(
                QUEUE_STATUS_UPDATES,
                self._handle_status_update
            )
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Status updates consumer cancelled")
        except Exception as e:
            logger.error(f"Error in status updates consumer: {e}")

    async def _handle_status_update(self, message: IncomingMessage):
        """Handle incoming status update messages"""
        try:
            message_data = json.loads(message.body.decode())
            status_update = StatusUpdateMessage(**message_data)
            websocket_message = {
                "type": "status_update",
                "request_id": status_update.request_id,
                "url": status_update.url,
                "status": status_update.status,
                "detail": status_update.detail,
                "timestamp": status_update.timestamp,
                "result": status_update.result.model_dump() if status_update.result else None
            }
            await self.websocket_manager.send_to_request(
                status_update.request_id,
                websocket_message
            )   
            logger.info(f"Sent status update for request_id: {status_update.request_id}, status: {status_update.status}")
            await message.ack()
            
        except Exception as e:
            logger.error(f"Error handling status update message: {e}")
            await message.nack(requeue=True)