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
""""""Hardware registry — manages the `hardware` section of `project.yaml`.

All mutations go through this module so that the rest of the codebase
never has to worry about the YAML schema.  Every function takes the
project dict (as returned by `defty.project.load_project`) as its
first argument and returns the mutated dict.  The caller is responsible
for persisting changes via `defty.project.save_project`.
""""""

from __future__ import annotations

import logging
import re
from typing import Any

from defty.hardware.detector import list_cameras, list_serial_ports

logger = logging.getLogger(__name__)

__all__ = [
    "add_arm",
    "add_camera",
    "remove_arm",
    "remove_camera",
    "update_ports",
    "generate_arm_id",
    "generate_camera_id",
]


# ── ID generation ────────────────────────────────────────────────────────────


def generate_arm_id(
    project: dict[str, Any],
    robot_type: str = "so101",
    role: str = "follower",
) -> str:
    """"""Generate a short, unique default ID for an arm.

    Pattern: `<robot_type>_<role>_<n>` — e.g. `so101_follower_1`.

    Args:
        project: The loaded project dict.
        robot_type: Robot model identifier (default `so101`).
        role: `leader` or `follower`.

    Returns:
        A unique arm ID string.
    """"""
    existing = {a["id"] for a in project.get("hardware", {}).get("arms", [])}
    n = 1
    while True:
        candidate = f"{robot_type}_{role}_{n}"
        if candidate not in existing:
            return candidate
        n += 1


def generate_camera_id(
    project: dict[str, Any],
    position: str = "",
) -> str:
    """"""Generate a short, unique default ID for a camera.

    If *position* is given (e.g. `wrist`), produces `cam_wrist`.
    Otherwise produces `cam_0`, `cam_1`, …

    Args:
        project: The loaded project dict.
        position: Optional position label.

    Returns:
        A unique camera ID string.
    """"""
    existing = {c["id"] for c in project.get("hardware", {}).get("cameras", [])}

    if position:
        candidate = f"cam_{_slugify(position)}"
        if candidate not in existing:
            return candidate
        n = 2
        while True:
            numbered = f"{candidate}_{n}"
            if numbered not in existing:
                return numbered
            n += 1
    else:
        n = 0
        while True:
            candidate = f"cam_{n}"
            if candidate not in existing:
                return candidate
            n += 1


# ── Arm management ───────────────────────────────────────────────────────────


def add_arm(
    project: dict[str, Any],
    *,
    arm_id: str | None = None,
    port: str = "",
    hardware_id: str = "",
    robot_type: str = "so101",
    role: str = "follower",
    label: str = "",
) -> dict[str, Any]:
    """"""Register a new robot arm in the project.

    Args:
        project: The project dict to mutate.
        arm_id: Explicit ID. Auto-generated if *None*.
        port: Serial port (e.g. `/dev/ttyACM0`, `COM3`).
        hardware_id: Fingerprint from `resolve_hardware_id`.
        robot_type: Robot model (default `so101`).
        role: `leader` or `follower`.
        label: Human-readable position label.

    Returns:
        The mutated project dict.

    Raises:
        ValueError: If an arm with the same *arm_id* already exists.
    """"""
    hw = project.setdefault("hardware", {})
    arms: list[dict[str, Any]] = hw.setdefault("arms", [])

    if arm_id is None:
        arm_id = generate_arm_id(project, robot_type, role)

    if any(a["id"] == arm_id for a in arms):
        msg = f"Arm '{arm_id}' already exists in project"
        raise ValueError(msg)

    entry: dict[str, Any] = {
        "id": arm_id,
        "robot_type": robot_type,
        "role": role,
        "port": port,
        "hardware_id": hardware_id,
        "label": label,
        "calibration": {},
    }
    arms.append(entry)
    logger.info("Added arm '%s' (port=%s, hardware_id=%s)", arm_id, port, hardware_id)
    return project


def remove_arm(project: dict[str, Any], arm_id: str) -> dict[str, Any]:
    """"""Remove a registered arm by its ID.

    Args:
        project: The project dict to mutate.
        arm_id: The ID of the arm to remove.

    Returns:
        The mutated project dict.

    Raises:
        KeyError: If no arm with *arm_id* exists.
    """"""
    arms: list[dict[str, Any]] = project.get("hardware", {}).get("arms", [])
    for i, a in enumerate(arms):
        if a["id"] == arm_id:
            arms.pop(i)
            logger.info("Removed arm '%s'", arm_id)
            return project
    msg = f"Arm '{arm_id}' not found"
    raise KeyError(msg)


