import asyncio
import json
import logging
from aio_pika import IncomingMessage
from app.common.models import URLProcessingResult
from app.common.queue_utils import AsyncQueueManager, EvaluationTaskMessage
from app.common.config import QUEUE_EVALUATION_TASKS, get_llm
from app.common.redis_client import get_redis_key, redis_client
from app.llm_workers.evaluator.evaluator import URLProcessingEvaluator

logger = logging.getLogger(__name__)

class EvaluatorConsumerAsync:
    def __init__(self, prefetch_count: int = 1, score_threshold: float = 7.0):
        self.llm = get_llm()
        self.evaluator = URLProcessingEvaluator(self.llm)
        self.score_threshold = score_threshold
        self.queue_manager = AsyncQueueManager()
        self.prefetch_count = prefetch_count
    
    @staticmethod
    def save_processing_result(result: URLProcessingResult):
        """
        Save the result only if it's new or has a better overall_score.
        """
        key = get_redis_key(result.url)
        existing_data = redis_client.get(key)

        if existing_data:
            existing_result = URLProcessingResult.model_validate_json(existing_data)
            if (
                not existing_result.overall_score or
                (result.overall_score and result.overall_score > existing_result.overall_score)
            ):
                redis_client.set(key, result.model_dump_json())
        else:
            redis_client.set(key, result.model_dump_json())


    async def start(self):
        await self.queue_manager.init()
        await self.queue_manager.channel.set_qos(prefetch_count=self.prefetch_count)
        await self.queue_manager.consume(QUEUE_EVALUATION_TASKS, self.process_message)
        logger.info("EvaluatorConsumerAsync started consuming")
        while True:
            await asyncio.sleep(1)

    async def process_message(self, message: IncomingMessage):
        async with message.process():
            try:
                message_data = json.loads(message.body.decode())
                eval_task = EvaluationTaskMessage.model_validate(message_data)

                logger.info(f"Evaluating URL: {eval_task.url_result.url} (request_id: {eval_task.request_id}, retry: {eval_task.retry_count})")

                await self.queue_manager.publish_status_update(
                    request_id=eval_task.request_id,
                    url=eval_task.url_result.url,
                    status="evaluating",
                    detail="URL evaluation initiated."
                )

                url_result = eval_task.url_result
                evaluation = self.evaluator.evaluate(url_result)

                if not evaluation:
                    raise Exception("Evaluator returned None result")

                url_result.overall_score = evaluation.overall_score
                updated_result = url_result

                self.save_processing_result(updated_result)
                logger.info(f"Saved evaluation result for URL: {url_result.url} (score: {evaluation.overall_score})")

                if evaluation.overall_score >= self.score_threshold:
                    await self.queue_manager.publish_status_update(
                        request_id=eval_task.request_id,
                        url=url_result.url,
                        status="completed",
                        detail=f"URL successfully evaluated and approved (score: {evaluation.overall_score}).",
                        result=updated_result.model_dump()
                    )
                else:
                    retry_priority = max(1, eval_task.priority - 3)
                    await self.queue_manager.publish_status_update(
                        request_id=eval_task.request_id,
                        url=url_result.url,
                        status="reprocessing",
                        detail=f"URL failed evaluation (score: {evaluation.overall_score}), re-queuing (attempt: {eval_task.retry_count + 1})."
                    )
                    await self.queue_manager.publish_url_task(
                        url=url_result.url,
                        priority=retry_priority,
                        retry_count=eval_task.retry_count + 1,
                        request_id=eval_task.request_id
                    )

            except Exception as e:
                logger.error(f"Error evaluating URL message: {e}")
                if 'eval_task' in locals():
                    await self.queue_manager.publish_status_update(
                        request_id=eval_task.request_id,
                        url=eval_task.url_result.url,
                        status="failed",
                        detail=f"Error during evaluation: {str(e)}"
                    )

class EvaluatorWorkerAsync:
    def __init__(self, prefetch_count: int = 1, score_threshold: float = 7.0):
        self.prefetch_count = prefetch_count
        self.score_threshold = score_threshold
        self.consumer = EvaluatorConsumerAsync(prefetch_count, score_threshold)

    async def start(self):
        logger.info(f"Starting Async Evaluator Worker (threshold: {self.score_threshold})...")
        await self.consumer.start()

async def main():
    import argparse

    parser = argparse.ArgumentParser(description='Async URL Evaluator Consumer')
    parser.add_argument('--prefetch', type=int, default=1)
    parser.add_argument('--threshold', type=float, default=7.0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    worker = EvaluatorWorkerAsync(prefetch_count=args.prefetch, score_threshold=args.threshold)
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())
