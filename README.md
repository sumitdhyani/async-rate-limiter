# async-rate-limiter

A **RateLimiter** with serialized, sliding-window-like execution 

## Overview

This library provides:
A **RateLimiter** with serialized, sliding-window-like execution guarantees.
It is intentionally conservative and explicit, making it suitable for protecting external systems (APIs, databases, hardware) where contract violation and ambiguity are unacceptable.

## Why this library exists

Most RateLimiting utilities:
- rely on best-effort timing
- do not clearly specify stop or overrun behavior
- provide the rate guarentees as an average rather than a mathematical guarentee
- function as a leacky bucket rather than a strict sliding window, sliding window id more appropriare where sticking to guarentees is crucial 

**async-rate-limiter** takes a different approach:

> Behavior is explicit, testable, and deterministic — even if that costs some throughput.

---

## Installation

```bash
pip install py-asyncio-utils
```

### What it does

Enforces a maximum number of executions (a rate) per time window. Tasks pushed to the limiter are executed as bandwidth becomes available. Tasks may be synchronous functions or async coroutines. Internally uses a small ring buffer of recent execution timestamps and a pending queue. When the buffer is full, execution is deferred until the earliest timestamp ages out by `per`.


### Guarantees

- Serialized execution (no concurrent callbacks)
- Completion-based rate limiting
- No more than `rate` task completions occur in any `per` interval(for example a 'rate' 1000 task 'per' 2 seconds )
- No bursts
- FIFO ordering


### API

- `RateLimiter(rate: int, per_ns: int)` — allow `rate` executions per `per` interval.
    - **rate**      : Rate(or the max no.. of tasks) allowd to execure in 'per' nano seconds
    - **per_ns**    : Unit time interval in which at max 'rate' are allowed to execute
- `await push(task: Callable) -> bool` — execute the task, if bandwidth permits, else queue it for future execution
    - **task**: `Callable[[], None | Awaitable[None]]`
        - May be a synchronous function or an async coroutine
        - Takes no arguments
        - Returns nothing

### Example

```python
import asyncio
from async-rate-limiter import RateLimiter

async def work():
    print('did work')

async def main():
    rate_limiter = RateLimiter(10, timedelta(seconds=1))
    for _ in range(50):
        await rate_limiter.push(work)

asyncio.run(main())
```

### Important Semantic Note

This is **not** a token-bucket or admission-based limiter.

The RateLimiter enforces:

> At most `rate` task *completions* per `per` interval, with serialized execution.

This means:
- Tasks are awaited
- Long-running tasks reduce throughput
- No task executes concurrently with another

This design favors correctness and predictability over raw throughput.

### Suitable Use Cases

- Protecting external APIs
- Throttling database writes
- IO-bound pipelines
- Any system where bursts are harmful

### What this RateLimiter is NOT

- Not a token bucket
- Not burst-tolerant
- Not admission-based
- Not suitable for CPU-bound parallel work

If you need those semantics, consider **aiolimiter**.

---

## Comparison with Other Libraries

| Library | Model | Bursts | Concurrency |
|---------|-------|--------|-------------|
| py_asyncio_utils | Serialized, completion-based | No | No |
| aiolimiter | Token bucket | Yes | Yes |

## Design Philosophy

- Prefer explicit semantics over implicit behavior
- Favor determinism over throughput
- Make edge cases testable, not accidental

---

## When to Use This Library

**Use async-rate-limiter if:**
- You care about correctness and predictability
- You want to reason about timing behavior precisely
- You are protecting fragile downstream systems

**Do not use it if:**
- You need maximum throughput
- You rely on bursts
- You want parallel execution

---

## Working Examples

For concrete examples showing actual working code using these classes, see the example code in the `examples/` directory:

- [examples/BasicRateLimiterExample.py](examples/BasicRateLimiterExample.py) — basic `RateLimiter` usage
- [examples/MultipleRateLimitersExample.py](examples/MultipleRateLimitersExample.py) — using multiple `RateLimiter` instances

---

## Build Package from Source

The project uses `pyproject.toml`. To build distribution archives install `build` and run:

```bash
pip install --upgrade build
python -m build
```

The above produces a `dist/` folder with `.whl` and `.tar.gz` files. You can also install locally with:

```bash
pip install .        # install from source
pip install -e .     # editable install for development
```

Alternatively, this repository includes `build_package.py`; you can run it if you prefer (it wraps standard build steps):

```bash
python build_package.py
```

---

## Run Tests

The tests are in the `tests/` directory and use `unittest`'s async test support. You can run them with `unittest` or with `pytest`.

Run with unittest (cross-platform):
```bash
python -m unittest discover -v
```

Run with pytest (if installed):
```bash
pip install pytest
pytest -q
```

Platform-specific helper scripts are provided:
- Windows: `run_tests.bat`
- Unix/macOS: `run_tests.sh`

---

## Notes & Troubleshooting

- The utilities depend only on Python's standard library (`asyncio`, `datetime`, etc.). Tests use `unittest.IsolatedAsyncioTestCase` which requires Python 3.8+.
- If you see timing-sensitive failures, they may be due to scheduling resolution on the host system — increase sleep durations in tests when diagnosing on slow/oversubscribed CI runners.

---

## License

MIT
