import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../src/async-rate-limiter")
    ),
)

from RateLimiter import RateLimiter


# Basic Rate Limiter Example
# This example demonstrates how to use the RateLimiter to limit the rate of task execution.
# In this example, we create a RateLimiter that allows a maximum of 5 calls per second.
# push 20 tasks to the rate limiter.
# The conslole output will show that the tasks are executed at a rate of 5 per second.
async def basic_rate_limiter_example():
    rate_limiter: RateLimiter = RateLimiter(5, 1_000_000_000)

    for i in range(20):
        await rate_limiter.push(
            lambda i=i: print(f"Task {i + 1} executed at {datetime.now()}")
        )

    # Let the rate limiter run for 10.5 seconds
    await asyncio.sleep(4.5)


asyncio.run(basic_rate_limiter_example())
