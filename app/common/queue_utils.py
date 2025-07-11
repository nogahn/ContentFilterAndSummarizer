import asyncio
import logging
import datetime
from typing import Callable, Awaitable
from pydantic import BaseModel, Field
from aio_pika import connect_robust, Message, DeliveryMode, Channel, RobustConnection, IncomingMessage
from app.common.models import URLProcessingResult
from app.common.config import QUEUE_URL_TASKS, QUEUE_EVALUATION_TASKS, QUEUE_STATUS_UPDATES, RABBITMQ_AMQP_URL

logger = logging.getLogger(__name__)

class URLTaskMessage(BaseModel):
    url: str
    priority: int = 10
    retry_count: int = 0
    max_retries: int = 3
    request_id: str

class EvaluationTaskMessage(BaseModel):
    url_result: URLProcessingResult
    priority: int = 5
    retry_count: int = 0
    max_retries: int = 3
    request_id: str

class StatusUpdateMessage(BaseModel):
    request_id: str
    url: str | None = None
    status: str
    detail: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    result: URLProcessingResult | None = None

class AsyncQueueManager:
    def __init__(self):
        self.connection: RobustConnection | None = None
        self.channel: Channel | None = None
        self._initialized = False

    async def init(self):
        if self._initialized:
            return

        self.connection = await self.connect_rabbitmq_with_retries(RABBITMQ_AMQP_URL, retries=5, delay_sec=3)
        self.channel = await self.connection.channel()

        await self.channel.declare_queue(QUEUE_URL_TASKS, durable=True, arguments={"x-max-priority": 10})
        await self.channel.declare_queue(QUEUE_EVALUATION_TASKS, durable=True, arguments={"x-max-priority": 10})
        await self.channel.declare_queue(QUEUE_STATUS_UPDATES, durable=True)

        self._initialized = True
        logger.info("AsyncQueueManager initialized")

    async def connect_rabbitmq_with_retries(self, url: str, retries: int = 5, delay_sec: int = 3) -> RobustConnection:
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Trying to connect to RabbitMQ (attempt {attempt}/{retries})...")
                conn = await connect_robust(url)
                logger.info("Successfully connected to RabbitMQ")
                return conn
            except Exception as e:
                logger.warning(f"RabbitMQ connection attempt {attempt} failed: {e}")
                last_exc = e
                await asyncio.sleep(delay_sec)
        logger.error(f"Failed to connect to RabbitMQ after {retries} attempts")
        raise last_exc
    
    async def _publish(self, queue: str, message_obj: BaseModel, priority: int = 0):
        await self.init()

        message_body = message_obj.model_dump_json().encode()
        message = Message(
            body=message_body,
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=priority
        )

        await self.channel.default_exchange.publish(message, routing_key=queue)
        logger.info(f"Published to {queue} with priority {priority}")

    async def publish_url_task(self, url: str, request_id: str, priority: int = 10, retry_count: int = 0):
        msg = URLTaskMessage(url=url, request_id=request_id, priority=priority, retry_count=retry_count)
        await self._publish(QUEUE_URL_TASKS, msg, priority=priority)

        await self.publish_status_update(
            request_id=request_id,
            url=url,
            status="queued",
            detail="URL task queued for processing"
        )

    async def publish_status_update(self, request_id: str, url: str, status: str, detail: str | None = None, result: dict | None = None):
        msg = StatusUpdateMessage(
            request_id=request_id,
            url=url,
            status=status,
            detail=detail,
            result=URLProcessingResult(**result) if result else None
        )
        await self._publish(QUEUE_STATUS_UPDATES, msg)

    async def publish_evaluation_task(self, url_result: URLProcessingResult, request_id: str, priority: int = 5, retry_count: int = 0):
        msg = EvaluationTaskMessage(
            url_result=url_result,
            request_id=request_id,
            priority=priority,
            retry_count=retry_count
        )
        await self._publish(QUEUE_EVALUATION_TASKS, msg, priority=priority)

        await self.publish_status_update(
            request_id=request_id,
            url=url_result.url,
            status="evaluating",
            detail="URL result sent for evaluation"
        )

    async def consume(self, queue_name: str, callback: Callable[[IncomingMessage], Awaitable[None]]):
        await self.init()
        if queue_name in {QUEUE_URL_TASKS, QUEUE_EVALUATION_TASKS}:
            queue = await self.channel.declare_queue(queue_name, durable=True, arguments={"x-max-priority": 10})
        else:
            queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.consume(callback)
        logger.info(f"Started consuming from {queue_name}")


    async def close(self):
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logger.info("Async RabbitMQ connection closed")
