import asyncio, logging
from uuid import UUID

logger = logging.getLogger("ecoflow")

class InternalJobQueue:
    """Async in-memory queue. Accelerator only. PostgreSQL jobs table is the source of truth."""
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task = None
        self._process_fn = None

    async def enqueue(self, raw_message_id: UUID):
        await self._queue.put(raw_message_id)
        logger.info(f"job_enqueued raw_message_id={raw_message_id}")

    async def start(self, process_fn):
        self._process_fn = process_fn
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("job_worker_started")

    async def stop(self):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("job_worker_stopped")

    async def _worker(self):
        while True:
            raw_message_id = await self._queue.get()
            try:
                await self._process_fn(raw_message_id)
            except Exception as e:
                logger.error(f"job_failed raw_message_id={raw_message_id} error={e}")
            finally:
                self._queue.task_done()

job_queue = InternalJobQueue()
