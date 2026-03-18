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
#
# Portions of this file are derived from LeRobot by HuggingFace Inc.
# (https://github.com/huggingface/lerobot), used under the Apache License 2.0.
# Original copyright: Copyright 2024 The HuggingFace Inc. team.
"""LeRobot SO-101 robot interface for the Defty behavior-tree engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from defty.nodes.base import RobotInterface

logger = logging.getLogger(__name__)

__all__ = ["LeRobotSO101Interface"]


class LeRobotSO101Interface(RobotInterface):
    """Connect to and control a SO-101 robot arm via LeRobot.

    Args:
        port: Serial port for the follower arm.
        arm_id: Identifier for the arm (default "so101_follower_1").
        calibration_dir: Path to the calibration directory.
        cameras: Mapping of camera id to camera config dict.
    """

    def __init__(
        self,
        port: str,
        arm_id: str = "so101_follower_1",
        calibration_dir: str | Path = "calibration",
        cameras: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.port = port
        self.arm_id = arm_id
        self.calibration_dir = Path(calibration_dir)
        self.cameras_config = cameras or {}
        self._robot: Any = None

    def connect(self) -> None:
        """Establish a connection to the SO-101 robot arm."""
        try:
            from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
            from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig
        except ImportError as exc:
            raise RuntimeError(f"LeRobot import failed: {exc}") from exc
        camera_configs: dict[str, Any] = {}
        for cam_id, cam in self.cameras_config.items():
            device = cam.get("device", "0")
            idx = int(device) if str(device).isdigit() else device
            # Use default backend (CAP_ANY) — consistent with recorder.py
            camera_configs[cam_id] = OpenCVCameraConfig(
                index_or_path=idx,
                width=cam.get("width", 640),
                height=cam.get("height", 480),
                fps=cam.get("fps", 30),
            )
        config = SOFollowerRobotConfig(
            port=self.port,
            id=self.arm_id,
            calibration_dir=self.calibration_dir,
            cameras=camera_configs,
        )
        self._robot = SOFollower(config)
        self._robot.connect()
        logger.info("Connected to SO-101 on %s", self.port)

    def disconnect(self) -> None:
        """Disconnect from the SO-101 robot arm."""
        if self._robot is not None:
            try:
                self._robot.disconnect()
            except Exception:
                logger.warning("Error disconnecting SO-101", exc_info=True)
            self._robot = None
            logger.info("Disconnected from SO-101")

    def get_observation(self) -> dict[str, Any]:
        """Read joint positions and camera frames from the robot.

        Returns a dict with standardised keys:
        - ``"observation.state"``: float32 numpy array ``[n_motors]`` in motor
          tick order (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex,
          wrist_roll, gripper for SO-101).
        - ``"observation.images.{cam_id}"``: uint8 numpy array ``[H, W, C]``
          for each configured camera.
        - ``"_motor_names"``: list of motor name strings in state order.
        """
        if self._robot is None:
            raise RuntimeError("Robot not connected. Call connect() first.")
        import numpy as np

        raw = self._robot.get_observation()
        result: dict[str, Any] = {}

        # Motor positions: lerobot keys end with ".pos" (e.g. "shoulder_pan.pos").
        # Preserve insertion order — lerobot keeps motors in bus-registration order.
        motor_items = [(k, v) for k, v in raw.items() if k.endswith(".pos")]
        if motor_items:
            motor_names = [k.removesuffix(".pos") for k, _ in motor_items]
            result["observation.state"] = np.array(
                [v for _, v in motor_items], dtype=np.float32
            )
            result["_motor_names"] = motor_names

        # Camera frames: lerobot stores them under the camera id key directly.
        for cam_id in self.cameras_config:
            if cam_id in raw:
                result[f"observation.images.{cam_id}"] = raw[cam_id]

        return result

    def send_action(self, action: dict[str, Any]) -> None:
        """Send motor commands to the SO-101 arm.

        Args:
            action: Dict mapping ``"{motor_name}.pos"`` → int motor-tick value.
                    Example: ``{"gripper.pos": 2000, "shoulder_pan.pos": 2048}``
        """
        if self._robot is None:
            raise RuntimeError("Robot not connected. Call connect() first.")
        self._robot.send_action(action)
