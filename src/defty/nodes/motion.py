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
"""Motion-control leaf nodes for the Defty behavior-tree engine."""

from __future__ import annotations

import logging
from typing import Any

from defty.nodes.base import Context, Node, NodeStatus

logger = logging.getLogger(__name__)

__all__ = ["JointControlNode", "GripperOpenNode", "GripperCloseNode", "RelativeMoveNode"]


class JointControlNode(Node):
    """Read target joint positions from the blackboard and send to the robot.

    The blackboard value at *source* must be either:
    - a list/array of motor-tick values in motor-bus order, or
    - a dict mapping ``"{motor_name}.pos"`` → int directly.
    """

    def __init__(self, source: str = "action", name: str | None = None) -> None:
        super().__init__(name=name)
        self.source = source

    def tick(self, context: Context) -> NodeStatus:
        """Send joint positions from memory to the robot."""
        if context.robot is None:
            logger.warning("JointControlNode: no robot connected")
            return NodeStatus.failure(reason="no_robot")
        target = context.memory.get(self.source)
        if target is None:
            logger.warning("JointControlNode: key %r not in memory", self.source)
            return NodeStatus.failure(reason=f"missing_key:{self.source}")
        try:
            # Accept either a plain dict (already .pos keys) or a list/array
            if isinstance(target, dict):
                context.robot.send_action(target)
            else:
                import numpy as np

                arr = np.asarray(target, dtype=np.float32)
                # Get motor names from latest observation for mapping
                obs = context.robot.get_observation()
                motor_names: list[str] = obs.get("_motor_names") or []
                if len(motor_names) == len(arr):
                    action = {
                        f"{name}.pos": int(round(float(v)))
                        for name, v in zip(motor_names, arr)
                    }
                    context.robot.send_action(action)
                else:
                    logger.warning(
                        "JointControlNode: cannot map %d values to %d motors",
                        len(arr),
                        len(motor_names),
                    )
                    return NodeStatus.failure(reason="motor_count_mismatch")
            return NodeStatus.success()
        except Exception as exc:
            logger.error("JointControlNode failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))


class GripperOpenNode(Node):
    """Open the gripper to a target motor position.

    Args:
        position: Target gripper motor position in raw ticks (0–4095 for
                  Feetech STS3215).  Default ``1500`` is a safe open position
                  for SO-101 — adjust to match your hardware calibration.
        name: Optional node name.
    """

    def __init__(self, position: int = 1500, name: str | None = None) -> None:
        super().__init__(name=name)
        self.position = position

    def tick(self, context: Context) -> NodeStatus:
        """Open the gripper."""
        if context.robot is None:
            return NodeStatus.failure(reason="no_robot")
        try:
            context.robot.send_action({"gripper.pos": self.position})
            return NodeStatus.success()
        except Exception as exc:
            logger.error("GripperOpenNode failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))


class GripperCloseNode(Node):
    """Close the gripper to a target motor position.

    Args:
        position: Target gripper motor position in raw ticks (0–4095 for
                  Feetech STS3215).  Default ``3500`` is a safe closed
                  position for SO-101 — adjust to match your hardware
                  calibration.
        name: Optional node name.
    """

    def __init__(self, position: int = 3500, name: str | None = None) -> None:
        super().__init__(name=name)
        self.position = position

    def tick(self, context: Context) -> NodeStatus:
        """Close the gripper."""
        if context.robot is None:
            return NodeStatus.failure(reason="no_robot")
        try:
            context.robot.send_action({"gripper.pos": self.position})
            return NodeStatus.success()
        except Exception as exc:
            logger.error("GripperCloseNode failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))


class RelativeMoveNode(Node):
    """Move the end-effector by a relative offset (dx, dy, dz)."""

    def __init__(self, source: str | None = None, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0, name: str | None = None) -> None:
        super().__init__(name=name)
        self.source = source
        self.dx = dx
        self.dy = dy
        self.dz = dz

    def tick(self, context: Context) -> NodeStatus:
        """Send a relative-move command to the robot."""
        if context.robot is None:
            return NodeStatus.failure(reason="no_robot")
        if self.source is not None:
            delta: dict[str, Any] = context.memory.get(self.source, {})
            dx = delta.get("dx", self.dx)
            dy = delta.get("dy", self.dy)
            dz = delta.get("dz", self.dz)
        else:
            dx, dy, dz = self.dx, self.dy, self.dz
        try:
            context.robot.send_action({"relative_move": {"dx": dx, "dy": dy, "dz": dz}})
            return NodeStatus.success()
        except Exception as exc:
            logger.error("RelativeMoveNode failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))
