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
""""""Tests for defty.platform — OS detection utilities.""""""

from __future__ import annotations

import platform
from unittest.mock import patch

import pytest

from defty.platform import OSType, detect_os, get_serial_glob_patterns


class TestDetectOs:
    """"""Tests for detect_os.""""""

    def test_returns_enum(self) -> None:
        """"""detect_os should return an OSType member.""""""
        result = detect_os()
        assert isinstance(result, OSType)

    @patch("defty.platform.platform.system", return_value="Linux")
    def test_linux(self, mock_sys) -> None:
        """"""Linux should be detected.""""""
        assert detect_os() == OSType.LINUX

    @patch("defty.platform.platform.system", return_value="Darwin")
    def test_macos(self, mock_sys) -> None:
        """"""macOS should be detected.""""""
        assert detect_os() == OSType.MACOS

    @patch("defty.platform.platform.system", return_value="Windows")
    def test_windows(self, mock_sys) -> None:
        """"""Windows should be detected.""""""
        assert detect_os() == OSType.WINDOWS

    @patch("defty.platform.platform.system", return_value="FreeBSD")
    def test_unsupported_raises(self, mock_sys) -> None:
        """"""Unsupported OS should raise RuntimeError.""""""
        with pytest.raises(RuntimeError, match="Unsupported"):
            detect_os()


class TestGetSerialGlobPatterns:
    """"""Tests for get_serial_glob_patterns.""""""

    def test_linux_patterns(self) -> None:
        """"""Linux should return ttyUSB and ttyACM patterns.""""""
        patterns = get_serial_glob_patterns(OSType.LINUX)
        assert any("ttyUSB" in p for p in patterns)
        assert any("ttyACM" in p for p in patterns)

    def test_windows_empty(self) -> None:
        """"""Windows uses registry, not glob — should return empty list.""""""
        patterns = get_serial_glob_patterns(OSType.WINDOWS)
        assert patterns == []