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
"""Control-flow nodes for the Defty behavior-tree engine.

Provides the four standard composite / decorator nodes:

- :class:`SequenceNode` — tick children in order; all must succeed.
- :class:`SelectorNode` — tick children in order; first success wins.
- :class:`RepeatNode` — repeat a child N times or until a condition.
- :class:`ParallelNode` — tick all children concurrently.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from defty.nodes.base import Context, Node, NodeState, NodeStatus

logger = logging.getLogger(__name__)

__all__ = [
    "SequenceNode",
    "SelectorNode",
    "RepeatNode",
    "ParallelNode",
]


class SequenceNode(Node):
    """Tick children left-to-right; succeed only if **all** children succeed.

    Behaviour per tick:
    - If a child returns RUNNING → this node returns RUNNING.
    - If a child returns FAILURE → this node returns FAILURE immediately.
    - If all children return SUCCESS → this node returns SUCCESS.

    Resumes from the last RUNNING child on the next tick.
    """

    def __init__(
        self,
        *args: Node,
        children: list[Node] | None = None,
        name: str | None = None,
    ) -> None:
        kids = list(args) if args else (children or [])
        super().__init__(name=name, children=kids)
        self._running_index: int = 0

    def tick(self, context: Context) -> NodeStatus:
        """Tick children sequentially from the last running index."""
        for i in range(self._running_index, len(self.children)):
            status = self.children[i].tick(context)
            if status.state == NodeState.RUNNING:
                self._running_index = i
                return NodeStatus.running()
            if status.state == NodeState.FAILURE:
                self._running_index = 0
                return NodeStatus.failure()
        self._running_index = 0
        return NodeStatus.success()

    def reset(self) -> None:
        """Reset the running index and all children."""
        self._running_index = 0
        super().reset()


class SelectorNode(Node):
    """Tick children left-to-right; succeed on the **first** child success.

    Behaviour per tick:
    - If a child returns SUCCESS → this node returns SUCCESS immediately.
    - If a child returns RUNNING → this node returns RUNNING.
    - If all children return FAILURE → this node returns FAILURE.

    Resumes from the last RUNNING child on the next tick.
    """

    def __init__(
        self,
        *args: Node,
        children: list[Node] | None = None,
        name: str | None = None,
    ) -> None:
        kids = list(args) if args else (children or [])
        super().__init__(name=name, children=kids)
        self._running_index: int = 0

    def tick(self, context: Context) -> NodeStatus:
        """Tick children sequentially; return on first success."""
        for i in range(self._running_index, len(self.children)):
            status = self.children[i].tick(context)
            if status.state == NodeState.SUCCESS:
                self._running_index = 0
                return NodeStatus.success()
            if status.state == NodeState.RUNNING:
                self._running_index = i
                return NodeStatus.running()
        self._running_index = 0
        return NodeStatus.failure()

    def reset(self) -> None:
        """Reset the running index and all children."""
        self._running_index = 0
        super().reset()


class RepeatNode(Node):
    """Repeat a single child node N times or until a condition is met.

    Args:
        child: The child node to repeat.
        times: Number of repetitions.  Use ``-1`` for infinite repetition.
        until: Optional callable ``(Context) -> bool``.  If provided and it
               returns *True* after a child tick, the loop stops with SUCCESS.
        name: Optional node name.
    """

    def __init__(
        self,
        child: Node,
        times: int = -1,
        until: Callable[[Context], bool] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name, children=[child])
        self.times = times
        self.until = until
        self._iteration: int = 0

    @property
    def child(self) -> Node:
        """The single child node being repeated."""
        return self.children[0]

    def tick(self, context: Context) -> NodeStatus:
        """Execute one iteration of the child."""
        status = self.child.tick(context)

        if status.state == NodeState.RUNNING:
            return NodeStatus.running()

        if status.state == NodeState.FAILURE:
            self._iteration = 0
            return NodeStatus.failure()

        # Child succeeded
        self._iteration += 1
        self.child.reset()

        if self.until is not None and self.until(context):
            self._iteration = 0
            return NodeStatus.success()

        if self.times != -1 and self._iteration >= self.times:
            self._iteration = 0
            return NodeStatus.success()

        return NodeStatus.running()

    def reset(self) -> None:
        """Reset the iteration counter and children."""
        self._iteration = 0
        super().reset()


class ParallelNode(Node):
    """Tick all children concurrently using threads.

    Args:
        children: List of child nodes to run in parallel.
        policy: ``"wait_all"`` — succeed when all succeed (fail on any failure).
                ``"wait_any"`` — succeed when any one succeeds.
        name: Optional node name.
    """

    def __init__(
        self,
        *args: Node,
        children: list[Node] | None = None,
        policy: str = "wait_all",
        name: str | None = None,
    ) -> None:
        if policy not in ("wait_all", "wait_any"):
            raise ValueError(f"ParallelNode policy must be 'wait_all' or 'wait_any', got {policy!r}")
        kids = list(args) if args else (children or [])
        super().__init__(name=name, children=kids)
        self.policy = policy

    def tick(self, context: Context) -> NodeStatus:
        """Tick all children in parallel threads."""
        if not self.children:
            return NodeStatus.success()

        results: list[NodeStatus] = []
        with ThreadPoolExecutor(max_workers=len(self.children)) as pool:
            futures = {pool.submit(child.tick, context): child for child in self.children}
            for future in as_completed(futures):
                results.append(future.result())

        states = [r.state for r in results]

        if self.policy == "wait_all":
            if any(s == NodeState.FAILURE for s in states):
                return NodeStatus.failure()
            if any(s == NodeState.RUNNING for s in states):
                return NodeStatus.running()
            return NodeStatus.success()
        else:  # wait_any
            if any(s == NodeState.SUCCESS for s in states):
                return NodeStatus.success()
            if any(s == NodeState.RUNNING for s in states):
                return NodeStatus.running()
            return NodeStatus.failure()
