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
"""Cross-platform utilities for Defty.

Provides OS detection and platform-specific helpers that are used
throughout the Defty codebase to ensure consistent behavior on
Linux, macOS, and Windows.
"""

from __future__ import annotations

import logging
import platform
import sys
from enum import Enum

logger = logging.getLogger(__name__)

__all__ = ["OSType", "detect_os", "get_serial_glob_patterns"]


class OSType(Enum):
    """Supported operating systems."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


def detect_os() -> OSType:
    """Detect the current operating system.

    Returns:
        OSType: The detected operating system.

    Raises:
        RuntimeError: If the operating system is not supported.
    """
    system = platform.system().lower()
    if system == "linux":
        return OSType.LINUX
    if system == "darwin":
        return OSType.MACOS
    if system == "windows":
        return OSType.WINDOWS
    msg = f"Unsupported operating system: {platform.system()}"
    raise RuntimeError(msg)


def get_serial_glob_patterns(os_type: OSType | None = None) -> list[str]:
    """Return glob patterns for serial ports on the current platform.

    Args:
        os_type: Override the OS type. If None, detects automatically.

    Returns:
        A list of glob patterns that match serial port device files.
    """
    if os_type is None:
        os_type = detect_os()

    patterns: dict[OSType, list[str]] = {
        OSType.LINUX: ["/dev/ttyUSB*", "/dev/ttyACM*"],
        OSType.MACOS: ["/dev/tty.usb*", "/dev/cu.usb*"],
        OSType.WINDOWS: [],  # Windows uses COM ports via registry, not glob
    }
    return patterns[os_type]