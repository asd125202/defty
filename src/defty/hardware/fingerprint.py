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
""""""Cross-platform hardware fingerprinting for USB devices.

Generates stable identifiers for serial adapters and cameras so that
Defty can re-associate hardware even when OS-assigned port names change
between reboots or re-plugging.

Inspired by the `udevadm`-based approach in the Pineapple project, but
implemented on top of `pyserial` and platform-native APIs so it works on
Linux, macOS **and** Windows.

Priority chain (serial devices — via `pyserial` `ListPortInfo`):
  1. `serial:<serial_number>@<location>` — best: globally unique
  2. `serial:<serial_number>`            — good when location unavailable
  3. `vidpid:<vid>:<pid>@<location>`     — usable when serial is absent
  4. `vidpid:<vid>:<pid>`                — weak but still better than nothing
  5. `None`                              — device is not identifiable

For cameras the strategy depends on the platform:
  - Linux:  `udevadm info` → `ID_SERIAL` + `ID_PATH`  (same as Pineapple)
  - macOS:  `system_profiler SPCameraDataType` → unique-id
  - Windows: `wmic path Win32_PnPEntity` or device instance path
""""""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Any

from serial.tools.list_ports_common import ListPortInfo

logger = logging.getLogger(__name__)

__all__ = [
    "resolve_hardware_id",
    "resolve_hardware_info",
    "resolve_camera_hardware_id",
    "HardwareInfo",
]


@dataclass(frozen=True)
class HardwareInfo:
    """"""Resolved hardware information for a device.""""""

    hardware_id: str
    vendor: str
    model: str
    serial: str
    location: str


# ── Serial device fingerprinting (pyserial, cross-platform) ─────────────────


def resolve_hardware_id(port_info: ListPortInfo) -> str | None:
    """"""Build a stable hardware identifier from a pyserial `ListPortInfo`.

    Args:
        port_info: A `ListPortInfo` object returned by
                   `serial.tools.list_ports.comports()`.

    Returns:
        A fingerprint string, or *None* if the device cannot be identified.
    """"""
    serial = port_info.serial_number or ""
    location = port_info.location or ""
    vid = port_info.vid
    pid = port_info.pid

    if serial:
        tag = f"serial:{serial}"
        if location:
            return f"{tag}@{location}"
        return tag

    if vid is not None and pid is not None:
        tag = f"vidpid:{vid:04x}:{pid:04x}"
        if location:
            return f"{tag}@{location}"
        return tag

    return None


def resolve_hardware_info(port_info: ListPortInfo) -> HardwareInfo:
    """"""Extract detailed hardware info from a `ListPortInfo`.

    Args:
        port_info: A `ListPortInfo` from `comports()`.

    Returns:
        A `HardwareInfo` dataclass with all available metadata.
    """"""
    return HardwareInfo(
        hardware_id=resolve_hardware_id(port_info) or "",
        vendor=port_info.manufacturer or "",
        model=port_info.product or "",
        serial=port_info.serial_number or "",
        location=port_info.location or "",
    )


# ── Camera fingerprinting (platform-specific) ───────────────────────────────


def resolve_camera_hardware_id(device_path: str | int) -> str | None:
    """"""Build a stable hardware identifier for a camera device.

    On Linux, queries `udevadm info`.  On macOS, uses
    `system_profiler`.  On Windows, uses WMI device instance paths.

    Args:
        device_path: The OS camera path or index (`/dev/video0`, `0`,
                     `COM3`, etc.).

    Returns:
        A fingerprint string, or *None*.
    """"""
    system = platform.system()
    if system == "Linux":
        return _camera_id_linux(str(device_path))
    if system == "Darwin":
        return _camera_id_macos(str(device_path))
    if system == "Windows":
        return _camera_id_windows(str(device_path))
    return None


def resolve_camera_hardware_info(device_path: str | int) -> dict[str, str]:
    """"""Return a dict of camera metadata (hardware_id, vendor, model, serial).

    Args:
        device_path: The camera device path or index.

    Returns:
        A dict with keys `hardware_id`, `vendor`, `model`, `serial`.
    """"""
    system = platform.system()
    if system == "Linux":
        return _camera_info_linux(str(device_path))
    return {
        "hardware_id": resolve_camera_hardware_id(device_path) or "",
        "vendor": "",
        "model": "",
        "serial": "",
    }


# ── Linux camera helpers (udevadm) ──────────────────────────────────────────


def _udevadm_props(device: str) -> dict[str, str]:
    """"""Query udevadm for device properties.

    Args:
        device: Device path such as `/dev/video0`.

    Returns:
        A dict of `KEY=value` pairs from `udevadm info`.
    """"""
    try:
        out = subprocess.check_output(
            ["udevadm", "info", "--query=property", "--name", device],
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.debug("udevadm not available or failed for %s", device)
        return {}

    props: dict[str, str] = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            props[k.strip()] = v.strip()
    return props


def _camera_id_linux(device: str) -> str | None:
    """"""Resolve camera hardware ID on Linux via udevadm.""""""
    props = _udevadm_props(device)
    serial = props.get("ID_SERIAL")
    path = props.get("ID_PATH")

    if serial and path:
        return f"serial:{serial}@{path}"
    if serial:
        return f"serial:{serial}"

    vid = props.get("ID_VENDOR_ID")
    pid = props.get("ID_MODEL_ID")
    if vid and pid:
        tag = f"vidpid:{vid}:{pid}"
        return f"{tag}@{path}" if path else tag

    if path:
        return f"path:{path}"
    return None


def _camera_info_linux(device: str) -> dict[str, str]:
    """"""Get camera metadata on Linux.""""""
    props = _udevadm_props(device)
    return {
        "hardware_id": _camera_id_linux(device) or "",
        "vendor": props.get("ID_VENDOR", ""),
        "model": props.get("ID_MODEL", ""),
        "serial": props.get("ID_SERIAL_SHORT", ""),
    }


# ── macOS camera helpers ────────────────────────────────────────────────────


def _camera_id_macos(device: str) -> str | None:
    """"""Resolve camera hardware ID on macOS via system_profiler.""""""
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPCameraDataType"],
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.debug("system_profiler not available or failed")
        return None

    uid_match = re.search(r"Unique ID:\s*(.+)", out)
    if uid_match:
        return f"serial:{uid_match.group(1).strip()}"
    return None


# ── Windows camera helpers ──────────────────────────────────────────────────


def _camera_id_windows(device: str) -> str | None:
    """"""Resolve camera hardware ID on Windows.

    Uses `pnputil` or the device instance path from the registry.
    This is a best-effort approach — many USB cameras on Windows expose
    a device instance path like `USB\\VID_xxxx&PID_xxxx\\serial`.
    """"""
    try:
        out = subprocess.check_output(
            ["pnputil", "/enum-devices", "/class", "Camera", "/connected"],
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.debug("pnputil not available or failed")
        return None

    instance_ids = re.findall(r"Instance ID:\s*(.+)", out)
    for iid in instance_ids:
        iid = iid.strip()
        vid_match = re.search(r"VID_([0-9A-Fa-f]{4})", iid)
        pid_match = re.search(r"PID_([0-9A-Fa-f]{4})", iid)
        if vid_match and pid_match:
            parts = iid.split("\\\\")
            serial_part = parts[-1] if len(parts) >= 3 else ""
            tag = f"vidpid:{vid_match.group(1).lower()}:{pid_match.group(1).lower()}"
            if serial_part and not serial_part.startswith("&"):
                return f"serial:{serial_part}@{tag}"
            return tag
    return None