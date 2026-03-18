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

import contextlib
import logging
import os
import sys
import time
from pathlib import Path

from defty.project import find_project_root, load_project
from defty.utils import spawn_rerun_detached

logger = logging.getLogger(__name__)

__all__ = ["record"]


# ── Dataset name helpers ──────────────────────────────────────────────────────


def _auto_dataset_name(data_dir: Path, base: str) -> str:
    """Return the next free numbered dataset name: ``base_001``, ``base_002``, …"""
    existing: set[str] = set()
    if data_dir.exists():
        existing = {p.name for p in data_dir.iterdir() if p.is_dir()}
    for i in range(1, 10_000):
        candidate = f"{base}_{i:03d}"
        if candidate not in existing:
            return candidate
    import time  # extreme fallback
    return f"{base}_{int(time.time())}"


def _latest_dataset(data_dir: Path) -> str | None:
    """Return the name of the most-recently-modified valid dataset dir, or None."""
    if not data_dir.exists():
        return None
    valid = [
        d for d in data_dir.iterdir()
        if d.is_dir() and (d / "meta" / "info.json").exists()
    ]
    if not valid:
        return None
    return max(valid, key=lambda d: d.stat().st_mtime).name




_PHASE_MAP: dict[str, tuple[str, str]] = {
    "Recording episode": ("🔴", "REC"),
    "Re-record episode": ("↩ ", "RE-RECORD"),
    "Reset the environment": ("⏸ ", "RESET"),
    "Stop recording": ("⏹ ", "STOPPING"),
    "Exiting": ("✓ ", "DONE"),
}


