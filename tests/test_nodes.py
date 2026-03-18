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
"""Unit tests for the Defty node engine (Phase 1) and leaf nodes (Phase 2)."""

from __future__ import annotations

import time

import pytest

from defty.nodes.base import Context, Node, NodeState, NodeStatus, RobotInterface
from defty.nodes.control import ParallelNode, RepeatNode, SelectorNode, SequenceNode
from defty.nodes.engine import BehaviorTreeRunner
from defty.nodes.motion import GripperCloseNode, GripperOpenNode, JointControlNode, RelativeMoveNode
from defty.nodes.perception import CameraCaptureNode
from defty.nodes.policy import ACTPolicyNode
from defty.nodes.utility import ConditionNode, WaitNode


# ── Mock helpers ─────────────────────────────────────────────────────────────


class AlwaysSucceedNode(Node):
    """Test node that always returns SUCCESS."""

    def tick(self, context: Context) -> NodeStatus:
        return NodeStatus.success()


class AlwaysFailNode(Node):
    """Test node that always returns FAILURE."""

    def tick(self, context: Context) -> NodeStatus:
        return NodeStatus.failure()


class CounterNode(Node):
    """Test node that succeeds after N ticks (returns RUNNING until then)."""

    def __init__(self, n: int = 3, name: str | None = None) -> None:
        super().__init__(name=name)
        self.n = n
        self.count = 0

    def tick(self, context: Context) -> NodeStatus:
        self.count += 1
        if self.count >= self.n:
            return NodeStatus.success()
        return NodeStatus.running()

    def reset(self) -> None:
        self.count = 0
        super().reset()


class MemoryWriterNode(Node):
    """Test node that writes a value to the blackboard."""

    def __init__(self, key: str, value: object, name: str | None = None) -> None:
        super().__init__(name=name)
        self.key = key
        self.value = value

    def tick(self, context: Context) -> NodeStatus:
        context.memory[self.key] = self.value
        return NodeStatus.success()


class MockRobot(RobotInterface):
    """Mock robot for testing."""

    def __init__(self) -> None:
        self.connected = False
        self.actions: list[dict] = []
        self.observations = {
            "joint_positions": [0.0] * 6,
            "camera_wrist": "mock_frame",
        }

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def get_observation(self) -> dict:
        return dict(self.observations)

    def send_action(self, action: dict) -> None:
        self.actions.append(action)


# ── Phase 1: NodeStatus ─────────────────────────────────────────────────────


class TestNodeStatus:
    """Tests for NodeStatus dataclass."""

    def test_success_factory(self) -> None:
        s = NodeStatus.success(val=42)
        assert s.state == NodeState.SUCCESS
        assert s.output == {"val": 42}

    def test_failure_factory(self) -> None:
        s = NodeStatus.failure(reason="oops")
        assert s.state == NodeState.FAILURE
        assert s.output == {"reason": "oops"}

    def test_running_factory(self) -> None:
        s = NodeStatus.running()
        assert s.state == NodeState.RUNNING
        assert s.output == {}


# ── Phase 1: Context ────────────────────────────────────────────────────────


class TestContext:
    """Tests for Context dataclass."""

    def test_default_values(self) -> None:
        ctx = Context()
        assert ctx.cameras == {}
        assert ctx.joint_states == {}
        assert ctx.memory == {}
        assert ctx.robot is None
        assert ctx.language == ""

    def test_blackboard_sharing(self) -> None:
        ctx = Context()
        ctx.memory["key"] = "value"
        assert ctx.memory["key"] == "value"


# ── Phase 1: SequenceNode ───────────────────────────────────────────────────


class TestSequenceNode:
    """Tests for SequenceNode."""

    def test_all_succeed(self) -> None:
        seq = SequenceNode(children=[AlwaysSucceedNode(), AlwaysSucceedNode()])
        result = seq.tick(Context())
        assert result.state == NodeState.SUCCESS

    def test_first_fails(self) -> None:
        seq = SequenceNode(children=[AlwaysFailNode(), AlwaysSucceedNode()])
        result = seq.tick(Context())
        assert result.state == NodeState.FAILURE

    def test_running_resumes(self) -> None:
        counter = CounterNode(n=2)
        seq = SequenceNode(children=[counter, AlwaysSucceedNode()])
        ctx = Context()

        r1 = seq.tick(ctx)
        assert r1.state == NodeState.RUNNING
        assert counter.count == 1

        r2 = seq.tick(ctx)
        assert r2.state == NodeState.SUCCESS
        assert counter.count == 2

    def test_empty_sequence(self) -> None:
        seq = SequenceNode(children=[])
        result = seq.tick(Context())
        assert result.state == NodeState.SUCCESS


