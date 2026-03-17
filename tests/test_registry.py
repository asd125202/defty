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
""""""Tests for defty.hardware.registry — hardware registration.""""""

from __future__ import annotations

import pytest

from defty.hardware.registry import (
    add_arm,
    add_camera,
    generate_arm_id,
    generate_camera_id,
    remove_arm,
    remove_camera,
)


def _empty_project() -> dict:
    """"""Return a minimal project dict.""""""
    return {"hardware": {"arms": [], "cameras": []}}


class TestGenerateArmId:
    """"""Tests for generate_arm_id.""""""

    def test_first_id(self) -> None:
        """"""First arm should be _1.""""""
        p = _empty_project()
        assert generate_arm_id(p) == "so101_follower_1"

    def test_increments(self) -> None:
        """"""Second arm should be _2.""""""
        p = _empty_project()
        add_arm(p, arm_id="so101_follower_1", port="/dev/ttyACM0", role="follower")
        assert generate_arm_id(p) == "so101_follower_2"

    def test_leader_role(self) -> None:
        """"""Leader role should appear in the ID.""""""
        p = _empty_project()
        assert generate_arm_id(p, role="leader") == "so101_leader_1"


class TestGenerateCameraId:
    """"""Tests for generate_camera_id.""""""

    def test_default_id(self) -> None:
        """"""Default should be cam_0.""""""
        p = _empty_project()
        assert generate_camera_id(p) == "cam_0"

    def test_with_position(self) -> None:
        """"""Position should be slugified.""""""
        p = _empty_project()
        assert generate_camera_id(p, position="wrist") == "cam_wrist"


class TestAddRemoveArm:
    """"""Tests for add_arm and remove_arm.""""""

    def test_add_arm(self) -> None:
        """"""Adding an arm should appear in the arms list.""""""
        p = _empty_project()
        add_arm(p, port="/dev/ttyACM0", role="follower")
        assert len(p["hardware"]["arms"]) == 1
        assert p["hardware"]["arms"][0]["role"] == "follower"

    def test_add_duplicate_raises(self) -> None:
        """"""Adding an arm with the same ID should raise.""""""
        p = _empty_project()
        add_arm(p, arm_id="arm1", port="/dev/ttyACM0", role="follower")
        with pytest.raises(ValueError):
            add_arm(p, arm_id="arm1", port="/dev/ttyACM1", role="leader")

    def test_remove_arm(self) -> None:
        """"""Removing an arm should remove it from the list.""""""
        p = _empty_project()
        add_arm(p, arm_id="arm1", port="/dev/ttyACM0", role="follower")
        remove_arm(p, "arm1")
        assert len(p["hardware"]["arms"]) == 0

    def test_remove_missing_raises(self) -> None:
        """"""Removing a non-existent arm should raise KeyError.""""""
        p = _empty_project()
        with pytest.raises(KeyError):
            remove_arm(p, "nonexistent")


class TestAddRemoveCamera:
    """"""Tests for add_camera and remove_camera.""""""

    def test_add_camera(self) -> None:
        """"""Adding a camera should appear in the cameras list.""""""
        p = _empty_project()
        add_camera(p, device="/dev/video0", position="overhead")
        assert len(p["hardware"]["cameras"]) == 1
        assert p["hardware"]["cameras"][0]["position"] == "overhead"

    def test_add_duplicate_raises(self) -> None:
        """"""Adding a camera with the same ID should raise.""""""
        p = _empty_project()
        add_camera(p, camera_id="cam1", device="/dev/video0")
        with pytest.raises(ValueError):
            add_camera(p, camera_id="cam1", device="/dev/video2")

    def test_remove_camera(self) -> None:
        """"""Removing a camera should remove it from the list.""""""
        p = _empty_project()
        add_camera(p, camera_id="cam1", device="/dev/video0")
        remove_camera(p, "cam1")
        assert len(p["hardware"]["cameras"]) == 0