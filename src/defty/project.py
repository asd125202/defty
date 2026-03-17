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
""""""Defty project management — project.yaml CRUD operations.

A Defty project is a directory containing a `project.yaml` file.
This module provides helpers to initialise, load, save and query that file.
""""""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

__all__ = [
    "PROJECT_FILENAME",
    "init_project",
    "load_project",
    "save_project",
    "find_project_root",
]

PROJECT_FILENAME = "project.yaml"

_DEFAULT_PROJECT: dict[str, Any] = {
    "defty_version": "0.1.0",
    "project": {
        "name": "",
        "description": "",
    },
    "hardware": {
        "arms": [],
        "cameras": [],
    },
    "recording": {
        "fps": 30,
        "dataset_dir": "data",
    },
    "training": {},
}


def init_project(
    directory: str | Path,
    name: str | None = None,
    description: str = "",
) -> Path:
    """"""Create a new Defty project in *directory*.

    Creates the directory (including parents) if it does not exist, writes a
    default `project.yaml`, and returns the path to the file.

    Args:
        directory: Path to the project root.
        name: Human-readable project name. Defaults to the directory name.
        description: Optional one-liner.

    Returns:
        Path to the created `project.yaml`.

    Raises:
        FileExistsError: If `project.yaml` already exists in *directory*.
    """"""
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)

    yaml_path = root / PROJECT_FILENAME
    if yaml_path.exists():
        msg = f"Project already exists: {yaml_path}"
        raise FileExistsError(msg)

    data = _deep_copy_default()
    data["project"]["name"] = name or root.name
    data["project"]["description"] = description

    save_project(yaml_path, data)
    logger.info("Initialised project at %s", yaml_path)
    return yaml_path


def load_project(path: str | Path | None = None) -> dict[str, Any]:
    """"""Load a `project.yaml` from disk.

    Args:
        path: Explicit path to project.yaml **or** a directory that contains
              one.  When *None*, searches upward from the cwd.

    Returns:
        The parsed YAML as a dict.

    Raises:
        FileNotFoundError: If no project.yaml can be located.
    """"""
    if path is None:
        yaml_path = find_project_root()
    else:
        p = Path(path)
        yaml_path = p if p.name == PROJECT_FILENAME else p / PROJECT_FILENAME

    if not yaml_path.exists():
        msg = f"project.yaml not found at {yaml_path}"
        raise FileNotFoundError(msg)

    with open(yaml_path, encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}

    logger.debug("Loaded project from %s", yaml_path)
    return data


def save_project(path: str | Path, data: dict[str, Any]) -> None:
    """"""Write *data* to a `project.yaml` file.

    Args:
        path: Destination file path.
        data: The project dict to serialise.
    """"""
    p = Path(path)
    with open(p, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
    logger.debug("Saved project to %s", p)


def find_project_root(start: str | Path | None = None) -> Path:
    """"""Walk upward from *start* until a `project.yaml` is found.

    Args:
        start: Starting directory.  Defaults to the current working directory.

    Returns:
        Absolute path to the discovered `project.yaml`.

    Raises:
        FileNotFoundError: If no `project.yaml` is found.
    """"""
    current = Path(start or Path.cwd()).resolve()
    while True:
        candidate = current / PROJECT_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    msg = "No project.yaml found (searched upward from working directory)"
    raise FileNotFoundError(msg)


# ── helpers ──────────────────────────────────────────────────────────────────


def _deep_copy_default() -> dict[str, Any]:
    """"""Return a deep copy of the default project template.""""""
    import copy

    return copy.deepcopy(_DEFAULT_PROJECT)