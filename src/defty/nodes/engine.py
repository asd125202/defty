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
"""Behavior-tree runner — the main execution loop.

:class:`BehaviorTreeRunner` repeatedly ticks the root node at a controlled
frequency, refreshing the :class:`Context` from the connected robot before
each tick.
"""

from __future__ import annotations

import logging
import signal
import time

from defty.nodes.base import Context, Node, NodeState, NodeStatus

logger = logging.getLogger(__name__)

__all__ = ["BehaviorTreeRunner"]


class BehaviorTreeRunner:
    """Execute a behavior tree by ticking the root node in a loop.

    The runner:
    1. Refreshes ``context.cameras`` and ``context.joint_states`` from the
       robot (if one is connected).
    2. Ticks the root node.
    3. Sleeps to maintain the target frequency.
    4. Repeats until the root returns SUCCESS or FAILURE, or the runner
       is stopped via :meth:`stop` / Ctrl+C.

    Args:
        root: The root node of the behavior tree.
        context: The shared :class:`Context` instance.
        frequency: Target tick rate in Hz (default 30).
    """

    def __init__(
        self,
        root: Node,
        context: Context,
        frequency: float = 30.0,
    ) -> None:
        self.root = root
        self.context = context
        self.frequency = frequency
        self._running = False
        self._tick_count = 0
        self._last_status: NodeStatus | None = None

    @property
    def tick_count(self) -> int:
        """Number of ticks executed since the last :meth:`run` call."""
        return self._tick_count

    @property
    def last_status(self) -> NodeStatus | None:
        """The status returned by the most recent tick."""
        return self._last_status

    def stop(self) -> None:
        """Signal the runner to stop after the current tick."""
        self._running = False

    def _refresh_context(self) -> None:
        """Pull fresh observations from the robot into the context."""
        if self.context.robot is None:
            return
        try:
            obs = self.context.robot.get_observation()
            if "joint_positions" in obs:
                self.context.joint_states = obs
            for key, value in obs.items():
                if key.startswith("camera_"):
                    self.context.cameras[key] = value
        except Exception:
            logger.warning("Failed to refresh context from robot", exc_info=True)

    def run(self) -> NodeStatus:
        """Run the behavior tree until completion or interruption.

        Returns:
            The final :class:`NodeStatus` from the root node.
        """
        self._running = True
        self._tick_count = 0
        self._last_status = None
        period = 1.0 / self.frequency if self.frequency > 0 else 0.0

        original_handler = signal.getsignal(signal.SIGINT)

        def _sigint_handler(signum: int, frame: object) -> None:
            logger.info("Ctrl+C received — stopping behavior tree.")
            self.stop()

        signal.signal(signal.SIGINT, _sigint_handler)

        try:
            logger.info(
                "BehaviorTreeRunner started (root=%s, freq=%.1f Hz)",
                self.root.name,
                self.frequency,
            )
            while self._running:
                tick_start = time.monotonic()

                self._refresh_context()
                status = self.root.tick(self.context)
                self._last_status = status
                self._tick_count += 1

                if status.state in (NodeState.SUCCESS, NodeState.FAILURE):
                    logger.info(
                        "Tree finished: %s after %d ticks",
                        status.state.value,
                        self._tick_count,
                    )
                    return status

                elapsed = time.monotonic() - tick_start
                sleep_time = period - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            logger.info("Runner stopped after %d ticks", self._tick_count)
            return self._last_status or NodeStatus.failure()

        finally:
            signal.signal(signal.SIGINT, original_handler)
