import asyncio
import os
import sys
import time
import unittest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../src/async-rate-limiter")
    ),
)
from RateLimiter import RateLimiter


class RateLimiterTests(unittest.IsolatedAsyncioTestCase):
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
        await self.do_test(1000, 100, 1)

    async def test_2(self):
        await self.do_test(10000, 1000, 1)

    # provide 'per' in seconds
    async def do_test(self, totalTasks: int, rate: int, per: int):
        per *= 1_000_000_000  # convert to nanoseconds
        print(
            f"Running RateLimiter test: totalTasks={totalTasks}, rate={rate}, per={per}"
        )
        rateLimiter: RateLimiter = RateLimiter(rate, per)
        executionLog: list[int] = []

        async def log_execution():
            nonlocal executionLog
            executionLog.append(time.monotonic_ns())

        # Push 1000 tasks
        for _ in range(totalTasks):
            await rateLimiter.push(log_execution)
        # Wait enough time for all tasks to complete
        await asyncio.sleep((totalTasks // rate) * per // 1_000_000_000 + 1)
        self.assertEqual(len(executionLog), totalTasks)

        totalSpareTime: int = 0
        # Check that no more than 'rate' tasks were executed in any 'per' time window
        for i in range(rate - 1, totalTasks, rate):
            self.assertLessEqual(executionLog[i] - executionLog[i - rate + 1], per)
            totalSpareTime += executionLog[i - rate + 1] + per - executionLog[i]

        # Check that there is at least 'per' time difference a task and the task 'rate' positions before it
        for i in range(totalTasks - rate):
            self.assertGreater(executionLog[i + rate] - executionLog[i], per)

        startWindow: int = executionLog[0]
        endWindow: int = executionLog[-1]

        currStart: int = startWindow
        cuurrEnd: int = currStart + per  # 1 second in nanoseconds
        # Slide a 'per' timeimeinterval window across the entire execution log, 1 ms at a time
        # and check there were never more than 'rate' executions in that window
        while cuurrEnd <= endWindow:
            startIdx: int = self.findEarliest(executionLog, currStart)
            endIdx: int = self.findLatest(executionLog, cuurrEnd)
            if startIdx == -1:
                startIdx = 0
            self.assertLessEqual(endIdx - startIdx + 1, rate)
            currStart += 1_000_000  # 1 millisecond in nanoseconds
            cuurrEnd += 1_000_000  # 1 millisecond in nanoseconds
        print(
            f"Total Spare time = {totalSpareTime}, Average spare time per window: {totalSpareTime / (totalTasks // rate)} ns"
        )
