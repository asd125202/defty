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
"""Unit tests for the Defty agent system (Phase 3)."""

from __future__ import annotations

import pytest

from defty.agents.manager import AgentManager
from defty.agents.parser import DeftyParseError, parse_defty_source
from defty.agents.registry import NodeRegistry
from defty.nodes.base import Node, NodeState


# ── Registry ─────────────────────────────────────────────────────────────────


class TestNodeRegistry:
    """Tests for NodeRegistry."""

    def test_builtins_loaded(self) -> None:
        registry = NodeRegistry()
        registry._load_builtins()
        assert "Sequence" in registry
        assert "Selector" in registry
        assert "Repeat" in registry
        assert "Parallel" in registry
        assert "CameraCapture" in registry
        assert "JointControl" in registry
        assert "GripperOpen" in registry
        assert "GripperClose" in registry
        assert "ACTPolicy" in registry
        assert "Wait" in registry
        assert "Condition" in registry

    def test_register_custom(self) -> None:
        from defty.nodes.base import Context, NodeStatus

        class MyNode(Node):
            def tick(self, context: Context) -> NodeStatus:
                return NodeStatus.success()

        registry = NodeRegistry()
        registry.register("MyNode", MyNode)
        assert registry.get("MyNode") is MyNode

    def test_register_non_node_raises(self) -> None:
        registry = NodeRegistry()
        with pytest.raises(TypeError):
            registry.register("Bad", str)  # type: ignore[arg-type]

    def test_list_nodes(self) -> None:
        registry = NodeRegistry()
        nodes = registry.list_nodes()
        assert len(nodes) >= 11

    def test_len(self) -> None:
        registry = NodeRegistry()
        assert len(registry) >= 11


# ── Parser ───────────────────────────────────────────────────────────────────


class TestDeftyParser:
    """Tests for the .defty file parser."""

    def test_simple_sequence(self) -> None:
        source = '''
name = "test_agent"
version = "1.0"
robot = "so101"
tree = Sequence(
    Wait(seconds=1),
    Wait(seconds=2),
)
'''
        result = parse_defty_source(source)
        assert result["name"] == "test_agent"
        assert result["version"] == "1.0"
        assert result["robot"] == "so101"
        assert isinstance(result["tree"], Node)

    def test_nested_tree(self) -> None:
        source = '''
name = "nested"
version = "1.0"
robot = "so101"
tree = Repeat(
    child=Sequence(
        Wait(seconds=1),
        GripperClose(),
    ),
    times=3,
)
'''
        result = parse_defty_source(source)
        assert isinstance(result["tree"], Node)
        assert result["tree"].children

    def test_selector_node(self) -> None:
        source = '''
name = "sel_test"
version = "1.0"
robot = "so101"
tree = Selector(
    children=[
        Condition(key="found", value=True),
        Wait(seconds=1),
    ]
)
'''
        result = parse_defty_source(source)
        assert isinstance(result["tree"], Node)

    def test_infinite_repeat(self) -> None:
        source = '''
name = "loop"
version = "1.0"
robot = "so101"
tree = Repeat(
    times=-1,
    child=Wait(seconds=1),
)
'''
        result = parse_defty_source(source)
        assert isinstance(result["tree"], Node)

    def test_bread_loop_style(self) -> None:
        """Test the bread_loop.defty example from PLAN.md."""
        source = '''
name = "bread_loop"
version = "1.0"
robot = "so101"
tree = Repeat(
    times=-1,
    child=Sequence(
        ACTPolicy("models/act_bread_pick"),
        Wait(seconds=2),
        ACTPolicy("models/act_bread_place"),
        Wait(seconds=2),
    ),
)
'''
        result = parse_defty_source(source)
        assert result["name"] == "bread_loop"
        tree = result["tree"]
        assert isinstance(tree, Node)

    def test_missing_name_raises(self) -> None:
        source = '''
version = "1.0"
robot = "so101"
tree = Wait(seconds=1)
'''
        with pytest.raises(DeftyParseError, match="missing required field 'name'"):
            parse_defty_source(source)

    def test_missing_tree_raises(self) -> None:
        source = '''
name = "no_tree"
version = "1.0"
robot = "so101"
'''
        with pytest.raises(DeftyParseError, match="missing required field 'tree'"):
            parse_defty_source(source)

    def test_import_rejected(self) -> None:
        source = '''
import os
name = "bad"
version = "1.0"
robot = "so101"
tree = Wait(seconds=1)
'''
        with pytest.raises(DeftyParseError, match="import"):
            parse_defty_source(source)

    def test_function_def_rejected(self) -> None:
        source = '''
def hack():
    pass
name = "bad"
version = "1.0"
robot = "so101"
tree = Wait(seconds=1)
'''
        with pytest.raises(DeftyParseError, match="function"):
            parse_defty_source(source)

    def test_class_def_rejected(self) -> None:
        source = '''
class Evil:
    pass
name = "bad"
version = "1.0"
robot = "so101"
tree = Wait(seconds=1)
'''
        with pytest.raises(DeftyParseError, match="class"):
            parse_defty_source(source)

    def test_unknown_name_rejected(self) -> None:
        source = '''
name = "bad"
version = "1.0"
robot = "so101"
tree = UnknownNode()
'''
        with pytest.raises(DeftyParseError, match="unknown name"):
            parse_defty_source(source)

    def test_attribute_access_rejected(self) -> None:
        source = '''
name = "bad"
version = "1.0"
robot = "so101"
tree = os.system("rm -rf /")
'''
        with pytest.raises(DeftyParseError):
            parse_defty_source(source)

    def test_negative_numbers(self) -> None:
        source = '''
name = "neg"
version = "1.0"
robot = "so101"
tree = Repeat(times=-1, child=Wait(seconds=1))
'''
        result = parse_defty_source(source)
        assert isinstance(result["tree"], Node)

    def test_string_docstrings_allowed(self) -> None:
        source = '''
"This is a docstring comment"
name = "doc"
version = "1.0"
robot = "so101"
tree = Wait(seconds=1)
'''
        result = parse_defty_source(source)
        assert result["name"] == "doc"


