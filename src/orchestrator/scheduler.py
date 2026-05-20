"""Task Scheduler — Priority-based task queuing and dispatch."""

import asyncio
import heapq
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class QueueCapacityError(RuntimeError):
    """Raised when a task cannot be durably reserved in a queue."""


class PriorityQueue:
    def __init__(self):
        self._queue = []
        self._counter = 0

    def push(self, item: Any, priority: int = 0) -> None:
        heapq.heappush(self._queue, (-priority, self._counter, item))
        self._counter += 1

    def pop(self) -> Optional[Any]:
        if self._queue:
            return heapq.heappop(self._queue)[2]
        return None

    def peek(self) -> Optional[Any]:
        if self._queue:
            return self._queue[0][2]
        return None

    def __len__(self) -> int:
        return len(self._queue)


class TaskScheduler:
    def __init__(self, max_queue_size: Optional[int] = None):
        self._queues: Dict[str, PriorityQueue] = {}
        self._scheduled: Dict[str, float] = {}
        self._in_flight: Dict[str, Dict] = {}
        self._max_retries = 3
        self._max_queue_size = max_queue_size
        self._queue_reservations: Dict[str, int] = {}
        self._audit_records: List[Dict[str, Any]] = []

    @property
    def audit_records(self) -> List[Dict[str, Any]]:
        return list(self._audit_records)

    def _record_decision(
        self, action: str, queue: str, task_id: Optional[str], reason: str
    ) -> None:
        record = {
            "action": action,
            "queue": queue,
            "task_id": task_id,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._audit_records.append(record)
        logger.info("scheduler queue decision: %s", record)

    def _queue_is_full(self, queue: str) -> bool:
        if self._max_queue_size is None:
            return False
        return self._queue_reservations.get(queue, 0) >= self._max_queue_size

    def _reserve_capacity(self, queue: str, task_id: str) -> None:
        if self._queue_is_full(queue):
            self._record_decision("enqueue_rejected", queue, task_id, "queue_capacity_exhausted")
            raise QueueCapacityError(f"queue {queue!r} is at capacity")
        self._queue_reservations[queue] = self._queue_reservations.get(queue, 0) + 1

    def _release_capacity(self, queue: str) -> None:
        current = self._queue_reservations.get(queue, 0)
        if current <= 1:
            self._queue_reservations.pop(queue, None)
        else:
            self._queue_reservations[queue] = current - 1

    def enqueue(self, task: Dict, queue: str = "default", priority: int = 0) -> str:
        task_id = task.get("id") or str(uuid4())
        previous_values = {
            key: task.get(key) for key in ("id", "enqueued_at", "retries", "priority")
        }
        missing_keys = {key for key in previous_values if key not in task}

        self._reserve_capacity(queue, task_id)
        try:
            task["id"] = task_id
            task["enqueued_at"] = time.time()
            task["retries"] = task.get("retries", 0)
            task["priority"] = priority

            if queue not in self._queues:
                self._queues[queue] = PriorityQueue()
            self._queues[queue].push(task, priority)
        except Exception:
            self._release_capacity(queue)
            for key, value in previous_values.items():
                if key in missing_keys:
                    task.pop(key, None)
                else:
                    task[key] = value
            self._record_decision("enqueue_rolled_back", queue, task_id, "queue_push_failed")
            raise

        self._record_decision("enqueue_committed", queue, task_id, "capacity_reserved")
        return task_id

    def schedule(self, task: Dict, delay: float, queue: str = "default", priority: int = 0) -> str:
        task_id = str(uuid4())
        task["id"] = task_id
        task["queue"] = queue
        task["priority"] = priority
        self._scheduled[task_id] = time.time() + delay
        return task_id

    async def dequeue(self, queue: str = "default", timeout: float = 1.0) -> Optional[Dict]:
        now = time.time()
        expired = [tid for tid, t in self._scheduled.items() if t <= now]
        for tid in expired:
            task = self._scheduled.pop(tid)
            if task:
                self.enqueue(task, task.get("queue", queue), priority=task.get("priority", 0))

        if queue in self._queues and len(self._queues[queue]) > 0:
            task = self._queues[queue].pop()
            if task:
                self._release_capacity(queue)
                self._in_flight[task["id"]] = task
                return task
        return None

    def complete(self, task_id: str) -> bool:
        return self._in_flight.pop(task_id, None) is not None

    def fail(self, task_id: str, queue: str = "default") -> bool:
        task = self._in_flight.get(task_id)
        if task:
            previous_retries = task.get("retries", 0)
            next_retries = previous_retries + 1
            if next_retries < self._max_retries:
                task["retries"] = next_retries
                try:
                    self.enqueue(task, queue, priority=task.get("priority", 0))
                except Exception:
                    task["retries"] = previous_retries
                    self._record_decision(
                        "retry_deferred", queue, task_id, "enqueue_transaction_failed"
                    )
                    return False
                self._in_flight.pop(task_id, None)
                return True
            task["retries"] = next_retries
        return False

# 2019-04-25T08:37:12 update

# 2019-06-04T16:40:00 update

# 2019-07-11T12:01:28 update

# 2019-08-02T12:20:21 update

# 2019-08-23T10:38:50 update

# 2019-10-31T13:55:52 update

# 2019-11-04T20:12:32 update

# 2019-12-13T12:22:36 update

# 2020-02-01T10:32:37 update

# 2020-02-26T09:44:38 update

# 2020-03-09T19:00:55 update

# 2020-05-01T18:40:34 update

# 2020-05-12T15:10:31 update

# 2020-06-30T13:24:19 update

# 2020-09-22T16:00:45 update

# 2020-10-20T10:52:48 update

# 2020-10-21T12:18:08 update

# 2020-11-06T12:35:01 update

# 2020-12-09T08:09:33 update

# 2021-01-07T08:20:36 update

# 2021-10-02T15:23:16 update

# 2021-10-06T16:14:57 update

# 2021-10-06T09:27:41 update

# 2021-11-19T08:37:40 update

# 2022-03-01T16:39:54 update

# 2022-05-26T13:43:07 update

# 2022-06-02T10:50:58 update

# 2022-06-14T10:46:48 update

# 2022-07-31T16:44:34 update

# 2022-08-30T18:20:12 update

# 2022-11-04T14:47:03 update

# 2022-12-06T10:36:49 update

# 2022-12-22T13:21:12 update

# 2022-12-26T12:24:50 update

# 2023-03-09T08:09:55 update

# 2023-05-01T10:07:37 update

# 2023-06-08T14:32:15 update

# 2023-07-14T17:24:18 update

# 2023-12-14T08:38:31 update

# 2024-02-20T13:43:58 update

# 2024-03-24T08:52:42 update

# 2024-03-28T15:27:17 update

# 2024-03-29T18:10:33 update

# 2024-04-15T20:18:31 update

# 2024-05-27T13:11:52 update

# 2024-05-27T16:42:56 update

# 2024-06-20T13:03:45 update

# 2024-06-28T12:32:58 update

# 2024-07-10T14:10:16 update

# 2024-07-26T14:18:59 update

# 2024-08-12T08:21:05 update

# 2024-08-21T16:58:40 update

# 2024-09-27T19:54:30 update

# 2024-10-21T13:47:42 update

# 2024-11-11T09:19:27 update

# 2024-12-24T08:23:41 update

# 2025-02-14T10:35:15 update

# 2025-03-31T18:09:40 update

# 2025-06-21T17:32:49 update

# 2025-07-21T16:52:28 update

# 2025-08-20T19:45:16 update

# 2025-11-04T18:54:24 update

# 2025-12-09T20:17:36 update

# 2026-01-12T15:42:32 update

# 2026-01-23T14:41:20 update

# 2026-03-18T14:43:07 update

# 2026-04-13T11:43:19 update
