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
"""Defty hardware management — detection, registration, and health checks."""

from defty.hardware.detector import list_cameras, list_serial_ports
from defty.hardware.fingerprint import resolve_hardware_id, resolve_hardware_info
from defty.hardware.registry import add_arm, add_camera, remove_arm, remove_camera, update_ports

__all__ = [
    "list_serial_ports",
    "list_cameras",
    "resolve_hardware_id",
    "resolve_hardware_info",
    "add_arm",
    "add_camera",
    "remove_arm",
    "remove_camera",
    "update_ports",
]