# ── Phase 1: SelectorNode ───────────────────────────────────────────────────


class TestSelectorNode:
    """Tests for SelectorNode."""

    def test_first_succeeds(self) -> None:
        sel = SelectorNode(children=[AlwaysSucceedNode(), AlwaysFailNode()])
        result = sel.tick(Context())
        assert result.state == NodeState.SUCCESS

    def test_all_fail(self) -> None:
        sel = SelectorNode(children=[AlwaysFailNode(), AlwaysFailNode()])
        result = sel.tick(Context())
        assert result.state == NodeState.FAILURE

    def test_fallback(self) -> None:
        sel = SelectorNode(children=[AlwaysFailNode(), AlwaysSucceedNode()])
        result = sel.tick(Context())
        assert result.state == NodeState.SUCCESS

    def test_empty_selector(self) -> None:
        sel = SelectorNode(children=[])
        result = sel.tick(Context())
        assert result.state == NodeState.FAILURE


# ── Phase 1: RepeatNode ─────────────────────────────────────────────────────


class TestRepeatNode:
    """Tests for RepeatNode."""

    def test_repeat_n_times(self) -> None:
        child = AlwaysSucceedNode()
        repeat = RepeatNode(child=child, times=3)
        ctx = Context()

        assert repeat.tick(ctx).state == NodeState.RUNNING  # 1st
        assert repeat.tick(ctx).state == NodeState.RUNNING  # 2nd
        assert repeat.tick(ctx).state == NodeState.SUCCESS   # 3rd

    def test_repeat_until(self) -> None:
        child = MemoryWriterNode("counter", 0)
        counter = [0]

        def until_fn(ctx: Context) -> bool:
            counter[0] += 1
            return counter[0] >= 2

        repeat = RepeatNode(child=child, times=-1, until=until_fn)
        ctx = Context()

        assert repeat.tick(ctx).state == NodeState.RUNNING  # until returns False
        assert repeat.tick(ctx).state == NodeState.SUCCESS   # until returns True

    def test_child_failure_stops_repeat(self) -> None:
        repeat = RepeatNode(child=AlwaysFailNode(), times=10)
        result = repeat.tick(Context())
        assert result.state == NodeState.FAILURE


# ── Phase 1: ParallelNode ───────────────────────────────────────────────────


class TestParallelNode:
    """Tests for ParallelNode."""

    def test_wait_all_success(self) -> None:
        par = ParallelNode(
            children=[AlwaysSucceedNode(), AlwaysSucceedNode()],
            policy="wait_all",
        )
        result = par.tick(Context())
        assert result.state == NodeState.SUCCESS

    def test_wait_all_one_fails(self) -> None:
        par = ParallelNode(
            children=[AlwaysSucceedNode(), AlwaysFailNode()],
            policy="wait_all",
        )
        result = par.tick(Context())
        assert result.state == NodeState.FAILURE

    def test_wait_any_one_succeeds(self) -> None:
        par = ParallelNode(
            children=[AlwaysFailNode(), AlwaysSucceedNode()],
            policy="wait_any",
        )
        result = par.tick(Context())
        assert result.state == NodeState.SUCCESS

    def test_wait_any_all_fail(self) -> None:
        par = ParallelNode(
            children=[AlwaysFailNode(), AlwaysFailNode()],
            policy="wait_any",
        )
        result = par.tick(Context())
        assert result.state == NodeState.FAILURE

    def test_invalid_policy(self) -> None:
        with pytest.raises(ValueError, match="policy"):
            ParallelNode(children=[], policy="invalid")

    def test_empty_parallel(self) -> None:
        par = ParallelNode(children=[], policy="wait_all")
        result = par.tick(Context())
        assert result.state == NodeState.SUCCESS


# ── Phase 1: BehaviorTreeRunner ─────────────────────────────────────────────


