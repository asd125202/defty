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
""""""Wrap LeRobot's training pipeline.

Reads the Defty `project.yaml` training section, constructs the
appropriate LeRobot `TrainConfig`, and delegates to
`lerobot.scripts.lerobot_train`.
""""""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from defty.project import load_project

logger = logging.getLogger(__name__)

__all__ = ["train"]


def train(
    project_path: str | Path | None = None,
    *,
    policy: str = "act",
    dataset_name: str | None = None,
    output_dir: str | None = None,
    num_epochs: int | None = None,
    batch_size: int | None = None,
    learning_rate: float | None = None,
    push_to_hub: bool = False,
) -> None:
    """"""Train a policy using LeRobot.

    Reads configuration from `project.yaml`, merges with any explicit
    overrides, and delegates to LeRobot's training entry point.

    Args:
        project_path: Path to `project.yaml` or its parent directory.
        policy: Policy architecture name (e.g. `act`, `diffusion`).
        dataset_name: Override the dataset name from project config.
        output_dir: Override the output directory for checkpoints.
        num_epochs: Override the number of training epochs.
        batch_size: Override the batch size.
        learning_rate: Override the learning rate.
        push_to_hub: Push trained model to HuggingFace Hub.

    Raises:
        FileNotFoundError: If no `project.yaml` can be found.
        RuntimeError: If LeRobot is not installed.
    """"""
    project = load_project(project_path)
    proj_name = project.get("project", {}).get("name", "defty_project")

    train_cfg = project.get("training", {})
    rec_cfg = project.get("recording", {})

    ds_name = dataset_name or f"{proj_name}_dataset"
    dataset_dir = rec_cfg.get("dataset_dir", "data")
    out_dir = output_dir or train_cfg.get("output_dir", "outputs")

    epochs = num_epochs or train_cfg.get("num_epochs")
    bs = batch_size or train_cfg.get("batch_size")
    lr = learning_rate or train_cfg.get("learning_rate")

    logger.info(
        "Training policy='%s' on dataset='%s' -> '%s'",
        policy,
        ds_name,
        out_dir,
    )

    _invoke_lerobot_train(
        policy=policy,
        dataset_name=ds_name,
        dataset_dir=dataset_dir,
        output_dir=out_dir,
        num_epochs=epochs,
        batch_size=bs,
        learning_rate=lr,
        push_to_hub=push_to_hub,
    )


def _invoke_lerobot_train(
    *,
    policy: str,
    dataset_name: str,
    dataset_dir: str,
    output_dir: str,
    num_epochs: int | None,
    batch_size: int | None,
    learning_rate: float | None,
    push_to_hub: bool,
) -> None:
    """"""Construct LeRobot train config and call the training pipeline.""""""
    try:
        from lerobot.scripts.lerobot_train import train as lerobot_train
    except ImportError as exc:
        msg = "LeRobot is not installed. Run: pip install 'defty[dev]'"
        raise RuntimeError(msg) from exc

    overrides: list[str] = [
        f"policy={policy}",
        f"dataset.repo_id={dataset_name}",
        f"dataset.root={dataset_dir}",
        f"output_dir={output_dir}",
    ]

    if num_epochs is not None:
        overrides.append(f"num_epochs={num_epochs}")
    if batch_size is not None:
        overrides.append(f"batch_size={batch_size}")
    if learning_rate is not None:
        overrides.append(f"lr={learning_rate}")
    if push_to_hub:
        overrides.append("push_to_hub=true")

    logger.info("LeRobot train overrides: %s", overrides)

    try:
        lerobot_train(overrides=overrides)
    except TypeError:
        logger.error(
            "LeRobot train API signature may have changed. "
            "Please check LeRobot >= 0.5.1 compatibility."
        )
        raise