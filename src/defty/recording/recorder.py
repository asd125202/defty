# Copyright (c) 2026 APRL Technologies Inc. All rights reserved.
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
""""""Wrap LeRobot's recording pipeline.

Reads the Defty `project.yaml`, constructs the LeRobot configuration
objects, and delegates to `lerobot.scripts.lerobot_record`.
""""""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from defty.project import load_project

logger = logging.getLogger(__name__)

__all__ = ["record"]


def record(
    project_path: str | Path | None = None,
    *,
    num_episodes: int = 1,
    fps: int | None = None,
    dataset_name: str | None = None,
    push_to_hub: bool = False,
) -> None:
    """"""Record teleoperation episodes using LeRobot.

    Reads hardware configuration from `project.yaml`, builds the
    appropriate LeRobot `RecordConfig`, and calls the record script.

    Args:
        project_path: Path to `project.yaml` or its parent directory.
                      Searches upward from cwd if *None*.
        num_episodes: Number of episodes to record.
        fps: Override the recording FPS from project config.
        dataset_name: Dataset name. Defaults to `<project_name>_dataset`.
        push_to_hub: Whether to push the dataset to the HuggingFace Hub.

    Raises:
        FileNotFoundError: If no `project.yaml` can be found.
        RuntimeError: If hardware is not configured or not connected.
    """"""
    project = load_project(project_path)
    proj_name = project.get("project", {}).get("name", "defty_project")

    arms = project.get("hardware", {}).get("arms", [])
    cameras = project.get("hardware", {}).get("cameras", [])

    if not arms:
        msg = "No arms configured. Run 'defty setup add-arm' first."
        raise RuntimeError(msg)

    # Resolve recording parameters
    rec_cfg = project.get("recording", {})
    record_fps = fps or rec_cfg.get("fps", 30)
    dataset_dir = rec_cfg.get("dataset_dir", "data")
    ds_name = dataset_name or f"{proj_name}_dataset"

    # Find leader and follower arms
    leaders = [a for a in arms if a.get("role") == "leader"]
    followers = [a for a in arms if a.get("role") == "follower"]

    if not leaders:
        msg = "No leader arm configured. Add a leader arm for teleoperation recording."
        raise RuntimeError(msg)
    if not followers:
        msg = "No follower arm configured. Add a follower arm for teleoperation recording."
        raise RuntimeError(msg)

    logger.info(
        "Recording %d episode(s) at %d FPS — %d leader(s), %d follower(s), %d camera(s)",
        num_episodes,
        record_fps,
        len(leaders),
        len(followers),
        len(cameras),
    )

    # Build LeRobot config and call record
    _invoke_lerobot_record(
        leaders=leaders,
        followers=followers,
        cameras=cameras,
        num_episodes=num_episodes,
        fps=record_fps,
        dataset_dir=dataset_dir,
        dataset_name=ds_name,
        push_to_hub=push_to_hub,
    )


def _invoke_lerobot_record(
    *,
    leaders: list[dict[str, Any]],
    followers: list[dict[str, Any]],
    cameras: list[dict[str, Any]],
    num_episodes: int,
    fps: int,
    dataset_dir: str,
    dataset_name: str,
    push_to_hub: bool,
) -> None:
    """"""Construct LeRobot objects and delegate to the record pipeline.

    This is the integration seam between Defty's config world and
    LeRobot's draccus dataclass world.
    """"""
    try:
        from lerobot.motors.feetech import FeetechMotorsBus, Motor
        from lerobot.robots.so_follower import SOFollower, SOFollowerConfig
        from lerobot.teleoperators.so100 import SO100Leader, SO100LeaderConfig
    except ImportError as exc:
        msg = "LeRobot is not installed. Run: pip install 'defty[dev]'"
        raise RuntimeError(msg) from exc

    # Build leader teleoperator(s)
    leader_configs: list[tuple[str, Any]] = []
    for ldr in leaders:
        port = ldr.get("port", "")
        arm_id = ldr.get("id", "leader")
        calibration = ldr.get("calibration", {})
        leader_cfg = SO100LeaderConfig(port=port)
        leader_configs.append((arm_id, leader_cfg))

    # Build follower robot(s)
    follower_configs: list[tuple[str, Any]] = []
    for flw in followers:
        port = flw.get("port", "")
        arm_id = flw.get("id", "follower")
        calibration = flw.get("calibration", {})
        follower_cfg = SOFollowerConfig(port=port)
        follower_configs.append((arm_id, follower_cfg))

    # Build camera configs
    camera_dict: dict[str, int | str] = {}
    for cam in cameras:
        cam_id = cam.get("id", "cam_0")
        device = cam.get("device", "")
        camera_dict[cam_id] = int(device) if device.isdigit() else device

    logger.info("Delegating to LeRobot record pipeline...")

    # For now, use the first leader/follower pair
    # TODO: Support multi-arm recording when LeRobot adds the capability
    leader_id, leader_cfg = leader_configs[0]
    follower_id, follower_cfg = follower_configs[0]

    try:
        from lerobot.scripts.lerobot_record import record as lerobot_record

        lerobot_record(
            robot_type="so101",
            robot_overrides=[f"leader_arms.main.port={leader_cfg.port}", f"follower_arms.main.port={follower_cfg.port}"],
            fps=fps,
            root=dataset_dir,
            repo_id=dataset_name,
            num_episodes=num_episodes,
            push_to_hub=push_to_hub,
        )
    except TypeError:
        logger.warning(
            "LeRobot record API signature may have changed. "
            "Falling back to direct robot construction."
        )
        _record_fallback(
            leader_cfg=leader_cfg,
            follower_cfg=follower_cfg,
            cameras=camera_dict,
            num_episodes=num_episodes,
            fps=fps,
            dataset_dir=dataset_dir,
            dataset_name=dataset_name,
        )


def _record_fallback(
    *,
    leader_cfg: Any,
    follower_cfg: Any,
    cameras: dict[str, int | str],
    num_episodes: int,
    fps: int,
    dataset_dir: str,
    dataset_name: str,
) -> None:
    """"""Fallback recording path using direct robot API.""""""
    logger.info("Using direct robot API for recording (fallback path)")
    # This will be fleshed out as LeRobot's API stabilizes
    raise NotImplementedError(
        "Direct recording fallback not yet implemented. "
        "Please ensure LeRobot >= 0.5.1 is installed."
    )