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
"""Wrap LeRobot's training pipeline.

Reads the Defty ``project.yaml`` training section, resolves dataset and
model paths, constructs the appropriate LeRobot ``TrainPipelineConfig``,
and delegates to ``lerobot.scripts.lerobot_train``.

Models are stored under ``models/<name>/`` in the project directory so
multiple experiments can coexist.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from defty.project import find_project_root, load_project
from defty.recording.recorder import _auto_dataset_name, _latest_dataset

logger = logging.getLogger(__name__)

__all__ = ["train"]


def _auto_model_name(models_dir: Path, base: str) -> str:
    """Return the next free numbered model name: ``base_001``, ``base_002``, …"""
    existing: set[str] = set()
    if models_dir.exists():
        existing = {p.name for p in models_dir.iterdir() if p.is_dir()}
    for i in range(1, 10_000):
        candidate = f"{base}_{i:03d}"
        if candidate not in existing:
            return candidate
    import time
    return f"{base}_{int(time.time())}"


def train(
    project_path: str | Path | None = None,
    *,
    policy: str = "act",
    dataset_name: str | None = None,
    model_name: str | None = None,
    steps: int | None = None,
    batch_size: int | None = None,
    learning_rate: float | None = None,
    push_to_hub: bool = False,
) -> None:
    """Train a policy using LeRobot.

    Reads configuration from ``project.yaml``, resolves the dataset and
    model output paths, then calls LeRobot's training pipeline directly.

    Args:
        project_path: Path to ``project.yaml`` or its parent directory.
        policy: Policy architecture name (``act``, ``diffusion``, ``tdmpc``, ``vqbet``).
        dataset_name: Dataset name from ``data/``.  Auto-selects latest if *None*.
        model_name: Name for the output model directory under ``models/``.
                    Auto-numbered if *None*.
        steps: Total training steps (default: lerobot default 100k).
        batch_size: Override the batch size.
        learning_rate: Override the learning rate.
        push_to_hub: Push trained model to HuggingFace Hub.

    Raises:
        FileNotFoundError: If no ``project.yaml`` can be found.
        RuntimeError: If LeRobot is not installed or dataset is missing.
    """
    # Resolve project
    if project_path is not None:
        p = Path(project_path)
        yaml_path = p if p.name == "project.yaml" else p / "project.yaml"
    else:
        yaml_path = find_project_root()

    project = load_project(yaml_path)
    proj_name = project.get("project", {}).get("name", "defty_project")

    data_dir = yaml_path.parent / "data"
    models_dir = yaml_path.parent / "models"

    # Resolve dataset
    if dataset_name is None:
        dataset_name = _latest_dataset(data_dir)
        if dataset_name is None:
            raise RuntimeError(
                "No recorded datasets found. Run 'defty record' first."
            )
        logger.info("Auto-selected latest dataset: %s", dataset_name)

    dataset_root = data_dir / dataset_name
    if not dataset_root.exists() or not (dataset_root / "meta" / "info.json").exists():
        raise RuntimeError(
            f"Dataset '{dataset_name}' not found or incomplete. "
            "Run 'defty datasets' to see available datasets."
        )

    # Resolve model output directory
    if model_name is None:
        model_name = _auto_model_name(models_dir, f"{policy}_{dataset_name}")
    model_output = models_dir / model_name

    repo_id = f"local/{dataset_name}"

    logger.info(
        "Training policy='%s' on dataset='%s' -> models/%s",
        policy, dataset_name, model_name,
    )

    try:
        from lerobot.scripts.lerobot_train import train as lerobot_train
        from lerobot.configs.default import DatasetConfig
        from lerobot.configs.train import TrainPipelineConfig
    except ImportError as exc:
        raise RuntimeError(f"LeRobot not available: {exc}") from exc

    # Build config
    dataset_cfg = DatasetConfig(
        repo_id=repo_id,
        root=str(dataset_root),
    )

    # Build kwargs for TrainPipelineConfig
    train_kwargs: dict[str, Any] = {
        "dataset": dataset_cfg,
        "output_dir": model_output,
    }
    if steps is not None:
        train_kwargs["steps"] = steps
    if batch_size is not None:
        train_kwargs["batch_size"] = batch_size

    cfg = TrainPipelineConfig(**train_kwargs)

    # Set policy type via the config's policy field
    # lerobot resolves policy from type string
    try:
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.diffusion.configuration_diffusion import DiffusionConfig
        from lerobot.policies.tdmpc.configuration_tdmpc import TDMPCConfig
        from lerobot.policies.vqbet.configuration_vqbet import VQBeTConfig

        policy_map = {
            "act": ACTConfig,
            "diffusion": DiffusionConfig,
            "tdmpc": TDMPCConfig,
            "vqbet": VQBeTConfig,
        }
        policy_cls = policy_map.get(policy.lower())
        if policy_cls is not None:
            cfg.policy = policy_cls()
        else:
            raise RuntimeError(f"Unknown policy: {policy}")
    except ImportError as exc:
        raise RuntimeError(f"Policy '{policy}' not available: {exc}") from exc

    if learning_rate is not None:
        # Learning rate is set via optimizer config
        try:
            from lerobot.configs.train import OptimizerConfig
            cfg.optimizer = OptimizerConfig(lr=learning_rate)
            cfg.use_policy_training_preset = False
        except (ImportError, TypeError):
            logger.warning("Could not set custom learning rate; using policy default.")

    if push_to_hub:
        cfg.policy.push_to_hub = True

    # Write defty model metadata before training starts
    model_output.mkdir(parents=True, exist_ok=True)
    meta = {
        "policy": policy,
        "dataset": dataset_name,
        "steps": steps or 100_000,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "project": proj_name,
    }
    (model_output / "defty_model_info.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    try:
        lerobot_train(cfg)
    except TypeError:
        logger.error(
            "LeRobot train API signature may have changed. "
            "Please check LeRobot compatibility."
        )
        raise

    logger.info("Training complete. Model saved to: %s", model_output)