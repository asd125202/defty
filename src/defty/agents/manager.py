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
"""Agent manager — CRUD operations for .defty agents."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AgentManager"]

_DEFAULT_AGENTS_DIR = Path.home() / ".defty" / "agents"
_DEFAULT_MODELS_DIR = Path.home() / ".defty" / "models"


class AgentManager:
    """Manage .defty agents: create, list, load, validate, and delete.

    Args:
        agents_dir: Base directory for agent storage. Defaults to ~/.defty/agents/.
    """

    def __init__(self, agents_dir: str | Path | None = None) -> None:
        self.agents_dir = Path(agents_dir) if agents_dir else _DEFAULT_AGENTS_DIR
        self.models_dir = _DEFAULT_MODELS_DIR

    def _ensure_dirs(self) -> None:
        """Create the agents and models directories if they don't exist."""
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def create(self, name: str, robot: str = "so101", template: str | None = None) -> Path:
        """Create a new agent from a template.

        Returns:
            Path to the created agent directory.
        """
        self._ensure_dirs()
        agent_dir = self.agents_dir / name
        if agent_dir.exists():
            raise FileExistsError(f"Agent '{name}' already exists at {agent_dir}")
        agent_dir.mkdir(parents=True)
        defty_file = agent_dir / f"{name}.defty"
        if template is None:
            template = _DEFAULT_TEMPLATE.format(name=name, robot=robot)
        defty_file.write_text(template, encoding="utf-8")
        logger.info("Created agent '%s' at %s", name, agent_dir)
        return agent_dir

    def load(self, name: str) -> dict[str, Any] | None:
        """Load and parse an agent by name."""
        agent_dir = self.agents_dir / name
        defty_file = agent_dir / f"{name}.defty"
        if not defty_file.exists():
            logger.warning("Agent '%s' not found at %s", name, defty_file)
            return None
        from defty.agents.parser import parse_defty_file
        return parse_defty_file(defty_file)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all available agents with metadata."""
        self._ensure_dirs()
        agents: list[dict[str, Any]] = []
        for agent_dir in sorted(self.agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            defty_file = agent_dir / f"{agent_dir.name}.defty"
            if not defty_file.exists():
                continue
            try:
                definition = self.load(agent_dir.name)
                if definition is None:
                    continue
                agents.append({
                    "name": definition.get("name", agent_dir.name),
                    "version": definition.get("version", "?"),
                    "robot": definition.get("robot", "?"),
                    "node_count": _count_nodes(definition.get("tree")),
                    "path": str(agent_dir),
                })
            except Exception as exc:
                logger.warning("Failed to load agent '%s': %s", agent_dir.name, exc)
                agents.append({
                    "name": agent_dir.name, "version": "?", "robot": "?",
                    "node_count": 0, "path": str(agent_dir), "error": str(exc),
                })
        return agents

    def list_names(self) -> list[str]:
        """Return a list of agent names."""
        self._ensure_dirs()
        return [d.name for d in sorted(self.agents_dir.iterdir()) if d.is_dir() and (d / f"{d.name}.defty").exists()]

    def info(self, name: str) -> dict[str, Any] | None:
        """Get detailed info about an agent."""
        definition = self.load(name)
        if definition is None:
            return None
        tree = definition.get("tree")
        return {
            "name": definition.get("name", name),
            "version": definition.get("version", "?"),
            "robot": definition.get("robot", "?"),
            "node_count": _count_nodes(tree),
            "tree_structure": _tree_to_string(tree) if tree else "empty",
            "dependencies": definition.get("dependencies", {}),
            "path": str(self.agents_dir / name),
        }

    def delete(self, name: str) -> bool:
        """Delete an agent by name."""
        agent_dir = self.agents_dir / name
        if not agent_dir.exists():
            return False
        shutil.rmtree(agent_dir)
        logger.info("Deleted agent '%s'", name)
        return True

    def validate(self, name: str) -> tuple[bool, str]:
        """Validate an agent's .defty file."""
        try:
            definition = self.load(name)
            if definition is None:
                return False, f"Agent '{name}' not found"
            return True, "Valid"
        except Exception as exc:
            return False, str(exc)


def _count_nodes(node: Any) -> int:
    """Count total nodes in a behavior tree."""
    if node is None:
        return 0
    from defty.nodes.base import Node
    if not isinstance(node, Node):
        return 0
    count = 1
    for child in node.children:
        count += _count_nodes(child)
    return count


def _tree_to_string(node: Any, indent: int = 0) -> str:
    """Convert a behavior tree to an indented string representation."""
    if node is None:
        return ""
    from defty.nodes.base import Node
    if not isinstance(node, Node):
        return ""
    prefix = "  " * indent
    lines = [f"{prefix}├─ {node.name}"]
    for child in node.children:
        lines.append(_tree_to_string(child, indent + 1))
    return "\n".join(lines)


_DEFAULT_TEMPLATE = '''# {name}.defty
name = "{name}"
version = "1.0"
robot = "{robot}"

tree = Sequence(
    CameraCapture(),
    Wait(seconds=1),
)
'''
