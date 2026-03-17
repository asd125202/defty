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
""""""Tests for defty.project — project.yaml CRUD.""""""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from defty.project import (
    PROJECT_FILENAME,
    find_project_root,
    init_project,
    load_project,
    save_project,
)


class TestInitProject:
    """"""Tests for init_project.""""""

    def test_creates_project_yaml(self, tmp_path: Path) -> None:
        """"""init_project should create a project.yaml file.""""""
        yaml_path = init_project(tmp_path, name="test-project")
        assert yaml_path.exists()
        assert yaml_path.name == PROJECT_FILENAME

    def test_default_name_is_dirname(self, tmp_path: Path) -> None:
        """"""When name is None, use the directory name.""""""
        init_project(tmp_path)
        data = load_project(tmp_path)
        assert data["project"]["name"] == tmp_path.name

    def test_custom_name(self, tmp_path: Path) -> None:
        """"""Explicit name should be stored.""""""
        init_project(tmp_path, name="my-robot")
        data = load_project(tmp_path)
        assert data["project"]["name"] == "my-robot"

    def test_raises_if_exists(self, tmp_path: Path) -> None:
        """"""Should raise FileExistsError if project.yaml already exists.""""""
        init_project(tmp_path)
        with pytest.raises(FileExistsError):
            init_project(tmp_path)

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """"""Should create parent directories as needed.""""""
        nested = tmp_path / "a" / "b" / "c"
        yaml_path = init_project(nested)
        assert yaml_path.exists()

    def test_default_structure(self, tmp_path: Path) -> None:
        """"""Default project should have hardware section with empty arms/cameras.""""""
        init_project(tmp_path)
        data = load_project(tmp_path)
        assert "hardware" in data
        assert data["hardware"]["arms"] == []
        assert data["hardware"]["cameras"] == []


class TestLoadSaveProject:
    """"""Tests for load_project and save_project.""""""

    def test_round_trip(self, tmp_path: Path) -> None:
        """"""Save then load should return the same data.""""""
        data = {"project": {"name": "roundtrip"}, "hardware": {"arms": [], "cameras": []}}
        yaml_path = tmp_path / PROJECT_FILENAME
        save_project(yaml_path, data)
        loaded = load_project(yaml_path)
        assert loaded["project"]["name"] == "roundtrip"

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        """"""Loading from a path with no project.yaml should raise.""""""
        with pytest.raises(FileNotFoundError):
            load_project(tmp_path / "nonexistent")


class TestFindProjectRoot:
    """"""Tests for find_project_root.""""""

    def test_finds_in_current_dir(self, tmp_path: Path) -> None:
        """"""Should find project.yaml in the given directory.""""""
        init_project(tmp_path)
        found = find_project_root(tmp_path)
        assert found == tmp_path / PROJECT_FILENAME

    def test_finds_in_parent(self, tmp_path: Path) -> None:
        """"""Should walk upward and find project.yaml.""""""
        init_project(tmp_path)
        child = tmp_path / "subdir"
        child.mkdir()
        found = find_project_root(child)
        assert found == tmp_path / PROJECT_FILENAME

    def test_raises_if_not_found(self, tmp_path: Path) -> None:
        """"""Should raise FileNotFoundError if no project.yaml anywhere.""""""
        with pytest.raises(FileNotFoundError):
            find_project_root(tmp_path)