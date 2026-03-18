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
    reads the pre-populated observation from the context, runs one inference
    step through the full lerobot pre/post-processor pipeline (normalize →
    model → unnormalize), and sends the resulting joint-position command to
    the arm.

    Args:
        model: Path to the model directory (may contain a ``checkpoints/``
               sub-tree; the latest checkpoint is used automatically).
        output_key: Blackboard key where the raw action array is stored.
        name: Optional node name.
    """

    def __init__(self, model: str, output_key: str = "action", name: str | None = None) -> None:
        super().__init__(name=name or f"ACTPolicy({model})")
        self.model_path = model
        self.output_key = output_key
        self._policy: Any = None
        self._preprocessor: Any = None
        self._postprocessor: Any = None
        self._device: Any = None

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
        """Lazily load the ACT policy and its pre/post-processor pipelines."""
        if self._policy is not None:
            return
        model_dir = self._resolve_model_dir()
        if not model_dir.exists():
            raise FileNotFoundError(f"Model not found: {model_dir}")
        try:
            import torch
            from lerobot.policies.act.modeling_act import ACTPolicy
            from lerobot.policies.factory import make_pre_post_processors

            device_str = "cuda" if torch.cuda.is_available() else "cpu"
            self._device = torch.device(device_str)

            self._policy = ACTPolicy.from_pretrained(str(model_dir))
            self._policy = self._policy.to(self._device)
            self._policy.eval()

            # Pre-processor: normalizes inputs (observation.state + images).
            # Post-processor: unnormalizes the raw model output back to degree units.
            # Both are saved alongside the model weights in policy_preprocessor.json /
            # policy_postprocessor.json + matching .safetensors stat files.
            self._preprocessor, self._postprocessor = make_pre_post_processors(
                self._policy.config, pretrained_path=str(model_dir)
            )
            logger.info("Loaded ACT policy from %s on %s", model_dir, device_str)
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

            # Build observation dict as numpy arrays — lerobot's predict_action /
            # prepare_observation_for_inference expects numpy (not tensors).
            obs: dict[str, Any] = {}

            state = context.joint_states.get("observation.state")
            if state is not None:
                obs["observation.state"] = np.asarray(state, dtype=np.float32)

            for key, value in context.cameras.items():
                if key.startswith("observation.images."):
                    # Keep as uint8 HWC — prepare_observation_for_inference
                    # handles CHW conversion and /255 normalisation internally.
                    obs[key] = np.asarray(value)

            if not obs:
                logger.warning("ACTPolicyNode: context has no observation data")
                return NodeStatus.failure(reason="empty_observation")

            # Full inference pipeline: normalize → forward → unnormalize.
            # This replicates exactly what lerobot's predict_action() does so
            # that action values are in the same units as the training data
            # (degrees for SO-101 with use_degrees=True).
            from lerobot.utils.control_utils import predict_action

            action = predict_action(
                observation=obs,
                policy=self._policy,
                device=self._device,
                preprocessor=self._preprocessor,
                postprocessor=self._postprocessor,
                use_amp=False,
            )

            # action shape: [1, n_motors] — squeeze batch dim
            action_np = action.squeeze(0).cpu().numpy()

            # Store in blackboard
            context.memory[self.output_key] = action_np

            # Map to {motor_name.pos: float} and send to robot.
            motor_names: list[str] = context.joint_states.get("_motor_names") or []
            if motor_names and len(action_np) == len(motor_names):
                robot_action = {f"{name}.pos": float(val) for name, val in zip(motor_names, action_np)}
                context.robot.send_action(robot_action)
            else:
                logger.warning(
                    "ACTPolicyNode: motor_names length %d != action length %d; action not sent",
                    len(motor_names),
                    len(action_np),
                )

            return NodeStatus.success()

        except Exception as exc:
            logger.error("Policy inference failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))
