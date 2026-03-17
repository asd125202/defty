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
""""""Hardware detection — serial ports and cameras.

Provides cross-platform scanning for serial adapters and video capture
devices.  Results include fingerprint data so callers can match a
physical device to its stored configuration even when OS-assigned
names change.
""""""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from serial.tools import list_ports

from defty.hardware.fingerprint import (
    HardwareInfo,
    resolve_camera_hardware_id,
    resolve_hardware_id,
    resolve_hardware_info,
)

logger = logging.getLogger(__name__)

__all__ = [
    "SerialPortInfo",
    "CameraInfo",
    "list_serial_ports",
    "list_cameras",
]


# ── Serial port scanning ────────────────────────────────────────────────────


@dataclass(frozen=True)
class SerialPortInfo:
    """"""Discovered serial port with fingerprint metadata.""""""

    port: str
    hardware_id: str
    vendor: str
    model: str
    serial: str
    location: str
    description: str


def list_serial_ports() -> list[SerialPortInfo]:
    """"""Scan for connected USB-to-serial adapters.

    Uses `pyserial`'s `list_ports.comports()` which works on Linux,
    macOS, and Windows.

    Returns:
        A list of `SerialPortInfo` for every detected serial port,
        sorted by port name.
    """"""
    results: list[SerialPortInfo] = []
    for p in sorted(list_ports.comports(), key=lambda x: x.device):
        info = resolve_hardware_info(p)
        results.append(
            SerialPortInfo(
                port=p.device,
                hardware_id=info.hardware_id,
                vendor=info.vendor,
                model=info.model,
                serial=info.serial,
                location=info.location,
                description=p.description or "",
            )
        )
    logger.info("Found %d serial port(s)", len(results))
    return results


# ── Camera scanning ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CameraInfo:
    """"""Discovered camera device with fingerprint metadata.""""""

    device: str
    index: int
    hardware_id: str
    name: str


def list_cameras() -> list[CameraInfo]:
    """"""Scan for connected video capture devices.

    Uses platform-specific strategies:
    - **Linux**: enumerates `/dev/video*` and filters to capture-capable
      nodes via `v4l2-ctl`.
    - **macOS**: parses `system_profiler SPCameraDataType`.
    - **Windows**: queries connected camera PnP devices via `pnputil`.

    Returns:
        A list of `CameraInfo` for every detected camera.
    """"""
    system = platform.system()
    if system == "Linux":
        cameras = _scan_cameras_linux()
    elif system == "Darwin":
        cameras = _scan_cameras_macos()
    elif system == "Windows":
        cameras = _scan_cameras_windows()
    else:
        logger.warning("Camera scanning not supported on %s", system)
        cameras = []
    logger.info("Found %d camera(s)", len(cameras))
    return cameras


# ── Linux ────────────────────────────────────────────────────────────────────


def _is_capture_node_linux(device: str) -> bool:
    """"""Check if a /dev/video* node supports video capture (not just metadata).""""""
    try:
        out = subprocess.check_output(
            ["v4l2-ctl", "--device", device, "--all"],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        return "Video Capture" in out
    except (FileNotFoundError, subprocess.SubprocessError):
        return True  # assume capture if v4l2-ctl unavailable


def _scan_cameras_linux() -> list[CameraInfo]:
    """"""Scan /dev/video* on Linux, deduplicate by hardware ID.""""""
    seen_hw_ids: set[str] = set()
    cameras: list[CameraInfo] = []

    video_devices = sorted(Path("/dev").glob("video*"), key=lambda p: p.name)
    for dev_path in video_devices:
        device = str(dev_path)
        if not _is_capture_node_linux(device):
            continue

        hw_id = resolve_camera_hardware_id(device) or ""
        if hw_id and hw_id in seen_hw_ids:
            continue
        if hw_id:
            seen_hw_ids.add(hw_id)

        idx_match = re.search(r"video(\d+)", device)
        index = int(idx_match.group(1)) if idx_match else -1

        name = _v4l2_card_name(device)
        cameras.append(CameraInfo(device=device, index=index, hardware_id=hw_id, name=name))

    return cameras


def _v4l2_card_name(device: str) -> str:
    """"""Read the V4L2 card name for a device.""""""
    try:
        out = subprocess.check_output(
            ["v4l2-ctl", "--device", device, "--info"],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if "Card type" in line:
                return line.split(":", 1)[1].strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return ""


# ── macOS ────────────────────────────────────────────────────────────────────


def _scan_cameras_macos() -> list[CameraInfo]:
    """"""Scan cameras on macOS via system_profiler.""""""
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPCameraDataType"],
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.debug("system_profiler failed")
        return []

    cameras: list[CameraInfo] = []
    current_name = ""
    current_uid = ""
    idx = 0

    for line in out.splitlines():
        stripped = line.strip()
        if stripped.endswith(":") and not stripped.startswith("Unique ID"):
            if current_name and current_uid:
                cameras.append(
                    CameraInfo(
                        device=current_uid,
                        index=idx,
                        hardware_id=f"serial:{current_uid}" if current_uid else "",
                        name=current_name,
                    )
                )
                idx += 1
            current_name = stripped.rstrip(":")
            current_uid = ""
        uid_match = re.match(r"\s*Unique ID:\s*(.+)", line)
        if uid_match:
            current_uid = uid_match.group(1).strip()

    if current_name:
        cameras.append(
            CameraInfo(
                device=current_uid or str(idx),
                index=idx,
                hardware_id=f"serial:{current_uid}" if current_uid else "",
                name=current_name,
            )
        )

    return cameras


# ── Windows ──────────────────────────────────────────────────────────────────


def _scan_cameras_windows() -> list[CameraInfo]:
    """"""Scan cameras on Windows via pnputil.""""""
    try:
        out = subprocess.check_output(
            ["pnputil", "/enum-devices", "/class", "Camera", "/connected"],
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.debug("pnputil failed")
        return []

    cameras: list[CameraInfo] = []
    idx = 0
    current_iid = ""
    current_name = ""

    for line in out.splitlines():
        iid_match = re.match(r"\s*Instance ID:\s*(.+)", line)
        desc_match = re.match(r"\s*Device Description:\s*(.+)", line)

        if iid_match:
            if current_iid and current_name:
                hw_id = _windows_iid_to_hwid(current_iid)
                cameras.append(
                    CameraInfo(device=current_iid, index=idx, hardware_id=hw_id, name=current_name)
                )
                idx += 1
            current_iid = iid_match.group(1).strip()
            current_name = ""
        if desc_match:
            current_name = desc_match.group(1).strip()

    if current_iid and current_name:
        hw_id = _windows_iid_to_hwid(current_iid)
        cameras.append(
            CameraInfo(device=current_iid, index=idx, hardware_id=hw_id, name=current_name)
        )

    return cameras


def _windows_iid_to_hwid(iid: str) -> str:
    """"""Convert a Windows instance ID to a hardware fingerprint.""""""
    vid_match = re.search(r"VID_([0-9A-Fa-f]{4})", iid)
    pid_match = re.search(r"PID_([0-9A-Fa-f]{4})", iid)
    if vid_match and pid_match:
        parts = iid.split("\\")
        serial_part = parts[-1] if len(parts) >= 3 else ""
        tag = f"vidpid:{vid_match.group(1).lower()}:{pid_match.group(1).lower()}"
        if serial_part and not serial_part.startswith("&"):
            return f"serial:{serial_part}@{tag}"
        return tag
    return ""