import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../src/async_rate_limiter")
    ),
)

from RateLimiter import RateLimiter


# Multiple Rate Limiters Example
# This example demonstrates how to use multiple RateLimiter instances to limit the rate of task execution.
# In this example, we create three RateLimiter instances with different rates:
# - RateLimiter_1: 5 calls per second
# - RateLimiter_2: 10 calls per second
# - RateLimiter_3: 15 calls per second
# We push 40 tasks to each rate limiter.
# The console output will show that the tasks are executed at their respective rates.
async def multiple_rate_limiters_example():
    rate_limiters: list[RateLimiter] = [
        RateLimiter((i + 1) * 5, 1_000_000_000) for i in range(3)
    ]

    for i in range(3):
        for j in range(40):
            await rate_limiters[i].push(
                lambda i=i, j=j: print(
                    f"Task {j + 1} executed at {datetime.now()} for RateLimiter_{i + 1}"
                )
            )

    # Let the rate limiters run for 8.5 seconds
    await asyncio.sleep(8.5)


asyncio.run(multiple_rate_limiters_example())
