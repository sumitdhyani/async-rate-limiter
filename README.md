# async-rate-limiter

This library provides a **RateLimiter** with serialized, strict
sliding-window execution guarantees.

## Overview

This library provides an interface to serially execute tasks, in
accordance with strict sliding-window semantics. It is intentionally
conservative and explicit, making it suitable for protecting external
systems (APIs, databases, hardware) where contract violation and
ambiguity are unacceptable.

**async-rate-limiter** takes a different approach:

> Behavior is explicit, testable, and deterministic --- even if that
> costs some throughput.

------------------------------------------------------------------------

## Installation

``` bash
pip install async_rate_limiter
```

### What it does

Enforces a maximum number of task completions per time window. Tasks
pushed to the limiter are executed as bandwidth becomes available. Tasks
may be synchronous functions or async coroutines. Internally uses a
small ring buffer of recent task completion timestamps and a pending
queue. When the buffer is full, execution is deferred until the earliest
timestamp ages out by `per`.

In addition to task-count-based limiting, the library also provides a
**WeightedRateLimiter**, which enforces a maximum **total weight** per
time window instead of a maximum number of tasks.

This is useful when tasks represent different amounts of work or
resource usage (for example, network bytes sent, database rows written,
or request cost units), and throttling must be based on total cost
rather than task count.

### Guarantees

-   Serialized execution (no concurrent callbacks)
-   Completion-based rate limiting
-   No more than `rate` task completions occur in any `per` interval
    (e.g. at most 1000 completions per 2 seconds)
-   FIFO ordering

For `WeightedRateLimiter`, the same guarantees apply, except:

-   Rate limiting is based on **total weight** instead of number of
    tasks
-   No more than `allowed_weight` total weight is consumed in any `per`
    interval
-   Tasks are still executed strictly in FIFO order

### API

-   `RateLimiter(rate: int, per_ns: int)` --- allow `rate` task
    completions per `per` interval.
    -   **rate** : Maximum number of task completions allowed per
        interval
    -   **per_ns** : Unit time interval in nanoseconds in which at max
        `rate` are allowed to complete
-   `await push(task: Callable) -> bool`
    -   Executes the task immediately if bandwidth permits, otherwise queues it.<br>
        Returns True if the task was executed immediately, False if it was queued
    - Params
        -   **task**: `Callable[[], None | Awaitable[None]]`
            -   May be a synchronous function or an async coroutine
            -   Takes no arguments
            -   Returns nothing

### Weighted API

-   `WeightedRateLimiter(allowed_weight: int, per_ns: int)` --- allow
    total weight `allowed_weight` per `per` interval.
    -   **allowed_weight** : Maximum total weight allowed per interval
    -   **per_ns** : Unit time interval in nanoseconds
-   `await push(task: Callable, estimated_weight: int) -> bool`
    -   Executes the task immediately if bandwidth permits, otherwise queues it.<br>
        Returns True if the task was executed immediately, False if it was queued
    - Params
        -   **task**: `Callable[[], None | Awaitable[None]]`
            -   May be a synchronous function or an async coroutine
            -   Takes no arguments
            -   Returns nothing
        -   **estimated_weight**:
            -   Must be `> 0` and `<= allowed_weight`
            -   Represents the estimated resource cost of the task

### Example

``` python
import asyncio
from async_rate_limiter import RateLimiter

async def work():
    print('did work')

async def main():
    rate_limiter = RateLimiter(10, 1_000_000_000)
    for _ in range(50):
        await rate_limiter.push(work)

asyncio.run(main())
```

### Weighted Example

``` python
import asyncio
from async_rate_limiter import WeightedRateLimiter

async def send_packet(size):
    print(f"sending {size} bytes")

def make_task(size):
    async def task():
        await send_packet(size)
    return task

async def main():
    # Allow 1000 bytes per second
    limiter = WeightedRateLimiter(allowed_weight=1000, per_ns=1_000_000_000)

    packets = [200, 400, 700, 300]

    for size in packets:
        await limiter.push(make_task(size), estimated_weight=size)

asyncio.run(main())
```

In this example, execution is throttled based on total bytes sent per
second rather than number of tasks.

### Important Semantic Note

This is **not** a token-bucket or admission-based limiter.

The RateLimiter enforces:

> At most `rate` task *completions* per `per` interval, with serialized
> execution.

The same completion-based semantics apply to `WeightedRateLimiter`:

> At most `allowed_weight` total weight of task completions per `per`
> interval, with serialized execution.

This means: - Tasks are awaited - Weight is charged only after task
completion - Long-running or heavy tasks reduce throughput - No task
executes concurrently with another

This design favors correctness and predictability over raw throughput.

### Suitable Use Cases

-   Protecting external APIs
-   Throttling database writes
-   IO-bound pipelines
-   Any system where bursts are harmful

Additional use cases for `WeightedRateLimiter`:

-   Network bandwidth throttling (bytes sent per second)
-   API cost-unit quotas
-   Database write amplification control
-   Any system where tasks have non-uniform cost

### What this RateLimiter is NOT

-   Not a token bucket
-   Not burst-tolerant
-   Not admission-based
-   Not suitable for CPU-bound parallel work

If you need those semantics, consider **aiolimiter**.

------------------------------------------------------------------------

## Comparison with Other Libraries

  ------------------------------------------------------------------------------------------
  Library                 Model              Bursts      Concurrency       Cost-Based
  ----------------------- ------------------ ----------- ----------------- -----------------
  async-rate-limiter      Sliding window,    No          No                No
  (RateLimiter)           completion-based                                 

  async-rate-limiter      Sliding window,    No          No                Yes
  (WeightedRateLimiter)   completion-based                                 

  aiolimiter              Token bucket       Yes         Yes               No
  ------------------------------------------------------------------------------------------

## Design Philosophy

-   Prefer explicit semantics over implicit behavior
-   Favor determinism over throughput
-   Make edge cases testable, not accidental

------------------------------------------------------------------------

## When to Use This Library

**Use async-rate-limiter if:** - You care about correctness and
predictability - You want to reason about timing behavior precisely -
You are protecting fragile downstream systems

**Do not use it if:** - You need maximum throughput - You rely on
bursts - You want parallel execution

------------------------------------------------------------------------

## Working Examples

For concrete examples showing actual working code using these classes,
see the example code in the `examples/` directory:

-   `examples/BasicRateLimiterExample.py` --- basic `RateLimiter` usage
-   `examples/WeightedRateLimiterExample.py` --- basic
    `WeightedRateLimiter` usage

------------------------------------------------------------------------

## Build Package from Source

The project uses `pyproject.toml`. To build distribution archives
install `build` and run:

``` bash
pip install --upgrade build
python -m build
```

The above produces a `dist/` folder with `.whl` and `.tar.gz` files. You
can also install locally with:

``` bash
pip install .        # install from source
pip install -e .     # editable install for development
```

------------------------------------------------------------------------

## Run Tests

The tests are in the `tests/` directory and use `unittest`'s async test
support. You can run them with `unittest` or with `pytest`.

Run with unittest (cross-platform):

``` bash
python -m unittest discover -v
```

Run with pytest (if installed):

``` bash
pip install pytest
pytest -q
```

------------------------------------------------------------------------

## Notes & Troubleshooting

-   The utilities depend only on Python's standard library (`asyncio`,
    `time`, etc.). Tests use `unittest.IsolatedAsyncioTestCase` which
    requires Python 3.8+.
-   If you see timing-sensitive failures, they may be due to scheduling
    resolution on the host system --- increase sleep durations in tests
    when diagnosing on slow or oversubscribed CI runners.

------------------------------------------------------------------------

## License

MIT