class TestBehaviorTreeRunner:
    """Tests for BehaviorTreeRunner."""

    def test_run_simple_success(self) -> None:
        runner = BehaviorTreeRunner(AlwaysSucceedNode(), Context())
        result = runner.run()
        assert result.state == NodeState.SUCCESS
        assert runner.tick_count == 1

    def test_run_simple_failure(self) -> None:
        runner = BehaviorTreeRunner(AlwaysFailNode(), Context())
        result = runner.run()
        assert result.state == NodeState.FAILURE

    def test_run_multi_tick(self) -> None:
        counter = CounterNode(n=3)
        runner = BehaviorTreeRunner(counter, Context(), frequency=1000)
        result = runner.run()
        assert result.state == NodeState.SUCCESS
        assert runner.tick_count == 3

    def test_run_with_robot(self) -> None:
        robot = MockRobot()
        robot.connect()
        ctx = Context(robot=robot)
        runner = BehaviorTreeRunner(AlwaysSucceedNode(), ctx)
        result = runner.run()
        assert result.state == NodeState.SUCCESS

    def test_stop(self) -> None:
        counter = CounterNode(n=1000)
        runner = BehaviorTreeRunner(counter, Context(), frequency=1000)

        import threading

        def stop_after():
            time.sleep(0.05)
            runner.stop()

        t = threading.Thread(target=stop_after)
        t.start()
        runner.run()
        t.join()
        assert runner.tick_count < 1000


# ── Phase 2: CameraCaptureNode ──────────────────────────────────────────────


class TestCameraCaptureNode:
    """Tests for CameraCaptureNode."""

    def test_no_robot(self) -> None:
        node = CameraCaptureNode()
        result = node.tick(Context())
        assert result.state == NodeState.FAILURE

    def test_captures_camera_data(self) -> None:
        robot = MockRobot()
        ctx = Context(robot=robot)
        node = CameraCaptureNode()
        result = node.tick(ctx)
        assert result.state == NodeState.SUCCESS
        assert "camera_wrist" in ctx.cameras


# ── Phase 2: JointControlNode ───────────────────────────────────────────────


class TestJointControlNode:
    """Tests for JointControlNode."""

    def test_no_robot(self) -> None:
        node = JointControlNode()
        result = node.tick(Context())
        assert result.state == NodeState.FAILURE

    def test_missing_key(self) -> None:
        robot = MockRobot()
        ctx = Context(robot=robot)
        node = JointControlNode(source="missing")
        result = node.tick(ctx)
        assert result.state == NodeState.FAILURE

    def test_sends_action(self) -> None:
        robot = MockRobot()
        target = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        ctx = Context(robot=robot, memory={"joint_target": target})
        node = JointControlNode(source="joint_target")
        result = node.tick(ctx)
        assert result.state == NodeState.SUCCESS
        assert len(robot.actions) == 1
        assert robot.actions[0]["joint_positions"] == target


# ── Phase 2: GripperNodes ───────────────────────────────────────────────────


class TestGripperNodes:
    """Tests for GripperOpenNode and GripperCloseNode."""

    def test_gripper_open(self) -> None:
        robot = MockRobot()
        ctx = Context(robot=robot)
        result = GripperOpenNode().tick(ctx)
        assert result.state == NodeState.SUCCESS
        assert robot.actions[-1]["gripper"] == 1.0

    def test_gripper_close(self) -> None:
        robot = MockRobot()
        ctx = Context(robot=robot)
        result = GripperCloseNode().tick(ctx)
        assert result.state == NodeState.SUCCESS
        assert robot.actions[-1]["gripper"] == 0.0

    def test_no_robot(self) -> None:
        assert GripperOpenNode().tick(Context()).state == NodeState.FAILURE
        assert GripperCloseNode().tick(Context()).state == NodeState.FAILURE


# ── Phase 2: RelativeMoveNode ───────────────────────────────────────────────