class _PhaseFilter(logging.Filter):
    """Reformat lerobot phase-transition messages with visual separators."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for keyword, (icon, label) in _PHASE_MAP.items():
            if keyword in msg:
                sep = "─" * 55
                record.msg = f"\n{sep}\n  {icon}  {label:<12} {msg}\n{sep}"
                record.args = ()
                break
        return True


# ── Motor stability patches ───────────────────────────────────────────────────

_MOTOR_PATCHES_APPLIED = False


def _apply_motor_stability_patches() -> None:
    """Patch LeRobot's motor bus for improved connection stability.

    LeRobot defaults to ``num_retry=0`` for all motor read/write operations,
    meaning a single missed serial packet kills the entire recording session.
    On Windows with CH343 USB-serial adapters, packet loss during USB bus
    contention (e.g. simultaneous camera streaming) is common.

    This patch:
    - Increases the default retry count from 0 to 3 for all motor operations
    - Doubles the serial packet timeout from 1000 ms to 2000 ms
    """
    global _MOTOR_PATCHES_APPLIED  # noqa: PLW0603
    if _MOTOR_PATCHES_APPLIED:
        return
    _MOTOR_PATCHES_APPLIED = True

    try:
        from lerobot.motors.motors_bus import SerialMotorsBus
        from lerobot.motors.feetech import feetech as _feetech_mod
    except ImportError:
        logger.debug("lerobot.motors not available — skipping stability patches")
        return

    # 1. Increase default timeout: 1000 ms → 2000 ms
    _feetech_mod.DEFAULT_TIMEOUT_MS = 2000
    _feetech_mod.FeetechMotorsBus.default_timeout = 2000

    _DEFAULT_RETRY = 3

    # 2. Wrap sync_read: num_retry 0 → 3
    _orig_sync_read = SerialMotorsBus.sync_read

    def _patched_sync_read(self, data_name, motors=None, *, normalize=True, num_retry=_DEFAULT_RETRY):
        return _orig_sync_read(self, data_name, motors, normalize=normalize, num_retry=num_retry)

    SerialMotorsBus.sync_read = _patched_sync_read

    # 3. Wrap sync_write: num_retry 0 → 3
    _orig_sync_write = SerialMotorsBus.sync_write

    def _patched_sync_write(self, data_name, values, *, normalize=True, num_retry=_DEFAULT_RETRY):
        return _orig_sync_write(self, data_name, values, normalize=normalize, num_retry=num_retry)

    SerialMotorsBus.sync_write = _patched_sync_write

    # 4. Wrap single-motor write (used by configure()): num_retry 0 → 3
    _orig_write = SerialMotorsBus.write

    def _patched_write(self, data_name, motor, value, *, normalize=True, num_retry=_DEFAULT_RETRY):
        return _orig_write(self, data_name, motor, value, normalize=normalize, num_retry=num_retry)

    SerialMotorsBus.write = _patched_write

    # 5. Wrap single-motor read: num_retry 0 → 3
    _orig_read = SerialMotorsBus.read

    def _patched_read(self, data_name, motor, *, normalize=True, num_retry=_DEFAULT_RETRY):
        return _orig_read(self, data_name, motor, normalize=normalize, num_retry=num_retry)

    SerialMotorsBus.read = _patched_read

    logger.info("Motor stability patches applied: timeout=2000ms, num_retry=%d", _DEFAULT_RETRY)


# ── C-level stdout suppressor (kills SVT-AV1 encoder noise) ──────────────────


@contextlib.contextmanager
def _suppress_c_stdout():
    """Redirect C-level fd 1 to /dev/null to silence SVT-AV1 encoder noise.

    SVT-AV1 writes its verbose init messages directly to the C runtime's
    stdout (fd 1), bypassing Python logging.  Redirecting fd 1 while keeping
    fd 2 (Python logging / stderr) intact cleans up the recording output.
    Falls back silently on any OS error.
    """
    old_sys_stdout = sys.stdout
    old_fd: int | None = None
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        old_fd = os.dup(1)
        os.dup2(devnull_fd, 1)
        os.close(devnull_fd)
        sys.stdout = open(os.devnull, "w")
    except OSError:
        pass  # If fd tricks fail, just run without suppression

    try:
        yield
    finally:
        try:
            sys.stdout.close()
        except Exception:
            pass
        sys.stdout = old_sys_stdout
        if old_fd is not None:
            try:
                os.dup2(old_fd, 1)
                os.close(old_fd)
            except OSError:
                pass


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
    resume: bool = False,
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
        resume: Append to an existing dataset instead of creating a new one.

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

    data_dir = yaml_path.parent / "data"

    if resume:
        # --resume without --dataset-name → pick the most recently modified dataset
        if dataset_name is None:
            auto = _latest_dataset(data_dir)
            if auto is None:
                raise RuntimeError(
                    "No existing dataset found to resume. "
                    "Run 'defty record' (without --resume) to start a new one."
                )
            dataset_name = auto
            logger.info("Auto-selected dataset to resume: %s", dataset_name)
    else:
        # No explicit name → auto-generate base_001, base_002, …
        if dataset_name is None:
            base = project.get("project", {}).get("name", "defty_project")
            dataset_name = _auto_dataset_name(data_dir, base)

    # lerobot requires repo_id in "namespace/name" format even for local datasets
    ds_name = dataset_name if "/" in dataset_name else f"local/{dataset_name}"

    local_name = ds_name.split("/")[-1]
    dataset_root_path = data_dir / local_name
    dataset_root = str(dataset_root_path)

    # Pre-flight: handle leftover dirs from previous failed/aborted runs.
    # lerobot calls LeRobotDatasetMetadata.create() with exist_ok=False, so
    # any pre-existing directory causes FileExistsError even if empty.
    if dataset_root_path.exists() and not resume:
        meta_file = dataset_root_path / "meta" / "info.json"
        if meta_file.exists():
            raise RuntimeError(
                f"Dataset '{local_name}' already exists at {dataset_root}.\n"
                "  • To add more episodes: defty record --resume ...\n"
                "  • To start over: delete the data directory and re-run."
            )
        else:
            # Partial/empty dir from a previous crash — clean up silently.
            import shutil
            logger.info("Removing incomplete dataset directory from previous run: %s", dataset_root)
            shutil.rmtree(dataset_root_path)

    task_desc = task or "Task recorded with Defty"

    calibration_dir = yaml_path.parent / "calibration"

    logger.info(
        "Recording %d episode(s) into '%s' at %d FPS — %d leader(s), %d follower(s), %d camera(s)",
        num_episodes, local_name, record_fps, len(leaders), len(followers), len(cameras),
    )

    try:
        from lerobot.robots.so_follower import SOFollowerRobotConfig
        from lerobot.teleoperators.so_leader import SOLeaderTeleopConfig
        from lerobot.scripts.lerobot_record import DatasetRecordConfig, RecordConfig
        from lerobot.scripts.lerobot_record import record as lerobot_record
    except ImportError as exc:
        raise RuntimeError(f"LeRobot not available: {exc}") from exc

    # Apply motor stability patches before lerobot creates any motor bus
    _apply_motor_stability_patches()

    leader = leaders[0]
    follower = followers[0]

    # Build camera config dict for the follower robot.
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
        root=dataset_root,
        fps=record_fps,
        num_episodes=num_episodes,
        push_to_hub=push_to_hub,
        episode_time_s=episode_time_s,
        reset_time_s=reset_time_s,
        streaming_encoding=True,
        num_image_writer_processes=1,
        num_image_writer_threads_per_camera=4,
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
        resume=resume,
        play_sounds=False,  # disable: requires PowerShell on Windows (blocked by execution policy)
    )

    # Install phase-separator filter on the root logger so lerobot's
    # `logging.info("Recording episode …")` calls stand out visually.
    root_logger = logging.getLogger()
    phase_filter = _PhaseFilter()
    root_logger.addFilter(phase_filter)

    # Retry settings — servo arms occasionally lose packets during USB contention
    _RECONNECT_INTERVAL_S = 5
    _RECONNECT_TIMEOUT_S = 120
    reconnect_deadline: float | None = None

    try:
        while True:
            try:
                with _suppress_c_stdout():
                    try:
                        # @parser.wrap() passes cfg through when first arg is already the target type
                        lerobot_record(cfg)
                    except ValueError as exc:
                        if "add_frame" in str(exc):
                            logger.warning(
                                "Recording ended with an empty episode — "
                                "you pressed → or Esc before the arm recorded any frames. "
                                "All previously completed episodes were saved."
                            )
                        else:
                            raise
                break  # Recording completed successfully

            except ConnectionError as exc:
                # Servo/camera connection lost — discard current episode, retry
                if reconnect_deadline is None:
                    reconnect_deadline = time.time() + _RECONNECT_TIMEOUT_S

                remaining = reconnect_deadline - time.time()
                if remaining <= 0:
                    raise RuntimeError(
                        f"Robot connection lost and could not reconnect "
                        f"after {_RECONNECT_TIMEOUT_S}s.\n"
                        f"  Last error: {exc}\n"
                        f"  Completed episodes were saved to: {dataset_root}"
                    ) from exc

                logger.warning(
                    "Robot connection lost — current episode discarded.\n"
                    "  Error: %s\n"
                    "  Retrying in %ds (timeout in %ds)...",
                    exc, _RECONNECT_INTERVAL_S, int(remaining),
                )
                time.sleep(_RECONNECT_INTERVAL_S)

                # Check if any episodes were saved before the crash.
                # If not, the dataset dir is an empty shell that lerobot
                # cannot resume from — clean it up and start fresh.
                meta_ok = (
                    (dataset_root_path / "meta" / "info.json").exists()
                    and (dataset_root_path / "meta" / "tasks.parquet").exists()
                )
                if not meta_ok and dataset_root_path.exists():
                    import shutil
                    shutil.rmtree(dataset_root_path, ignore_errors=True)

                # Rebuild config — resume only if there are saved episodes
                dataset_cfg = DatasetRecordConfig(
                    repo_id=ds_name,
                    single_task=task_desc,
                    root=dataset_root,
                    fps=record_fps,
                    num_episodes=num_episodes,
                    push_to_hub=push_to_hub,
                    episode_time_s=episode_time_s,
                    reset_time_s=reset_time_s,
                    streaming_encoding=True,
                    num_image_writer_processes=1,
                    num_image_writer_threads_per_camera=4,
                )
                cfg = RecordConfig(
                    robot=follower_cfg,
                    teleop=leader_cfg,
                    dataset=dataset_cfg,
                    display_data=display,
                    display_ip=display_ip,
                    display_port=display_port,
                    resume=meta_ok,
                    play_sounds=False,
                )
    finally:
        root_logger.removeFilter(phase_filter)
        if rerun_proc is not None:
            try:
                rerun_proc.terminate()
            except Exception:
                pass