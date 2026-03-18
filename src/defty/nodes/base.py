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
"""Core abstractions for the Defty behavior-tree node engine.

Defines the base :class:`Node` class, :class:`NodeStatus` result type,
:class:`Context` data container, and :class:`RobotInterface` ABC that
all leaf / control nodes and robot drivers build upon.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "Node",
    "NodeState",
    "NodeStatus",
    "Context",
    "RobotInterface",
]


class NodeState(Enum):
    """Possible states returned by a single node tick."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


@dataclass
class NodeStatus:
    """Result of a single :meth:`Node.tick` invocation.

    Attributes:
        state: The resulting state after the tick.
        output: Optional key-value data produced by the tick.
    """

    state: NodeState
    output: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, **output: Any) -> NodeStatus:
        """Create a SUCCESS status with optional output."""
        return cls(state=NodeState.SUCCESS, output=output)

    @classmethod
    def failure(cls, **output: Any) -> NodeStatus:
        """Create a FAILURE status with optional output."""
        return cls(state=NodeState.FAILURE, output=output)

    @classmethod
    def running(cls, **output: Any) -> NodeStatus:
        """Create a RUNNING status with optional output."""
        return cls(state=NodeState.RUNNING, output=output)


@dataclass
class Context:
    """Shared data container passed through the behavior tree on each tick.

    Attributes:
        cameras: Mapping of camera id to the latest captured frame (numpy array).
        joint_states: Current joint angles / positions from the robot.
        language: Optional natural-language instruction for LLM/VLA nodes.
        memory: Blackboard — short-term key/value store shared across nodes
                within a single run.
        robot: The connected :class:`RobotInterface` (or *None*).
    """

    cameras: dict[str, Any] = field(default_factory=dict)
    joint_states: dict[str, Any] = field(default_factory=dict)
    language: str = ""
    memory: dict[str, Any] = field(default_factory=dict)
    robot: RobotInterface | None = None


class Node(ABC):
    """Abstract base class for all behavior-tree nodes.

    Every node must implement :meth:`tick` which receives a :class:`Context`
    and returns a :class:`NodeStatus`.

    Attributes:
        name: Human-readable node name (defaults to the class name).
        children: Ordered list of child nodes (empty for leaf nodes).
    """

    def __init__(self, name: str | None = None, children: list[Node] | None = None) -> None:
        self.name: str = name or self.__class__.__name__
        self.children: list[Node] = children or []

    @abstractmethod
    def tick(self, context: Context) -> NodeStatus:
        """Execute one tick of this node.

        Args:
            context: Shared context for the current behavior-tree execution.

        Returns:
            A :class:`NodeStatus` indicating the result of this tick.
        """

    def reset(self) -> None:
        """Reset internal state so the node can be re-ticked from scratch."""
        for child in self.children:
            child.reset()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


class RobotInterface(ABC):
    """Abstract interface for connecting to and controlling a physical robot."""

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the robot hardware."""

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanly disconnect from the robot hardware."""

    @abstractmethod
    def get_observation(self) -> dict[str, Any]:
        """Read the latest sensor / joint observations.

        Returns:
            A dict with at least ``"joint_positions"`` and optionally camera
            frames keyed by camera id.
        """

    @abstractmethod
    def send_action(self, action: dict[str, Any]) -> None:
        """Send a motor command to the robot.

        Args:
            action: A dict with ``"joint_positions"`` (list/array of target
                    angles) and optionally ``"gripper"`` (float 0-1).
        """
