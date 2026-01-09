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

from WeightedRateLimiter import WeightedRateLimiter

# Basic Rate Limiter Example
# This example demonstrates how to use the WeightedRateLimiter to limit the tasks based on total weight.
# While pushing a task to the WeightedRateLimiter, an estimated cost has to be specified for the Limiter
# to able able to impose the weight limit
# In this example, we create a RateLimiter that allows a maximum weight of of 5 per second.
# 5 tasks are pushed with weights 1,2,3,4,5 respectively
# Each tasks prints the time at which it is executed
# The output shows that in an 1 second window, the the total weight is <= 5
# This semantics is being strictly applied
# For example if in a 1 sec window a task of weight 2 can be accomodated, but the next task
# is of weight 3, it will not be executed immediately, it will be queued for later


# interval_ns should be the unit interval in nano seconds
async def basic_rate_limiter_example():
    rate_limiter: WeightedRateLimiter = WeightedRateLimiter(
        allowed_weight=5, per_ns=1000_000_000
    )
    total_tasks = 5
    task_costs = [1, 2, 3, 4, 5]
    task_counter: int = 0
    semaphore: asyncio.Semaphore = asyncio.Semaphore(0)

    def task():
        nonlocal task_counter
        nonlocal semaphore
        print(
            f"Task {task_counter + 1} executed at time {datetime.now()}, weight: {task_costs[task_counter]}"
        )
        task_counter += 1

        if task_counter == total_tasks:
            semaphore.release()

    for i in range(total_tasks):
        await rate_limiter.push(task, task_costs[i])

    await semaphore.acquire()


asyncio.run(basic_rate_limiter_example())
