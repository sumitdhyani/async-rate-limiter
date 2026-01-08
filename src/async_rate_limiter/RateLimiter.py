import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable

from Reuseables import RingBuffer


def ns_to_seconds(ns: int) -> float:
    return ns / 1_000_000_000


# A function returning None that can be either a normal synchronous function or a coroutine
Callback = Callable[[], None | Awaitable[None]]

"""
    Implements a rate limiter that allows a certain number of tasks to be executed
    within a specified time window.
"""


class RateLimiter:
    """
    Initializes the rate limiter with a specified rate and time window.
    param rate: the maximum number of tasks allowed in the time window.
    param per: the time window in nanoseconds.
    """

    def __init__(self, rate: int, per_ns: int) -> None:
        self.ring_buffer: RingBuffer[int] = RingBuffer[int](rate)
        self.rate: int = rate
        self.per_ns: int = per_ns
        self.pending_tasks: deque[Callback] = deque()

    def bandwidth_available(self) -> bool:
        return (
            not self.ring_buffer.is_full()
            or self.ring_buffer.get_front() + self.per_ns < time.monotonic_ns()
        )

    """
        Executes a given task and logs its execution time.
        param task: a callable which can be synchronous or an async coroutine function.
    """

    async def execute_and_log_task(self, task: Callback) -> None:
        result: None | Awaitable[None] = task()
        if asyncio.iscoroutine(result):
            await result

        self.ring_buffer.push(time.monotonic_ns())

    """
        Schedule the on_bandwidth_available event for when bandwidth becomes available
        i.e., when the oldest timestamp in the ring_buffer + per is reached
        i.e when t = ring_buffer.get_front() + per
        In order not to block the caller until the bandwidth is available,
        we should not block here, so we schedule the on_bandwidth_available event asynchronously
    """

    def schedule_bandwidth_available_evt(self) -> None:
        asyncio.create_task(
            asyncio.sleep(
                ns_to_seconds(
                    (
                        # To avoid negative sleep times, we max with 0, not a bug but general programmimg hygine
                        max(
                            self.ring_buffer.get_front()
                            + self.per_ns
                            - time.monotonic_ns(),
                            0,
                        )
                    )
                )
            )
        ).add_done_callback(
            lambda coro_object: asyncio.create_task(self.on_bandwidth_available())
            # Check if the sleep task was not cancelled due to something like a shutdown
            if not coro_object.cancelled()
            else None,
        )

    """
        param task: a callable which can be synchronous or an async coroutine function.
        Pushes a new task to be executed under the rate limit.
        If the rate limit allows, the task is executed immediately, otehrwise it is queued for later execution.
        Returns True if the task was executed immediately, False if it was queued.
    """

    async def push(self, task: Callback) -> bool:
        ret: bool = False
        if len(self.pending_tasks) > 0:
            """
                there are pending tasks, queue this one as well, the condition implies
                that there is already a scheduled on_bandwidth_available event, as per the invariant
                mentioned in on_bandwidth_available method,
                so this task will be in the next wakeup if the bandwidth
                permits else in the one of the susequent ones
            """
            self.pending_tasks.append(task)
        elif not self.bandwidth_available():
            """
                No pending tasks but bandwidth not available, queue the task 
                Reaching here also means that since this is the 1st enqueued element, that was not executed immediately,
                due to bandwidth unavailability,
                This is where we kickoff the on_bandwidth_available event scheduling 'loop'
            """
            self.pending_tasks.append(task)
            self.schedule_bandwidth_available_evt()
        else:
            await self.execute_and_log_task(task)
            ret = True
        return ret

    async def on_bandwidth_available(self) -> None:
        while len(self.pending_tasks) > 0 and self.bandwidth_available():
            now: int = time.monotonic_ns()
            while (
                len(self.pending_tasks) > 0
                and self.ring_buffer.get_front() + self.per_ns < now
            ):
                await self.execute_and_log_task(self.pending_tasks.popleft())

        """
            If the bandwidth is exhausted but there are still pending tasks,
            schedule the next bandwidthAvailable event, this enforces an admittedly implicit but
            important invariant:
            if pending_tasks is not empty, there is always a scheduled on_bandwidth_available event
        """
        if len(self.pending_tasks) > 0:
            self.schedule_bandwidth_available_evt()