# ── AgentManager ─────────────────────────────────────────────────────────────


class TestAgentManager:
    """Tests for AgentManager."""

    def test_create_agent(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        agent_dir = manager.create("test_agent")
        assert agent_dir.exists()
        assert (agent_dir / "test_agent.defty").exists()

    def test_create_duplicate_raises(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("test_agent")
        with pytest.raises(FileExistsError):
            manager.create("test_agent")

    def test_list_agents(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("agent_a")
        manager.create("agent_b")
        agents = manager.list_agents()
        names = [a["name"] for a in agents]
        assert "agent_a" in names
        assert "agent_b" in names

    def test_list_empty(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager._ensure_dirs()
        assert manager.list_agents() == []

    def test_load_agent(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("my_agent")
        definition = manager.load("my_agent")
        assert definition is not None
        assert definition["name"] == "my_agent"
        assert isinstance(definition["tree"], Node)

    def test_load_nonexistent(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager._ensure_dirs()
        assert manager.load("nonexistent") is None

    def test_info(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("info_test")
        info = manager.info("info_test")
        assert info is not None
        assert info["name"] == "info_test"
        assert info["node_count"] > 0

    def test_delete(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("del_me")
        assert manager.delete("del_me")
        assert not manager.delete("del_me")

    def test_validate_valid(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("valid_agent")
        is_valid, msg = manager.validate("valid_agent")
        assert is_valid

    def test_validate_invalid(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        agent_dir = tmp_path / "agents" / "bad_agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "bad_agent.defty").write_text("import os\n", encoding="utf-8")
        is_valid, msg = manager.validate("bad_agent")
        assert not is_valid

    def test_list_names(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("alpha")
        manager.create("beta")
        names = manager.list_names()
        assert "alpha" in names
        assert "beta" in names

    def test_create_custom_template(self, tmp_path) -> None:
        manager = AgentManager(agents_dir=tmp_path / "agents")
        template = '''name = "custom"
version = "2.0"
robot = "so101"
tree = Sequence(
    GripperOpen(),
    Wait(seconds=3),
    GripperClose(),
)
'''
        agent_dir = manager.create("custom", template=template)
        definition = manager.load("custom")
        assert definition is not None
        assert definition["name"] == "custom"
        assert definition["version"] == "2.0"


# ── AgentRef ─────────────────────────────────────────────────────────────────


class TestAgentRef:
    """Tests for AgentRef node."""

    def test_agent_ref_loads_subtree(self, tmp_path) -> None:
        from defty.agents.ref import AgentRef
        from defty.nodes.base import Context

        manager = AgentManager(agents_dir=tmp_path / "agents")
        manager.create("sub_agent")

        ref = AgentRef("sub_agent")
        original_default = AgentManager.__init__.__defaults__
        try:
            AgentManager.__init__.__defaults__ = (str(tmp_path / "agents"),)
            result = ref.tick(Context())
            assert result.state in (NodeState.SUCCESS, NodeState.FAILURE)
        finally:
            AgentManager.__init__.__defaults__ = original_default

    def test_agent_ref_nonexistent(self) -> None:
        from defty.agents.ref import AgentRef
        from defty.nodes.base import Context

        ref = AgentRef("nonexistent_agent_xyz")
        result = ref.tick(Context())
        assert result.state == NodeState.FAILURE
