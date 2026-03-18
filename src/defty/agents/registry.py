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
"""Node registry — maps node type names to their Python classes."""

from __future__ import annotations

import logging
from typing import Any

from defty.nodes.base import Node

logger = logging.getLogger(__name__)

__all__ = ["NodeRegistry"]


class NodeRegistry:
    """Registry mapping string names to Node subclasses.

    Built-in nodes are registered automatically on first access.
    """

    _instance: NodeRegistry | None = None

    def __init__(self) -> None:
        self._nodes: dict[str, type[Node]] = {}
        self._loaded = False

    @classmethod
    def default(cls) -> NodeRegistry:
        """Return the singleton default registry."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_builtins(self) -> None:
        """Auto-register all built-in node types."""
        if self._loaded:
            return
        from defty.nodes.control import ParallelNode, RepeatNode, SelectorNode, SequenceNode
        from defty.nodes.motion import GripperCloseNode, GripperOpenNode, JointControlNode, RelativeMoveNode
        from defty.nodes.perception import CameraCaptureNode
        from defty.nodes.policy import ACTPolicyNode
        from defty.nodes.utility import ConditionNode, WaitNode

        builtins: dict[str, type[Node]] = {
            "Sequence": SequenceNode, "Selector": SelectorNode,
            "Repeat": RepeatNode, "Parallel": ParallelNode,
            "CameraCapture": CameraCaptureNode,
            "JointControl": JointControlNode, "GripperOpen": GripperOpenNode,
            "GripperClose": GripperCloseNode, "RelativeMove": RelativeMoveNode,
            "ACTPolicy": ACTPolicyNode,
            "Wait": WaitNode, "Condition": ConditionNode,
        }
        for name, cls_type in builtins.items():
            self._nodes[name] = cls_type
        self._loaded = True
        logger.debug("Registered %d built-in nodes", len(builtins))

    def register(self, name: str, node_class: type[Node]) -> None:
        """Register a node class under the given name."""
        if not issubclass(node_class, Node):
            raise TypeError(f"{node_class} is not a Node subclass")
        self._nodes[name] = node_class

    def get(self, name: str) -> type[Node] | None:
        """Look up a node class by name."""
        self._load_builtins()
        return self._nodes.get(name)

    def list_nodes(self) -> dict[str, type[Node]]:
        """Return a copy of all registered node names and classes."""
        self._load_builtins()
        return dict(self._nodes)

    def __contains__(self, name: str) -> bool:
        self._load_builtins()
        return name in self._nodes

    def __len__(self) -> int:
        self._load_builtins()
        return len(self._nodes)
