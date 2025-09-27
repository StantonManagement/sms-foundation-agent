from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, ParamSpec, TypeVar


T = TypeVar("T")
P = ParamSpec("P")


async def retry_async(
    func: Callable[P, Awaitable[T]],
    *args: P.args,
    attempts: int = 3,
    base_ms: int = 100,
    cap_ms: int = 2000,
    is_retryable: Callable[[BaseException], bool] | None = None,
    on_retry: Callable[[int, int, BaseException], None] | None = None,
    **kwargs: P.kwargs,
) -> T:
    """Retry an async function with exponential backoff and full jitter.

    Args:
        func: async callable to invoke
        attempts: max attempts (>=1). Total tries equals attempts.
        base_ms: base delay in milliseconds for backoff
        cap_ms: maximum delay cap in milliseconds
        is_retryable: predicate to decide whether to retry on exception
        on_retry: callback invoked before each sleep with (attempt_index starting at 1, backoff_ms, exception)

    Returns:
        Result of func on success

    Raises:
        Propagates last exception when attempts exhausted or not retryable
    """

    if attempts < 1:
        attempts = 1

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - propagate after retries
            last_exc = exc
            retry = True
            if is_retryable is not None:
                try:
                    retry = is_retryable(exc)
                except Exception:
                    retry = False
            if attempt >= attempts or not retry:
                raise

            # Compute exponential backoff with full jitter
            # attempt 1 -> 1 * base, attempt 2 -> 2 * base, ...
            delay_ms = min(cap_ms, base_ms * (2 ** (attempt - 1)))

            # Respect provider hint if present by preferring it over computed backoff,
            # while still bounding by cap to maintain responsiveness.
            retry_after_ms = getattr(exc, "retry_after_ms", None)
            if isinstance(retry_after_ms, int) and retry_after_ms > 0:
                delay_ms = min(retry_after_ms, cap_ms)

            # Full jitter: random between 0 and delay_ms
            backoff_ms = int(random.uniform(0, max(1, delay_ms)))

            if on_retry is not None:
                try:
                    on_retry(attempt, backoff_ms, exc)
                except Exception:
                    pass

            await asyncio.sleep(backoff_ms / 1000.0)

    # Should be unreachable
    assert last_exc is not None
    raise last_exc
