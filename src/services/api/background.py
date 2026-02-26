# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import time
import functools
from collections import deque
from enum import Enum
from threading import Lock
from typing import Any
from typing import Callable
from typing import Optional
from uuid import uuid4

from fastapi import BackgroundTasks
from pydantic import BaseModel
from pydantic import StrictStr
from pydantic import StrictInt


def _ts():
    """Return current Unix timestamp (seconds since epoch)"""
    return int(time.time())


class BackgroundOpStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    succeeded = 'succeeded'
    failed = 'failed'

    @property
    def is_completed(self):
        """True if the operation is in a terminal state (succeeded/failed)"""
        return self in (BackgroundOpStatus.succeeded, BackgroundOpStatus.failed)


class BackgroundOpRecord(BaseModel):
    """Metadata and outcome for a single background operation"""

    op_id: StrictStr
    created_at: StrictInt
    started_at: Optional[StrictInt] = None
    finished_at: Optional[StrictInt] = None
    status: BackgroundOpStatus = BackgroundOpStatus.queued
    result: Optional[Any] = None
    error: Optional[StrictStr] = None


class BackgroundOpError(Exception):
    """Raised when a background operation cannot be enqueued/executed"""

    pass


class BackgroundOpManager:
    """
    In-memory FIFO operation queue.

    Uses BackgroundTasks to schedule a `drain()` call after the response,
    so `enqueue()` is fast and non-blocking for the client.
    """

    DEFAULT_MAX_QUEUE_SIZE = 128

    def __init__(self, max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE):
        # max number of queued (pending) operations allowed at a time
        self._max_queue_size = max_queue_size

        # FIFO queue of operation IDs waiting to be executed
        self._queue = deque()
        self._jobs = {}
        self._workers = {}

        # protects _queue/_jobs/_workers/_drain_scheduled from concurrent access
        self._mx = Lock()

        # whether a drain task has already been scheduled via BackgroundTasks
        self._drain_scheduled = False

    def enqueue(
        self,
        background_tasks: BackgroundTasks,
        func: Callable,
        *args,
        **kwargs,
    ) -> BackgroundOpRecord:
        """Enqueue a function for background execution and return its record"""

        assert isinstance(background_tasks, BackgroundTasks)
        assert callable(func), '`func` argument should be function or lambda'

        with self._mx:
            if len(self._queue) >= self._max_queue_size:
                raise BackgroundOpError(
                    f'Background operation queue is full ({self._max_queue_size})'
                )

            op_id = str(uuid4())
            record = BackgroundOpRecord(op_id=op_id, created_at=_ts())

            self._jobs[op_id] = record
            # store the callable for later execution (outside the lock)
            self._workers[op_id] = functools.partial(func, *args, **kwargs)
            self._queue.append(op_id)

            if not self._drain_scheduled:
                # schedule a single drain() call after the current response
                background_tasks.add_task(self.drain)
                self._drain_scheduled = True

            # Best-effort pruning: keep history bounded by dropping oldest completed records
            if len(self._jobs) > self._max_queue_size:
                oldest = min(self._jobs.values(), key=lambda record: record.created_at)
                if oldest.status.is_completed:
                    del self._jobs[oldest.op_id]

        return record

    def drain(self):
        """Run queued operations sequentially until the queue is empty"""

        while True:
            with self._mx:
                if not self._queue:
                    # allow future enqueue() calls to schedule the next drain()
                    self._drain_scheduled = False
                    return

                op_id = self._queue.popleft()
                record = self._jobs[op_id]
                func = self._workers.pop(op_id)

                record.status = BackgroundOpStatus.running
                record.started_at = _ts()

            # execute outside the lock to avoid blocking enqueues/status reads
            result = error = status = None
            try:
                result = func()
            except Exception as e:  # noqa: BLE001
                status = BackgroundOpStatus.failed
                error = str(e)
            else:
                status = BackgroundOpStatus.succeeded

            with self._mx:
                record.result = result
                record.error = error
                record.status = status
                record.finished_at = _ts()

    def get_record(self, op_id: str) -> BackgroundOpRecord | None:
        """Return a deep copy of a single record"""

        with self._mx:
            record = self._jobs.get(op_id)
            return record.copy(deep=True) if record else None

    def get_records(self) -> list:
        """Return deep copies of all records, sorted oldest-first by created_at"""

        with self._mx:
            records = [record.copy(deep=True) for record in self._jobs.values()]

        # stable-ish ordering (oldest first)
        records.sort(key=lambda record: record.created_at)
        return records
