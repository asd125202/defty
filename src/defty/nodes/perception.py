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
        """Check that camera frames are available in the context.

        The engine pre-populates ``context.cameras`` via ``_refresh_context()``
        before each tick, so this node acts as a gate: it succeeds when at
        least one camera frame is present and fails otherwise.
        If ``context.cameras`` is empty (first tick or no robot), it falls back
        to reading directly from the robot.
        """
        if not context.cameras and context.robot is not None:
            # Fallback: populate cameras directly on first tick
            try:
                obs = context.robot.get_observation()
                for key, value in obs.items():
                    if key.startswith("observation.images."):
                        context.cameras[key] = value
            except Exception as exc:
                logger.error("Camera capture failed: %s", exc)
                return NodeStatus.failure(reason=str(exc))

        if not context.cameras:
            if context.robot is None:
                logger.warning("CameraCaptureNode: no robot connected")
                return NodeStatus.failure(reason="no_robot")
            logger.warning("CameraCaptureNode: no camera frames in context")
            return NodeStatus.failure(reason="no_camera_frames")

        logger.debug("CameraCaptureNode: %d camera frame(s) available", len(context.cameras))
        return NodeStatus.success()
