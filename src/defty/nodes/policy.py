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
    """Run a trained ACT policy model to produce and send robot actions.

    On the first tick the model is loaded lazily from *model*.  Each tick
    reads an observation from the connected robot, runs one inference step,
    and immediately sends the resulting joint-position command back to the arm.

    Args:
        model: Path to the model directory (may contain a ``checkpoints/``
               sub-tree; the latest checkpoint is used automatically).
        output_key: Blackboard key where the raw action tensor is stored.
        name: Optional node name.
    """

    def __init__(self, model: str, output_key: str = "action", name: str | None = None) -> None:
        super().__init__(name=name or f"ACTPolicy({model})")
        self.model_path = model
        self.output_key = output_key
        self._policy: Any = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_model_dir(self) -> Path:
        """Return the ``pretrained_model`` directory for the latest checkpoint."""
        model_dir = Path(self.model_path)
        ckpt_root = model_dir / "checkpoints"
        if ckpt_root.exists():
            step_dirs = sorted(
                (d for d in ckpt_root.iterdir() if d.is_dir() and d.name.isdigit()),
                key=lambda d: int(d.name),
            )
            if step_dirs:
                pretrained = step_dirs[-1] / "pretrained_model"
                if pretrained.exists():
                    return pretrained
        return model_dir

    def _load_policy(self) -> None:
        """Lazily load the ACT policy from the model directory."""
        if self._policy is not None:
            return
        model_dir = self._resolve_model_dir()
        if not model_dir.exists():
            raise FileNotFoundError(f"Model not found: {model_dir}")
        try:
            import torch
            from lerobot.policies.act.modeling_act import ACTPolicy

            self._policy = ACTPolicy.from_pretrained(str(model_dir))
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._policy = self._policy.to(device)
            self._policy.eval()
            logger.info("Loaded ACT policy from %s on %s", model_dir, device)
        except ImportError as exc:
            raise RuntimeError(f"lerobot import failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Node tick
    # ------------------------------------------------------------------

    def tick(self, context: Context) -> NodeStatus:
        """Load policy (once), observe, infer, and send action to robot."""
        try:
            self._load_policy()
        except Exception as exc:
            logger.error("Failed to load policy: %s", exc)
            return NodeStatus.failure(reason=str(exc))

        if context.robot is None:
            return NodeStatus.failure(reason="no_robot")

        try:
            import numpy as np
            import torch

            obs = context.robot.get_observation()
            batch: dict[str, Any] = {}

            # --- joint state ---
            if "observation.state" in obs:
                state = np.asarray(obs["observation.state"], dtype=np.float32)
                batch["observation.state"] = torch.from_numpy(state).unsqueeze(0)

            # --- camera images ---
            for key, value in obs.items():
                if key.startswith("observation.images."):
                    img = np.asarray(value, dtype=np.float32) / 255.0
                    if img.ndim == 3:
                        img = img.transpose(2, 0, 1)  # HWC → CHW
                    batch[key] = torch.from_numpy(img).unsqueeze(0)  # [1, C, H, W]

            if not batch:
                logger.warning("ACTPolicyNode: observation is empty")
                return NodeStatus.failure(reason="empty_observation")

            # Move tensors to policy device
            device = next(self._policy.parameters()).device
            batch = {k: v.to(device) for k, v in batch.items()}

            # Run inference
            action: Any = self._policy.select_action(batch)  # Tensor [n_actions]
            action_np = action.detach().cpu().numpy()

            # Store in blackboard
            context.memory[self.output_key] = action_np

            # Send to robot: map values back to motor .pos keys
            motor_names: list[str] = obs.get("_motor_names") or []
            if motor_names and len(action_np) == len(motor_names):
                robot_action = {
                    f"{name}.pos": int(round(float(val)))
                    for name, val in zip(motor_names, action_np)
                }
                context.robot.send_action(robot_action)
            else:
                logger.warning(
                    "ACTPolicyNode: motor_names length %d != action length %d; "
                    "action not sent",
                    len(motor_names),
                    len(action_np),
                )

            return NodeStatus.success()

        except Exception as exc:
            logger.error("Policy inference failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))
