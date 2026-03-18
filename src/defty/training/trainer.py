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
import os
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
        policy: Policy architecture name — any model supported by LeRobot
                (e.g. ``act``, ``diffusion``, ``pi0``, ``pi0_fast``, ``smolvla``, …).
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

    # Resolve model output directory — auto-increment until we find a free slot
    # (lerobot raises FileExistsError if output_dir already exists and resume=False)
    if model_name is None:
        model_name = _auto_model_name(models_dir, f"{policy}_{dataset_name}")
    else:
        # Explicit name: still check and increment if already taken
        if (models_dir / model_name).exists():
            model_name = _auto_model_name(models_dir, model_name)
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

    # Authenticate with Hugging Face so gated model downloads succeed.
    # The token is read from (in priority order):
    #   1. HF_TOKEN env var  2. ~/.defty/config.yaml  3. HF CLI cache
    try:
        from defty.cloud.config import get_hf_token

        _hf_token = get_hf_token()
        if _hf_token:
            os.environ["HF_TOKEN"] = _hf_token
            try:
                from huggingface_hub import login as hf_login
                hf_login(token=_hf_token, add_to_git_credential=False)
                logger.info("Authenticated with Hugging Face for model downloads")
            except Exception as exc:
                logger.debug("huggingface_hub.login() failed: %s", exc)
        else:
            logger.debug("No HF token found; gated models may be inaccessible")
    except ImportError:
        logger.debug("defty.cloud.config not available; skipping HF auth")

    # Build config
    dataset_cfg = DatasetConfig(
        repo_id=repo_id,
        root=str(dataset_root),
    )

    # Build kwargs for TrainPipelineConfig
    train_kwargs: dict[str, Any] = {
        "dataset": dataset_cfg,
        "output_dir": model_output,
        "steps": steps if steps is not None else 10_000,  # default 10k (lerobot default is 100k)
    }
    if batch_size is not None:
        train_kwargs["batch_size"] = batch_size

    cfg = TrainPipelineConfig(**train_kwargs)

    # Set policy type via the config's policy field
    # lerobot resolves policy from type string
    try:
        from lerobot.policies.factory import make_policy_config

        policy_inst = make_policy_config(policy.lower())
        import torch as _torch
        policy_inst.push_to_hub = False
        # Auto-select best available device; installer sets up the right torch wheel
        # but guard here too in case of manual installs
        if hasattr(policy_inst, "device"):
            if _torch.cuda.is_available():
                policy_inst.device = "cuda"
            elif getattr(_torch.backends, "mps", None) and _torch.backends.mps.is_available():
                policy_inst.device = "mps"
            else:
                policy_inst.device = "cpu"
            logger.info("Training device: %s", policy_inst.device)
        cfg.policy = policy_inst
    except ValueError as exc:
        raise RuntimeError(f"Unknown policy: {policy}. {exc}") from exc
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

    meta = {
        "policy": policy,
        "dataset": dataset_name,
        "steps": steps or 10_000,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "project": proj_name,
    }

    try:
        lerobot_train(cfg)
    except OSError as exc:
        # Windows symlink error (WinError 1314) — training completed but
        # lerobot failed to create a "last" checkpoint symlink.  Not fatal.
        if "1314" in str(exc) or "privilege" in str(exc).lower():
            logger.warning(
                "Training completed but checkpoint symlink failed "
                "(Windows admin privileges required for symlinks). "
                "This does not affect the trained model."
            )
        else:
            raise
    except TypeError:
        logger.error(
            "LeRobot train API signature may have changed. "
            "Please check LeRobot compatibility."
        )
        raise

    # Write defty metadata AFTER training so lerobot's dir-existence check passes
    try:
        (model_output / "defty_model_info.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write defty_model_info.json: %s", exc)

    logger.info("Training complete. Model saved to: %s", model_output)