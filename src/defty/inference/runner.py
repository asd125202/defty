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
#
# Portions of this file are derived from LeRobot by HuggingFace Inc.
# (https://github.com/huggingface/lerobot), used under the Apache License 2.0.
# Original copyright: Copyright 2024 The HuggingFace Inc. team.
"""Run a trained policy on the physical robot.

Uses lerobot's record pipeline in policy-only mode (no teleoperation).
The robot executes actions predicted by the model while optionally
recording the rollout as a new dataset for later analysis.

Two modes are supported:

- **With vision**: cameras are active, the policy receives image
  observations and (optionally) a live Rerun feed is displayed.
- **Without vision**: cameras are disabled — only joint-state observations
  are fed to the policy.  Useful for state-only policies or debugging.
"""

from __future__ import annotations

import logging
from pathlib import Path

from defty.project import find_project_root, load_project
from defty.recording.recorder import _auto_dataset_name, _latest_dataset
from defty.utils import spawn_rerun_detached

logger = logging.getLogger(__name__)

__all__ = ["run"]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _latest_model(models_dir: Path) -> str | None:
    """Return the name of the most recently modified model directory."""
    if not models_dir.exists():
        return None
    candidates = [
        p for p in models_dir.iterdir()
        if p.is_dir() and _find_checkpoint(p) is not None
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest.name


def _find_checkpoint(model_dir: Path) -> Path | None:
    """Find the latest ``pretrained_model`` directory inside a model's checkpoints.

    Returns the path to ``checkpoints/<highest_step>/pretrained_model`` or
    *None* if no valid checkpoint exists.
    """
    ckpt_root = model_dir / "checkpoints"
    if not ckpt_root.exists():
        return None
    step_dirs = sorted(
        (d for d in ckpt_root.iterdir() if d.is_dir() and d.name.isdigit()),
        key=lambda d: int(d.name),
    )
    if not step_dirs:
        return None
    pretrained = step_dirs[-1] / "pretrained_model"
    if pretrained.exists() and (pretrained / "config.json").exists():
        return pretrained
    return None


# ── Main entry ───────────────────────────────────────────────────────────────


def run(
    project_path: str | Path | None = None,
    *,
    model_name: str | None = None,
    episodes: int = 1,
    display: bool = False,
    vision: bool = True,
    record: bool = False,
    dataset_name: str | None = None,
    fps: int | None = None,
    episode_time_s: float = 60.0,
    reset_time_s: float = 10.0,
) -> None:
    """Run a trained policy on the robot.

    Loads a model from ``models/<name>/``, connects to the robot defined
    in ``project.yaml``, and executes inference episodes.

    Args:
        project_path: Path to ``project.yaml`` or its parent directory.
        model_name: Model directory name under ``models/``.
                    Auto-selects the most recent model if *None*.
        episodes: Number of episodes to execute.
        display: Show live camera feed in Rerun.
        vision: Enable cameras.  Set *False* for state-only policies.
        record: Save the rollout as a new dataset under ``data/``.
        dataset_name: Dataset name when *record* is True.  Auto-generated
                      if *None*.
        fps: Override the recording / control FPS.
        episode_time_s: Maximum time per episode in seconds.
        reset_time_s: Pause between episodes for environment reset.

    Raises:
        FileNotFoundError: If ``project.yaml`` cannot be found.
        RuntimeError: If no valid model or robot configuration exists.
    """
    # ── Resolve project ──────────────────────────────────────────────────
    if project_path is not None:
        p = Path(project_path)
        yaml_path = p if p.name == "project.yaml" else p / "project.yaml"
    else:
        yaml_path = find_project_root()

    project = load_project(yaml_path)
    proj_name = project.get("project", {}).get("name", "defty_project")

    models_dir = yaml_path.parent / "models"
    data_dir = yaml_path.parent / "data"
    calibration_dir = yaml_path.parent / "calibration"

    # ── Resolve model ────────────────────────────────────────────────────
    if model_name is None:
        model_name = _latest_model(models_dir)
        if model_name is None:
            raise RuntimeError(
                "No trained models found. Run 'defty train' first."
            )
        logger.info("Auto-selected latest model: %s", model_name)

    model_dir = models_dir / model_name
    if not model_dir.exists():
        raise RuntimeError(f"Model '{model_name}' not found in {models_dir}")

    checkpoint_path = _find_checkpoint(model_dir)
    if checkpoint_path is None:
        raise RuntimeError(
            f"No valid checkpoint found in {model_dir}. "
            "Training may not have completed successfully."
        )

    logger.info("Using checkpoint: %s", checkpoint_path)

    # ── Resolve hardware from project.yaml ───────────────────────────────
    hw = project.get("hardware", {})
    arms = hw.get("arms", [])
    followers = [a for a in arms if a.get("role") == "follower"]
    cameras = hw.get("cameras", [])
    record_fps = fps or int(project.get("recording", {}).get("fps", 30))

    if not followers:
        raise RuntimeError(
            "No follower arms defined in project.yaml. "
            "Run 'defty scan ports' and 'defty calibrate' first."
        )

    # ── Resolve dataset for recording ────────────────────────────────────
    # lerobot requires dataset name to start with "eval_" when a policy is used
    if record:
        if dataset_name is None:
            base = f"eval_{model_name}"
            dataset_name = _auto_dataset_name(data_dir, base)
        elif not dataset_name.startswith("eval_"):
            dataset_name = f"eval_{dataset_name}"
        ds_name = dataset_name if "/" in dataset_name else f"local/{dataset_name}"
    else:
        # Even when not recording, lerobot needs a dataset config.
        ds_name = f"local/eval_tmp_{model_name}"

    local_name = ds_name.split("/")[-1]
    dataset_root_path = data_dir / local_name
    dataset_root = str(dataset_root_path)

    # Clean up any leftover temp dir from a previous --no-record run
    if not record and dataset_root_path.exists():
        import shutil
        shutil.rmtree(dataset_root_path, ignore_errors=True)

    # ── Build lerobot config ─────────────────────────────────────────────
    try:
        from lerobot.robots.so_follower import SOFollowerRobotConfig
        from lerobot.scripts.lerobot_record import DatasetRecordConfig, RecordConfig
        from lerobot.scripts.lerobot_record import record as lerobot_record
        from lerobot.configs.policies import PreTrainedConfig
    except ImportError as exc:
        raise RuntimeError(f"LeRobot not available: {exc}") from exc

    # Apply motor stability patches before lerobot creates any motor bus
    from defty.recording.recorder import _apply_motor_stability_patches
    _apply_motor_stability_patches()

    follower = followers[0]

    # Camera config (only if vision enabled).
    camera_configs: dict = {}
    if vision:
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
                logger.warning(
                    "OpenCV camera config unavailable; skipping camera %s",
                    cam.get("id"),
                )
                )

    follower_cfg = SOFollowerRobotConfig(
        port=follower["port"],
        id=follower["id"],
        calibration_dir=calibration_dir,
        cameras=camera_configs,
    )

    dataset_cfg = DatasetRecordConfig(
        repo_id=ds_name,
        single_task=f"Run {model_name}",
        root=dataset_root,
        fps=record_fps,
        num_episodes=episodes,
        push_to_hub=False,
        episode_time_s=episode_time_s,
        reset_time_s=reset_time_s,
        num_image_writer_processes=1,
        num_image_writer_threads_per_camera=4,
    )

    # Load the policy config from the checkpoint
    policy_cfg = PreTrainedConfig.from_pretrained(str(checkpoint_path))
    policy_cfg.pretrained_path = checkpoint_path

    # Auto-select best device
    import torch as _torch
    if _torch.cuda.is_available():
        policy_cfg.device = "cuda"
    elif getattr(_torch.backends, "mps", None) and _torch.backends.mps.is_available():
        policy_cfg.device = "mps"
    else:
        policy_cfg.device = "cpu"
    logger.info("Inference device: %s", policy_cfg.device)

    # Rerun display
    rerun_proc = None
    display_ip = None
    display_port = None
    if display:
        rerun_proc = spawn_rerun_detached()
        if rerun_proc is not None:
            display_ip = "127.0.0.1"
            display_port = 9876
        else:
            logger.warning("Could not spawn Rerun viewer; running without display.")
            display = False

    cfg = RecordConfig(
        robot=follower_cfg,
        teleop=None,  # no teleoperation — policy-only inference
        dataset=dataset_cfg,
        policy=policy_cfg,
        display_data=display,
        display_ip=display_ip,
        display_port=display_port,
        resume=False,
        play_sounds=False,
    )

    # ── Run ──────────────────────────────────────────────────────────────
    from defty.recording.recorder import _PhaseFilter, _suppress_c_stdout

    root_logger = logging.getLogger()
    phase_filter = _PhaseFilter()
    root_logger.addFilter(phase_filter)

    try:
        with _suppress_c_stdout():
            try:
                lerobot_record(cfg)
            except ValueError as exc:
                if "add_frame" in str(exc):
                    logger.warning(
                        "Run ended with an empty episode (stopped before any "
                        "frames were captured). Completed episodes are saved."
                    )
                else:
                    raise
            except OSError as exc:
                # Windows symlink error — not fatal
                if "1314" in str(exc) or "privilege" in str(exc).lower():
                    logger.warning("Symlink error (non-fatal): %s", exc)
                else:
                    raise
    finally:
        root_logger.removeFilter(phase_filter)
        if rerun_proc is not None:
            try:
                rerun_proc.terminate()
            except Exception:
                pass

        # Clean up temp dataset if not recording
        if not record and dataset_root_path.exists():
            import shutil
            shutil.rmtree(dataset_root_path, ignore_errors=True)
            logger.info("Cleaned up temporary run data.")
