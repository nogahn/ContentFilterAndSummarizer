import asyncio
import json
import logging
from aio_pika import IncomingMessage
from app.common.models import URLProcessingResult
from app.common.config import get_llm
from app.common.queue_utils import AsyncQueueManager, URLTaskMessage
from app.llm_workers.processor.processor import URLProcessor
from app.common.config import QUEUE_URL_TASKS

logger = logging.getLogger(__name__)


class AsyncProcessorConsumer:
    def __init__(self):
        self.llm = get_llm()
        self.processor = URLProcessor(self.llm)
        self.queue = AsyncQueueManager()

    async def handle_message(self, message: IncomingMessage):
        async with message.process():
            try:
                message_data = json.loads(message.body.decode())
                url_task = URLTaskMessage.model_validate(message_data)

                logger.info(f"Processing URL: {url_task.url} (retry: {url_task.retry_count})")

                await self.queue.publish_status_update(
                    request_id=url_task.request_id,
                    url=url_task.url,
                    status="processing",
                    detail="URL processing initiated."
                )

                result: URLProcessingResult = await asyncio.to_thread(
                    self.processor.process_url, url_task.url
                )

                if not result:
                    raise Exception("Processor returned None result")

                await self.queue.publish_evaluation_task(
                    url_result=result,
                    priority=url_task.priority,
                    retry_count=0,
                    request_id=url_task.request_id
                )

                logger.info(f"Successfully processed and queued for evaluation: {url_task.url}")

                await self.queue.publish_status_update(
                    request_id=url_task.request_id,
                    url=url_task.url,
                    status="processed",
                    detail="URL content processed and sent for evaluation."
                )

            except Exception as e:
                logger.error(f"Error processing URL message: {e}")
                retry_count = message_data.get("retry_count", 0) + 1
                max_retries = message_data.get("max_retries", 3)

                if retry_count <= max_retries:
                    priority = max(1, url_task.priority - 2)
                    await self.queue.publish_url_task(
                        url=url_task.url,
                        request_id=url_task.request_id,
                        priority=priority,
                        retry_count=retry_count
                    )
                else:
                    await self.queue.publish_status_update(
                        request_id=url_task.request_id,
                        url=url_task.url,
                        status="failed",
                        detail=f"Processing failed after {max_retries} retries: {str(e)}"
                    )

    async def start(self):
        await self.queue.consume(QUEUE_URL_TASKS, self.handle_message)
        while True:
            await asyncio.sleep(1)

    async def close(self):
        await self.queue.close()


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    consumer = AsyncProcessorConsumer()
    try:
        logger.info(">>> Starting async processor consumer...")
        await consumer.start()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        await consumer.close()


if __name__ == "__main__":
    asyncio.run(main())
