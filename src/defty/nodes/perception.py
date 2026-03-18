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
"""Perception leaf nodes for the Defty behavior-tree engine."""

from __future__ import annotations

import logging

from defty.nodes.base import Context, Node, NodeStatus

logger = logging.getLogger(__name__)

__all__ = ["CameraCaptureNode"]


class CameraCaptureNode(Node):
    """Read the latest frame from all cameras into ``context.cameras``."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name)

    def tick(self, context: Context) -> NodeStatus:
        """Capture frames from all cameras into ``context.cameras``."""
        if context.robot is None:
            logger.warning("CameraCaptureNode: no robot connected")
            return NodeStatus.failure(reason="no_robot")
        try:
            obs = context.robot.get_observation()
            frames_captured = 0
            for key, value in obs.items():
                if key.startswith("observation.images."):
                    context.cameras[key] = value
                    frames_captured += 1
            if frames_captured == 0:
                logger.warning("CameraCaptureNode: no camera frames in observation")
                return NodeStatus.failure(reason="no_camera_frames")
            logger.debug("Captured %d camera frame(s)", frames_captured)
            return NodeStatus.success()
        except Exception as exc:
            logger.error("Camera capture failed: %s", exc)
            return NodeStatus.failure(reason=str(exc))
