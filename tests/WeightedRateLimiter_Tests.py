import asyncio
import os
import sys
import time
import unittest
from functools import reduce

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../src/async_rate_limiter")
    ),
)
from WeightedRateLimiter import WeightedRateLimiter


def now_ns():
    return time.monotonic_ns()


class TestWeightedRateLimiter(unittest.IsolatedAsyncioTestCase):
    # ----------------------------
    # Helpers
    # ----------------------------

    def make_task(self, log: int, delay: float = 0.0):
        async def task():
            if delay > 0.0:
                await asyncio.sleep(delay)
            log.append(time.monotonic())

        return task

    # ----------------------------
    # Edge Cases
    # ----------------------------

    async def test_single_task_executes_immediately(self):
        log = []
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=1_000_000_000)

        task = self.make_task(log)
        executed = await rl.push(task, 3)

        self.assertTrue(executed)
        self.assertEqual(len(log), 1)

    async def test_invalid_weight_raises(self):
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=1_000_000_000)

        async def task():
            pass

        with self.assertRaises(ValueError):
            await rl.push(task, 0)

        with self.assertRaises(ValueError):
            await rl.push(task, 11)

    # ----------------------------
    # Sliding Window Correctness
    # ----------------------------

    async def test_capacity_not_exceeded_within_window(self):
        log = []
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=500_000_000)

        task = self.make_task(log)

        # Fill window
        await rl.push(task, 5)
        await rl.push(task, 5)

        # This must be delayed
        await rl.push(task, 1)

        self.assertEqual(len(log), 2)

        # After window expires, third should execute
        await asyncio.sleep(0.6)
        self.assertEqual(len(log), 3)

    async def test_expiry_allows_new_work(self):
        log = []
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=500_000_000)

        task = self.make_task(log)

        await rl.push(task, 6)
        await asyncio.sleep(0.6)  # first expires

        await rl.push(task, 5)

        self.assertEqual(len(log), 2)

    async def test_new_work_allowed_if_bandwidth_available(self):
        log = []
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=500_000_000)

        task = self.make_task(log)

        await rl.push(task, 6)
        await asyncio.sleep(0.3)
        await rl.push(task, 4)

        self.assertEqual(len(log), 2)

    async def test_new_work_not_allowed_if_bandwidth_unavailable(self):
        log = []
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=500_000_000)

        task = self.make_task(log)

        await rl.push(task, 6)
        await asyncio.sleep(0.3)
        await rl.push(task, 5)

        self.assertEqual(len(log), 1)
        # total 0.6 sec passed 2nd task must have been executed by now
        await asyncio.sleep(0.3)
        self.assertEqual(len(log), 2)

    # ----------------------------
    # FIFO Blocking Semantics
    # ----------------------------

    async def test_fifo_blocks_smaller_tasks(self):
        log = []
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=300_000_000)

        async def big():
            log.append("big")

        async def small():
            log.append("small")

        await rl.push(big, 10)
        await rl.push(big, 9)
        await rl.push(small, 1)

        await asyncio.sleep(1)

        # small must not execute before second big
        self.assertTrue(log.index("big") < log.index("small"))

    # ----------------------------
    # Heavy Load / Stress
    # ----------------------------

    async def test_heavy_load_no_overrun(self):
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=200_000_000)

        executed = []

        async def task(i):
            executed.append((i, time.monotonic()))

        async def submitter():
            for i in range(100):
                await rl.push(lambda i=i: task(i), 1)

        await submitter()

        # wait for all to flush
        await asyncio.sleep(3)

        # Check sliding window property
        for i in range(len(executed)):
            t0 = executed[i][1]
            weight = 0
            for j in range(i, len(executed)):
                if executed[j][1] - t0 <= 0.2:
                    weight += 1
                else:
                    break
            self.assertLessEqual(weight, 10)

    async def test_tasks_never_overlap(self):
        rl = WeightedRateLimiter(allowed_weight=10, per_ns=1_000_000_000)
        running = 0
        max_running = 0

        async def task():
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.1)
            running -= 1

        for _ in range(10):
            await rl.push(task, 1)

        await asyncio.sleep(2)

        self.assertEqual(max_running, 1)

    # Binary search to find the latest timestamp less than the threshold
    def findLatest(self, timestamps: list[int], threshold: int) -> int:
        low: int = 0
        high: int = len(timestamps) - 1
        result: int = -1
        while low <= high:
            mid: int = (low + high) // 2
            if timestamps[mid] < threshold:
                result = mid
                low = mid + 1
            else:
                high = mid - 1
        return result

    # Binary search to find the earliest timestamp greater than the threshold
    def findEarliest(self, timestamps: list[int], threshold: int) -> int:
        low: int = 0
        high: int = len(timestamps) - 1
        result: int = -1
        while low <= high:
            mid: int = (low + high) // 2
            if timestamps[mid] > threshold:
                result = mid
                high = mid - 1
            else:
                low = mid + 1
        return result

    async def test_1(self):
        total_tasks: int = 1000
        allowed_weight: int = total_tasks // 10
        per: int = 1000_000_000
        await self.do_test(total_tasks, [1] * total_tasks, allowed_weight, per)

    async def test_2(self):
        total_tasks: int = 1000
        allowed_weight: int = total_tasks // 10
        per: int = 1000_000_000
        await self.do_test(total_tasks, [2] * total_tasks, allowed_weight, per)

    async def test_3(self):
        total_tasks: int = 10000
        allowed_weight: int = total_tasks // 10
        per: int = 1000_000_000
        await self.do_test(total_tasks, [1] * total_tasks, allowed_weight, per)

    async def test_4(self):
        total_tasks: int = 10000
        allowed_weight: int = total_tasks // 10
        per: int = 1000_000_000
        await self.do_test(total_tasks, [2] * total_tasks, allowed_weight, per)

    async def test_5(self):
        total_tasks: int = 1000
        allowed_weight: int = total_tasks // 10
        per: int = 1000_000_000
        await self.do_test(total_tasks, [3] * total_tasks, allowed_weight, per)

    # provide 'per' in nano seconds
    async def do_test(
        self, total_tasks: int, weights: list[int], allowed_weight: int, per: int
    ):
        self.assertEqual(len(weights), total_tasks)
        print(
            f"Running WeightedRateLimiter test: totalTasks={total_tasks}, max weight per interval={allowed_weight}, per={per}"
        )
        rateLimiter: WeightedRateLimiter = WeightedRateLimiter(allowed_weight, per)
        executionLog: list[tuple[int, int]] = []

        semaphore: asyncio.Semaphore = asyncio.Semaphore(0)

        async def log_execution():
            nonlocal executionLog
            executionLog.append((time.monotonic_ns(), weights[len(executionLog)]))
            if len(executionLog) == total_tasks:
                semaphore.release()

        # Push tasks
        for i in range(total_tasks):
            await rateLimiter.push(log_execution, weights[i])

        async with semaphore:
            self.assertEqual(len(executionLog), total_tasks)

        total_spare_time: int = 0

        # Check that in any window worth 'allowed_weight', the time taken was <= per
        curr_weight: int = 0
        curr_window_start: int = 0
        total_spare_time: int = 0
        total_windows: int = 0

        task_time_stamps: list[int] = [item[0] for item in executionLog]
        task_weights: list[int] = [item[1] for item in executionLog]

        total_weight_of_executed_tasks: int = reduce(lambda x, y: x + y, task_weights)
        self.assertEqual(
            total_weight_of_executed_tasks, reduce(lambda x, y: x + y, weights)
        )

        # list of tuple[length, totalWeight, totalTime]
        windows: list[tuple[int, int, int]] = []

        for i in range(total_tasks):
            curr_weight += task_weights[i]
            if curr_weight >= allowed_weight:
                curr_window_end: int = i if curr_weight == allowed_weight else i - 1
                self.assertLessEqual(
                    task_time_stamps[curr_window_end]
                    - task_time_stamps[curr_window_start],
                    per,
                )

                windows.append(
                    (
                        curr_window_end - curr_window_start + 1,
                        reduce(
                            lambda x, y: x + y,
                            task_weights[curr_window_start : curr_window_end + 1],
                        ),
                        task_time_stamps[curr_window_end]
                        - task_time_stamps[curr_window_start],
                    )
                )
                total_spare_time += (
                    task_time_stamps[curr_window_start]
                    + per
                    - task_time_stamps[curr_window_end]
                )
                total_windows += 1
                curr_weight -= reduce(
                    lambda x, y: x + y,
                    task_weights[curr_window_start : curr_window_end + 1],
                    0,
                )
                curr_window_start = curr_window_end + 1
            elif i == total_tasks - 1:
                curr_window_end: int = i
                self.assertLessEqual(
                    task_time_stamps[curr_window_end]
                    - task_time_stamps[curr_window_start],
                    per,
                )
                windows.append(
                    (
                        curr_window_end - curr_window_start + 1,
                        reduce(
                            lambda x, y: x + y,
                            task_weights[curr_window_start : curr_window_end + 1],
                        ),
                        task_time_stamps[curr_window_end]
                        - task_time_stamps[curr_window_start],
                    )
                )
                total_spare_time += (
                    task_time_stamps[curr_window_start]
                    + per
                    - task_time_stamps[curr_window_end]
                )
                total_windows += 1

        start_window: int = task_time_stamps[0]
        end_window: int = task_time_stamps[-1]

        curr_start: int = start_window
        curr_end: int = curr_start + per  # 1 second in nanoseconds
        # Slide a 'per' timeimeinterval window across the entire execution log, 1 ms at a time
        # and check there were never more than 'rate' executions in that window
        while curr_end <= end_window:
            start_idx: int = self.findEarliest(task_time_stamps, curr_start)
            end_idx: int = self.findLatest(task_time_stamps, curr_end)
            if start_idx == -1:
                start_idx = 0

            self.assertLessEqual(
                reduce(lambda x, y: x + y, task_weights[start_idx : end_idx + 1], 0),
                allowed_weight,
            )
            curr_start += 1_000_000  # 1 millisecond in nanoseconds
            curr_end += 1_000_000  # 1 millisecond in nanoseconds

        print(
            f"Total time = {(task_time_stamps[total_tasks - 1] - task_time_stamps[0]) / 1000_000_000} s, total weight: {total_weight_of_executed_tasks}, avg weight/task = {total_weight_of_executed_tasks / total_tasks}"
        )
        print(
            f"Net Spare time = {total_spare_time}, total windows = {total_windows}, Average spare time per window: {total_spare_time / total_windows} ns"
        )

        print("Time Window descriptions: ")
        [
            print(f"total tasks = {length}, weight = {weight}, time = {time}")
            for length, weight, time in windows
        ]
