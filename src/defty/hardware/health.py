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
"""Hardware health checks — motor-level ping and camera connectivity.

Provides non-interactive health diagnostics for arms and cameras.
Used by `defty health` to verify that every registered device is
reachable and functioning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "ArmHealthReport",
    "CameraHealthReport",
    "HealthReport",
    "check_arm_health",
    "check_camera_health",
    "check_all_health",
]


@dataclass
class MotorStatus:
    """Health status of a single motor."""

    motor_id: int
    name: str
    online: bool
    model_number: int | None = None
    error: str = ""


@dataclass
class ArmHealthReport:
    """Health report for a single robot arm."""

    arm_id: str
    port: str
    reachable: bool
    motors: list[MotorStatus] = field(default_factory=list)
    error: str = ""

    @property
    def all_motors_ok(self) -> bool:
        """True if every motor is online."""
        return self.reachable and all(m.online for m in self.motors)


@dataclass
class CameraHealthReport:
    """Health report for a single camera."""

    camera_id: str
    device: str
    online: bool
    error: str = ""


@dataclass
class HealthReport:
    """Aggregate health report for all hardware."""

    arms: list[ArmHealthReport] = field(default_factory=list)
    cameras: list[CameraHealthReport] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        """True if every device passes health check."""
        arms_ok = all(a.all_motors_ok for a in self.arms)
        cams_ok = all(c.online for c in self.cameras)
        return arms_ok and cams_ok


# ── SO-101 motor names (Feetech STS3215, IDs 1-6) ───────────────────────────

SO101_MOTOR_NAMES: dict[int, str] = {
    1: "shoulder_pan",
    2: "shoulder_lift",
    3: "elbow_flex",
    4: "wrist_flex",
    5: "wrist_roll",
    6: "gripper",
}


def check_arm_health(arm_config: dict[str, Any]) -> ArmHealthReport:
    """Ping every motor on a robot arm and report status.

    Opens the serial port, sends a broadcast ping via the Feetech
    protocol (through LeRobot's `FeetechMotorsBus`), and checks that
    all expected motor IDs respond.

    Args:
        arm_config: A single arm entry from `project.yaml`, containing
                    at least `id`, `port`, and `robot_type`.

    Returns:
        An `ArmHealthReport` with per-motor status.
    """
    arm_id = arm_config.get("id", "unknown")
    port = arm_config.get("port", "")
    robot_type = arm_config.get("robot_type", "so101")

    if not port:
        return ArmHealthReport(arm_id=arm_id, port="", reachable=False, error="No port configured")

    try:
        from lerobot.motors.feetech import FeetechMotorsBus

        bus = FeetechMotorsBus(port=port)
        bus.connect()
    except Exception as exc:
        logger.warning("Cannot open serial port %s: %s", port, exc)
        return ArmHealthReport(arm_id=arm_id, port=port, reachable=False, error=str(exc))

    motor_names = SO101_MOTOR_NAMES if robot_type == "so101" else {i: f"motor_{i}" for i in range(1, 7)}

    motors: list[MotorStatus] = []
    try:
        ping_result = bus.broadcast_ping()
        found_ids = set(ping_result.keys()) if ping_result else set()

        for mid, name in motor_names.items():
            if mid in found_ids:
                motors.append(MotorStatus(motor_id=mid, name=name, online=True, model_number=ping_result.get(mid)))
            else:
                motors.append(MotorStatus(motor_id=mid, name=name, online=False, error="No response"))
    except Exception as exc:
        logger.warning("Broadcast ping failed on %s: %s", port, exc)
        return ArmHealthReport(arm_id=arm_id, port=port, reachable=True, error=str(exc))
    finally:
        try:
            bus.disconnect()
        except Exception:
            pass

    return ArmHealthReport(arm_id=arm_id, port=port, reachable=True, motors=motors)


def check_camera_health(camera_config: dict[str, Any]) -> CameraHealthReport:
    """Check whether a camera is online and can capture a frame.

    Uses OpenCV to open the device and attempt a single frame grab.

    Args:
        camera_config: A single camera entry from `project.yaml`,
                       containing at least `id` and `device`.

    Returns:
        A `CameraHealthReport`.
    """
    camera_id = camera_config.get("id", "unknown")
    device = camera_config.get("device", "")

    if not device:
        return CameraHealthReport(camera_id=camera_id, device="", online=False, error="No device configured")

    try:
        import cv2

        dev_arg: int | str = int(device) if device.isdigit() else device
        # MSMF (Media Foundation) handles index-based access reliably on
        # modern Windows; CAP_ANY may try the obsensor UVC driver first
        # and fail for standard USB cameras.
        import platform as _plat

        backend = cv2.CAP_MSMF if _plat.system() == "Windows" else cv2.CAP_ANY
        cap = cv2.VideoCapture(dev_arg, backend)
        if not cap.isOpened():
            return CameraHealthReport(camera_id=camera_id, device=device, online=False, error="Cannot open device")

        ret, _ = cap.read()
        cap.release()

        if not ret:
            return CameraHealthReport(camera_id=camera_id, device=device, online=False, error="Frame grab failed")

        return CameraHealthReport(camera_id=camera_id, device=device, online=True)
    except ImportError:
        return CameraHealthReport(
            camera_id=camera_id, device=device, online=False, error="opencv-python not installed"
        )
    except Exception as exc:
        return CameraHealthReport(camera_id=camera_id, device=device, online=False, error=str(exc))


def check_all_health(project: dict[str, Any]) -> HealthReport:
    """Run health checks on all registered arms and cameras.

    Args:
        project: The loaded project dict.

    Returns:
        An aggregate `HealthReport`.
    """
    report = HealthReport()

    for arm in project.get("hardware", {}).get("arms", []):
        report.arms.append(check_arm_health(arm))

    for cam in project.get("hardware", {}).get("cameras", []):
        report.cameras.append(check_camera_health(cam))

    return report