# Copyright (c) 2026 APRL Technologies Inc.
# Author: Yiju Li
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utility leaf nodes for the Defty behavior-tree engine."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from defty.nodes.base import Context, Node, NodeStatus

logger = logging.getLogger(__name__)

__all__ = ["WaitNode", "ConditionNode"]


class WaitNode(Node):
    """Wait for a specified duration using RUNNING status (non-blocking)."""

    def __init__(self, seconds: float = 1.0, name: str | None = None) -> None:
        super().__init__(name=name or f"Wait({seconds}s)")
        self.seconds = seconds
        self._start_time: float | None = None

    def tick(self, context: Context) -> NodeStatus:
        """Return RUNNING until the wait duration has elapsed."""
        if self._start_time is None:
            self._start_time = time.monotonic()
        elapsed = time.monotonic() - self._start_time
        if elapsed >= self.seconds:
            self._start_time = None
            return NodeStatus.success()
        return NodeStatus.running(remaining=self.seconds - elapsed)

    def reset(self) -> None:
        """Reset the timer."""
        self._start_time = None
        super().reset()


class ConditionNode(Node):
    """Check a condition on the blackboard (context.memory).

    Returns SUCCESS if the condition is met, FAILURE otherwise.
    """

    def __init__(self, key: str, value: Any = None, predicate: Callable[[Any], bool] | None = None, exists: bool | None = None, name: str | None = None) -> None:
        super().__init__(name=name or f"Condition({key})")
        self.key = key
        self.value = value
        self.predicate = predicate
        self.exists = exists if exists is not None else (value is None and predicate is None)

    def tick(self, context: Context) -> NodeStatus:
        """Evaluate the condition against the blackboard."""
        if self.key not in context.memory:
            return NodeStatus.failure(reason=f"key_missing:{self.key}")
        actual = context.memory[self.key]
        if self.exists and self.value is None and self.predicate is None:
            return NodeStatus.success()
        if self.predicate is not None:
            try:
                result = self.predicate(actual)
                return NodeStatus.success() if result else NodeStatus.failure()
            except Exception as exc:
                logger.error("ConditionNode predicate error: %s", exc)
                return NodeStatus.failure(reason=str(exc))
        if self.value is not None:
            if actual == self.value:
                return NodeStatus.success()
            return NodeStatus.failure(reason=f"expected={self.value!r}, got={actual!r}")
        return NodeStatus.success()
