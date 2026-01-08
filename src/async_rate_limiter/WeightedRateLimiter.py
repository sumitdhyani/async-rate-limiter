import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable


class WeightMaintainingRingBuffer:
    def __init__(self):
        self.buffer: deque[tuple[int, int]] = deque()
        self.total_weight: int = 0

    def push(self, item: tuple[int, int]) -> None:
        self.total_weight += item[1]
        self.buffer.append(item)

    def get_front(self) -> tuple[int, int]:
        if self.is_empty():
            raise IndexError("RingBuffer is empty")
        return self.buffer[0]

    def is_empty(self) -> bool:
        return len(self.buffer) == 0

    def weight(self) -> int:
        return self.total_weight

    def pop(self) -> bool:
        if len(self.buffer) == 0:
            return False

        self.total_weight -= self.buffer[0][1]
        self.buffer.popleft()
        return True


def ns_to_seconds(ns: int) -> float:
    return ns / 1_000_000_000


"""
    A function returning taking no arguments and returns nothing, 
    can be either a normal synchronous function or a coroutine
"""
Callback = Callable[[], None | Awaitable[None]]

"""
    Implements a rate limiter that allows a certain weight to be consumed.
    Unlike the plain RateLimiter which counts tasks, this counts weights.
    Each task has an associated weight, and the rate limiter ensures that
    within the specified time(a sliding time-window), the total weight consumed
    is <= the specified weight
"""


class WeightedRateLimiter:
    """
    Initializes the rate limiter with a specified rate and time window.
    param rate: the maximum weight allowed in the time window.
    param per: the time window in nanoseconds.
    """

    def __init__(self, allowed_weight: int, per_ns: int) -> None:
        # Ringbuffer to store tuples of (timestamp, weight)
        self.ring_buffer: WeightMaintainingRingBuffer = WeightMaintainingRingBuffer()
        self.per_ns: int = per_ns
        # deque of tuples of (Callback, estimated_weight)
        self.pending_tasks: deque[tuple[Callback, int]] = deque()
        self.allowed_weight: int = allowed_weight

    def bandwidth_available(self, estimated_weight: int) -> bool:
        now: int = time.monotonic_ns()
        # Remove all entries that are out of the time window prior to checking bandwidth
        while (
            not self.ring_buffer.is_empty()
            and self.ring_buffer.get_front()[0] + self.per_ns < now
        ):
            self.ring_buffer.pop()

        return self.ring_buffer.weight() + estimated_weight <= self.allowed_weight

    """
        Executes a given task and logs its execution time.
        param task: a callable which can be synchronous or an async coroutine function.
    """

    async def execute_and_log_task(self, task: Callback, estimated_weight: int) -> None:
        result: None | Awaitable[None] = task()
        if asyncio.iscoroutine(result):
            await result

        self.ring_buffer.push((time.monotonic_ns(), estimated_weight))

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
                            self.ring_buffer.get_front()[0]
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
        Pushes a new task to be executed under the rate limit.
        If the rate limit allows, the task is executed immediately, otehrwise it is queued for later execution.
        Returns True if the task was executed immediately, False if it was queued. 
        Throws ValueError if the estimated weight is invalid, i.e., <= 0 or > allowed_weight
        param task: a callable which can be synchronous or an async coroutine function.
        param estimated_weight: the estimated weight of the task to be executed.
    """

    async def push(self, task: Callback, estimated_weight: int) -> bool:
        if estimated_weight > self.allowed_weight or estimated_weight <= 0:
            raise ValueError(
                f"Estimated weight {estimated_weight} is invalid. It must be > 0 and <= allowed_weight {self.allowed_weight}"
            )
        ret: bool = False
        if len(self.pending_tasks) > 0:
            """
                there are pending tasks, queue this one as well, the condition implies
                that there is already a scheduled on_bandwidth_available event, as per the invariant
                mentioned in on_bandwidth_available method,
                so this task will be in the next wakeup if the bandwidth
                permits else in the one of the susequent ones
            """
            self.pending_tasks.append((task, estimated_weight))
        elif not self.bandwidth_available(estimated_weight):
            """
                No pending tasks but bandwidth not available, queue the task 
                Reaching here also means that since this is the 1st enqueued element, that was not executed immediately,
                due to bandwidth unavailability,
                This is where we kickoff the on_bandwidth_available event scheduling 'loop'
            """
            self.pending_tasks.append((task, estimated_weight))
            self.schedule_bandwidth_available_evt()
        else:
            await self.execute_and_log_task(task, estimated_weight)
            ret = True
        return ret

    async def on_bandwidth_available(self) -> None:
        while len(self.pending_tasks) > 0 and self.bandwidth_available(
            self.pending_tasks[0][1]
        ):
            task: Callback
            estimated_weight: int
            task, estimated_weight = self.pending_tasks.popleft()
            await self.execute_and_log_task(task, estimated_weight)

        """
            If the bandwidth is exhausted but there are still pending tasks,
            schedule the next bandwidthAvailable event, this enforces an admittedly implicit but
            important invariant:
            if pending_tasks is not empty, there is always a scheduled on_bandwidth_available event
        """
        if len(self.pending_tasks) > 0:
            self.schedule_bandwidth_available_evt()


# async def task(num: int, delay: float = 0.0):
#     print(f"Task started at {time.monotonic()} with num={num} and delay={delay}")
#     if delay > 0.0:
#         await asyncio.sleep(delay)
#     print(f"Task ended at {time.monotonic()} with num={num} and delay={delay}")


# def getTask(num: int, delay: float = 0.0) -> Callback:
#     async def localTask():
#         await task(num, delay)

#     return localTask


# async def main():
#     rl = WeightedRateLimiter(allowed_weight=10, per_ns=1_000_000_000)

#     # Step 1: Fill the window completely
#     await rl.push(getTask(1), 10)

#     # Step 2: Queue another task before expiry
#     asyncio.create_task(rl.push(getTask(2, 0.5), 5))
#     asyncio.create_task(rl.push(getTask(3), 3))

#     # Step 3: Wait for window to expire
#     await asyncio.sleep(3)

#     # Step 4: Give event loop time to run scheduled wakeup
#     # This triggers on_bandwidth_available → schedule_bandwidth_available_evt
#     await asyncio.sleep(0.1)


# asyncio.run(main())