class TestRelativeMoveNode:
    """Tests for RelativeMoveNode."""

    def test_direct_values(self) -> None:
        robot = MockRobot()
        ctx = Context(robot=robot)
        node = RelativeMoveNode(dx=0.1, dy=0.2, dz=0.3)
        result = node.tick(ctx)
        assert result.state == NodeState.SUCCESS
        assert robot.actions[-1]["relative_move"] == {"dx": 0.1, "dy": 0.2, "dz": 0.3}

    def test_from_blackboard(self) -> None:
        robot = MockRobot()
        ctx = Context(robot=robot, memory={"delta": {"dx": 0.5, "dy": -0.1, "dz": 0.0}})
        node = RelativeMoveNode(source="delta")
        result = node.tick(ctx)
        assert result.state == NodeState.SUCCESS


# ── Phase 2: WaitNode ───────────────────────────────────────────────────────


class TestWaitNode:
    """Tests for WaitNode."""

    def test_returns_running_then_success(self) -> None:
        node = WaitNode(seconds=0.05)
        ctx = Context()
        r1 = node.tick(ctx)
        assert r1.state == NodeState.RUNNING

        time.sleep(0.06)
        r2 = node.tick(ctx)
        assert r2.state == NodeState.SUCCESS

    def test_reset(self) -> None:
        node = WaitNode(seconds=0.01)
        ctx = Context()
        node.tick(ctx)
        time.sleep(0.02)
        node.tick(ctx)  # SUCCESS
        node.reset()
        r = node.tick(ctx)
        assert r.state == NodeState.RUNNING  # Timer restarted


# ── Phase 2: ConditionNode ──────────────────────────────────────────────────


class TestConditionNode:
    """Tests for ConditionNode."""

    def test_key_exists(self) -> None:
        ctx = Context(memory={"flag": True})
        node = ConditionNode(key="flag")
        assert node.tick(ctx).state == NodeState.SUCCESS

    def test_key_missing(self) -> None:
        ctx = Context()
        node = ConditionNode(key="flag")
        assert node.tick(ctx).state == NodeState.FAILURE

    def test_value_match(self) -> None:
        ctx = Context(memory={"count": 5})
        node = ConditionNode(key="count", value=5)
        assert node.tick(ctx).state == NodeState.SUCCESS

    def test_value_mismatch(self) -> None:
        ctx = Context(memory={"count": 3})
        node = ConditionNode(key="count", value=5)
        assert node.tick(ctx).state == NodeState.FAILURE

    def test_predicate(self) -> None:
        ctx = Context(memory={"count": 10})
        node = ConditionNode(key="count", predicate=lambda x: x > 5)
        assert node.tick(ctx).state == NodeState.SUCCESS


# ── Phase 2: Integration ────────────────────────────────────────────────────


class TestIntegration:
    """End-to-end integration tests combining nodes."""

    def test_sequence_capture_control(self) -> None:
        """Sequence(CameraCapture → JointControl) with mock robot."""
        robot = MockRobot()
        ctx = Context(robot=robot, memory={"joint_target": [1.0] * 6})
        tree = SequenceNode(children=[
            CameraCaptureNode(),
            JointControlNode(source="joint_target"),
        ])
        result = tree.tick(ctx)
        assert result.state == NodeState.SUCCESS
        assert "camera_wrist" in ctx.cameras
        assert len(robot.actions) == 1

    def test_runner_with_sequence(self) -> None:
        """Runner with a multi-node sequence."""
        robot = MockRobot()
        ctx = Context(robot=robot, memory={"joint_target": [0.0] * 6})
        tree = SequenceNode(children=[
            CameraCaptureNode(),
            JointControlNode(source="joint_target"),
            GripperCloseNode(),
        ])
        runner = BehaviorTreeRunner(tree, ctx, frequency=100)
        result = runner.run()
        assert result.state == NodeState.SUCCESS
        assert runner.tick_count == 1

    def test_selector_fallback(self) -> None:
        """Selector falls back to second child when first fails."""
        ctx = Context()
        tree = SelectorNode(children=[
            AlwaysFailNode(),
            AlwaysSucceedNode(),
        ])
        result = tree.tick(ctx)
        assert result.state == NodeState.SUCCESS

    def test_repeat_with_wait(self) -> None:
        """Repeat with a WaitNode completes after enough ticks."""
        wait = WaitNode(seconds=0.01)
        repeat = RepeatNode(child=wait, times=2)
        ctx = Context()
        runner = BehaviorTreeRunner(repeat, ctx, frequency=1000)
        result = runner.run()
        assert result.state == NodeState.SUCCESS
