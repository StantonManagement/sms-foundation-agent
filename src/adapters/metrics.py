from __future__ import annotations

from typing import Any, ClassVar, Dict

import structlog


logger = structlog.get_logger(__name__)


class Metrics:
    """Very lightweight in-process counter helper.

    In lieu of a full metrics backend, increments are logged as structured events
    while maintaining in-memory counters for optional inspection in tests.
    """

    _counters: ClassVar[Dict[str, int]] = {}

    @classmethod
    def inc(cls, name: str, **labels: Any) -> None:
        cls._counters[name] = cls._counters.get(name, 0) + 1
        logger.info("metric_increment", metric=name, **({"labels": labels} if labels else {}))

    @classmethod
    def get(cls, name: str) -> int:
        return int(cls._counters.get(name, 0))

