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
"""Wrap LeRobot's recording pipeline.

Reads the Defty ``project.yaml``, constructs the correct LeRobot
``RecordConfig``, and calls ``lerobot.scripts.lerobot_record.record``
directly (bypassing draccus CLI parsing — the wrapper supports direct
config object injection when the first argument is already the target type).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from defty.project import find_project_root, load_project
from defty.utils import spawn_rerun_detached

logger = logging.getLogger(__name__)

__all__ = ["record"]


def record(
    project_path: str | Path | None = None,
    *,
    num_episodes: int = 1,
    fps: int | None = None,
    dataset_name: str | None = None,
    task: str | None = None,
    push_to_hub: bool = False,
    episode_time_s: float = 60,
    reset_time_s: float = 60,
    display: bool = False,
) -> None:
    """Record teleoperation episodes using LeRobot.

    Reads hardware configuration from ``project.yaml``, builds a
    ``RecordConfig``, and calls LeRobot's record pipeline directly.

    Args:
        project_path: Path to ``project.yaml`` or its parent directory.
                      Searches upward from cwd if *None*.
        num_episodes: Number of episodes to record.
        fps: Override the recording FPS from project config.
        dataset_name: Dataset repo_id (e.g. ``username/my_dataset`` for Hub,
                      or a plain name for local storage).
        task: One-line task description (e.g. "Pick the red cube").
        push_to_hub: Push dataset to HuggingFace Hub after recording.
        episode_time_s: Seconds of recording per episode.
        reset_time_s: Seconds to reset the environment between episodes.
        display: Show camera feeds and motor values via Rerun.

    Raises:
        FileNotFoundError: If no ``project.yaml`` can be found.
        RuntimeError: If hardware is not configured.
    """
    # Resolve project
    if project_path is not None:
        p = Path(project_path)
        yaml_path = p if p.name == "project.yaml" else p / "project.yaml"
    else:
        yaml_path = find_project_root()

    project = load_project(yaml_path)
    proj_name = project.get("project", {}).get("name", "defty_project")

    arms = project.get("hardware", {}).get("arms", [])
    cameras = project.get("hardware", {}).get("cameras", [])

    if not arms:
        raise RuntimeError("No arms configured. Run 'defty setup add-arm' first.")

    leaders = [a for a in arms if a.get("role") == "leader"]
    followers = [a for a in arms if a.get("role") == "follower"]

    if not leaders:
        raise RuntimeError("No leader arm found. Add one with 'defty setup add-arm --role leader'.")
    if not followers:
        raise RuntimeError("No follower arm found. Add one with 'defty setup add-arm --role follower'.")

    rec_cfg = project.get("recording", {})
    record_fps = fps or rec_cfg.get("fps", 30)
    ds_name = dataset_name or proj_name
    # lerobot requires repo_id in "namespace/name" format even for local datasets
    if "/" not in ds_name:
        ds_name = f"local/{ds_name}"
    task_desc = task or "Task recorded with Defty"

    calibration_dir = yaml_path.parent / "calibration"

    logger.info(
        "Recording %d episode(s) at %d FPS — %d leader(s), %d follower(s), %d camera(s)",
        num_episodes, record_fps, len(leaders), len(followers), len(cameras),
    )

    try:
        from lerobot.robots.so_follower import SOFollowerRobotConfig
        from lerobot.teleoperators.so_leader import SOLeaderTeleopConfig
        from lerobot.scripts.lerobot_record import DatasetRecordConfig, RecordConfig
        from lerobot.scripts.lerobot_record import record as lerobot_record
    except ImportError as exc:
        raise RuntimeError(f"LeRobot not available: {exc}") from exc

    leader = leaders[0]
    follower = followers[0]

    # Build camera config dict for the follower robot
    camera_configs: dict = {}
    for cam in cameras:
        try:
            from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
            device = cam.get("device", "0")
            idx = int(device) if str(device).isdigit() else device
            camera_configs[cam["id"]] = OpenCVCameraConfig(
                index_or_path=idx,
                width=cam.get("width", 640),
                height=cam.get("height", 480),
                fps=int(cam.get("fps", 30)),
            )
        except ImportError:
            logger.warning("OpenCV camera config unavailable; skipping camera %s", cam.get("id"))

    follower_cfg = SOFollowerRobotConfig(
        port=follower["port"],
        id=follower["id"],
        calibration_dir=calibration_dir,
        cameras=camera_configs,
    )
    leader_cfg = SOLeaderTeleopConfig(
        port=leader["port"],
        id=leader["id"],
        calibration_dir=calibration_dir,
    )
    dataset_cfg = DatasetRecordConfig(
        repo_id=ds_name,
        single_task=task_desc,
        root=str(yaml_path.parent / "data"),
        fps=record_fps,
        num_episodes=num_episodes,
        push_to_hub=push_to_hub,
        episode_time_s=episode_time_s,
        reset_time_s=reset_time_s,
    )

    # Pre-spawn Rerun viewer as a fully detached process so Ctrl+C during
    # recording never sends SIGINT to the viewer.  We then tell lerobot to
    # *connect* to it (display_ip/display_port) instead of spawning its own.
    rerun_proc = None
    display_ip = None
    display_port = None
    if display:
        rerun_proc = spawn_rerun_detached()
        if rerun_proc is not None:
            display_ip = "127.0.0.1"
            display_port = 9876
        else:
            logger.warning("Could not spawn Rerun viewer; recording without display.")
            display = False

    cfg = RecordConfig(
        robot=follower_cfg,
        teleop=leader_cfg,
        dataset=dataset_cfg,
        display_data=display,
        display_ip=display_ip,
        display_port=display_port,
        play_sounds=False,  # disable: requires PowerShell on Windows (blocked by execution policy)
    )

    try:
        # @parser.wrap() passes cfg through when first arg is already the target type
        lerobot_record(cfg)
    finally:
        if rerun_proc is not None:
            try:
                rerun_proc.terminate()
            except Exception:
                pass