# ── Camera management ────────────────────────────────────────────────────────


def add_camera(
    project: dict[str, Any],
    *,
    camera_id: str | None = None,
    device: str = "",
    hardware_id: str = "",
    position: str = "",
    width: int = 640,
    height: int = 480,
    fps: float = 30.0,
) -> dict[str, Any]:
    """"""Register a new camera in the project.

    Args:
        project: The project dict to mutate.
        camera_id: Explicit ID. Auto-generated if *None*.
        device: OS device path (e.g. `/dev/video0`, index, or instance ID).
        hardware_id: Fingerprint from `resolve_camera_hardware_id`.
        position: Human-readable position label (e.g. `wrist`, `overhead`).
        width: Capture width in pixels.
        height: Capture height in pixels.
        fps: Capture frame rate.

    Returns:
        The mutated project dict.

    Raises:
        ValueError: If a camera with the same *camera_id* already exists.
    """"""
    hw = project.setdefault("hardware", {})
    cameras: list[dict[str, Any]] = hw.setdefault("cameras", [])

    if camera_id is None:
        camera_id = generate_camera_id(project, position)

    if any(c["id"] == camera_id for c in cameras):
        msg = f"Camera '{camera_id}' already exists in project"
        raise ValueError(msg)

    entry: dict[str, Any] = {
        "id": camera_id,
        "device": device,
        "hardware_id": hardware_id,
        "position": position,
        "width": width,
        "height": height,
        "fps": fps,
    }
    cameras.append(entry)
    logger.info("Added camera '%s' (device=%s, hardware_id=%s)", camera_id, device, hardware_id)
    return project


def remove_camera(project: dict[str, Any], camera_id: str) -> dict[str, Any]:
    """"""Remove a registered camera by its ID.

    Args:
        project: The project dict to mutate.
        camera_id: The ID of the camera to remove.

    Returns:
        The mutated project dict.

    Raises:
        KeyError: If no camera with *camera_id* exists.
    """"""
    cameras: list[dict[str, Any]] = project.get("hardware", {}).get("cameras", [])
    for i, c in enumerate(cameras):
        if c["id"] == camera_id:
            cameras.pop(i)
            logger.info("Removed camera '%s'", camera_id)
            return project
    msg = f"Camera '{camera_id}' not found"
    raise KeyError(msg)


# ── Port update (re-association) ─────────────────────────────────────────────


def update_ports(project: dict[str, Any]) -> dict[str, Any]:
    """"""Re-scan hardware and update port assignments using fingerprints.

    Iterates over registered arms and cameras, matches their stored
    `hardware_id` against currently connected devices, and updates the
    `port` / `device` field if the OS-assigned name changed.

    Args:
        project: The project dict to mutate.

    Returns:
        The mutated project dict.
    """"""
    # Build lookup: hardware_id -> current port
    serial_hw_map: dict[str, str] = {}
    for sp in list_serial_ports():
        if sp.hardware_id:
            serial_hw_map[sp.hardware_id] = sp.port

    camera_hw_map: dict[str, str] = {}
    for cam in list_cameras():
        if cam.hardware_id:
            camera_hw_map[cam.hardware_id] = cam.device

    # Update arms
    for arm in project.get("hardware", {}).get("arms", []):
        hw_id = arm.get("hardware_id", "")
        if hw_id and hw_id in serial_hw_map:
            new_port = serial_hw_map[hw_id]
            if arm["port"] != new_port:
                logger.info("Arm '%s': port updated %s -> %s", arm["id"], arm["port"], new_port)
                arm["port"] = new_port

    # Update cameras
    for cam in project.get("hardware", {}).get("cameras", []):
        hw_id = cam.get("hardware_id", "")
        if hw_id and hw_id in camera_hw_map:
            new_device = camera_hw_map[hw_id]
            if cam["device"] != new_device:
                logger.info("Camera '%s': device updated %s -> %s", cam["id"], cam["device"], new_device)
                cam["device"] = new_device

    return project


# ── Helpers ──────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """"""Convert text to a lowercase slug suitable for use in IDs.""""""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")