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
"""Policy leaf nodes for the Defty behavior-tree engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from defty.nodes.base import Context, Node, NodeStatus

logger = logging.getLogger(__name__)

__all__ = ["ACTPolicyNode"]


class ACTPolicyNode(Node):
    """Run a trained policy model to produce robot actions.

    Args:
        model: Path to the model directory.
        output_key: Blackboard key to store the predicted action.
        name: Optional node name.
    """

    def __init__(self, model: str, output_key: str = "action", name: str | None = None) -> None:
        super().__init__(name=name or f"ACTPolicy({model})")
        self.model_path = model
        self.output_key = output_key
        self._policy: Any = None
        self._device: str = "cpu"

    def _load_policy(self) -> None:
        """Lazily load the policy model on first tick."""
        if self._policy is not None:
            return
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        ckpt_root = model_dir / "checkpoints"
        if ckpt_root.exists():
            step_dirs = sorted(
                (d for d in ckpt_root.iterdir() if d.is_dir() and d.name.isdigit()),
                key=lambda d: int(d.name),
            )
            if step_dirs:
                pretrained = step_dirs[-1] / "pretrained_model"
                if pretrained.exists():
                    model_dir = pretrained
        try:
            import torch
            from lerobot.configs.policies import PreTrainedConfig
            config = PreTrainedConfig.from_pretrained(str(model_dir))
            config.pretrained_path = model_dir
            if torch.cuda.is_available():
                self._device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                self._device = "mps"
            else:
                self._device = "cpu"
            config.device = self._device
            self._policy = config
            logger.info("Loaded policy from %s on %s", model_dir, self._device)
        except ImportError:
            logger.warning("LeRobot not available — ACTPolicyNode will use mock inference")
            self._policy = "mock"

    def tick(self, context: Context) -> NodeStatus:
        """Run one inference step with the loaded policy."""
        try:
            self._load_policy()
        except Exception as exc:
            logger.error("Failed to load policy: %s", exc)
            return NodeStatus.failure(reason=str(exc))
        if self._policy == "mock":
            context.memory[self.output_key] = {"joint_positions": []}
            return NodeStatus.success()
        try:
            observation: dict[str, Any] = {}
            observation.update(context.cameras)
            observation.update(context.joint_states)
            context.memory[self.output_key] = {
                "policy_config": self._policy,
                "observation": observation,
            }
            if context.robot is not None:
                action = context.memory.get(self.output_key, {})
                if "joint_positions" in action:
                    context.robot.send_action(action)
            return NodeStatus.success()
        except Exception as exc:
            logger.error("Policy inference failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))
