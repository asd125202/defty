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
"""AgentRef node — load another .defty agent as a sub-tree."""

from __future__ import annotations

import logging
from typing import Any

from defty.nodes.base import Context, Node, NodeStatus

logger = logging.getLogger(__name__)

__all__ = ["AgentRef"]


class AgentRef(Node):
    """Reference to another .defty agent, loaded as a sub-tree.

    Usage in .defty files::

        tree = Sequence(
            Agent("pick_bread"),
            Agent("place_bread"),
        )
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name=f"AgentRef({name})")
        self.agent_name = name
        self._loaded_tree: Node | None = None

    def _load_agent(self) -> Node:
        """Load and parse the referenced agent's .defty file."""
        if self._loaded_tree is not None:
            return self._loaded_tree
        from defty.agents.manager import AgentManager
        manager = AgentManager()
        agent_def = manager.load(self.agent_name)
        if agent_def is None:
            raise FileNotFoundError(f"Agent '{self.agent_name}' not found. Available agents: {', '.join(manager.list_names())}")
        self._loaded_tree = agent_def["tree"]
        self.children = [self._loaded_tree]
        logger.info("Loaded sub-agent: %s", self.agent_name)
        return self._loaded_tree

    def tick(self, context: Context) -> NodeStatus:
        """Tick the loaded sub-agent's behavior tree."""
        try:
            tree = self._load_agent()
        except Exception as exc:
            logger.error("Failed to load agent '%s': %s", self.agent_name, exc)
            return NodeStatus.failure(reason=str(exc))
        return tree.tick(context)

    def reset(self) -> None:
        """Reset the loaded sub-tree."""
        if self._loaded_tree is not None:
            self._loaded_tree.reset()
        super().reset()
