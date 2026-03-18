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
import sys
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


def _find_latest_checkpoint(model_dir: Path) -> tuple[Path, Path]:
    """Return ``(checkpoint_step_dir, pretrained_model_dir)`` for the latest checkpoint.

    Args:
        model_dir: Top-level model directory (e.g. ``models/act_test_012_001``).

    Returns:
        A tuple of ``(step_dir, pretrained_model_dir)`` where ``step_dir`` is the
        numeric checkpoint directory (e.g. ``checkpoints/001234``) and
        ``pretrained_model_dir`` is the ``pretrained_model`` sub-directory.

    Raises:
        FileNotFoundError: If no checkpoints are found or ``pretrained_model`` is missing.
    """
    ckpt_root = model_dir / "checkpoints"
    if not ckpt_root.exists():
        raise FileNotFoundError(f"No 'checkpoints' directory found in {model_dir}")
    step_dirs = sorted(
        [d for d in ckpt_root.iterdir() if d.is_dir() and d.name.isdigit()],
        key=lambda d: int(d.name),
    )
    if not step_dirs:
        raise FileNotFoundError(f"No checkpoint step directories found in {ckpt_root}")
    ckpt_dir = step_dirs[-1]
    pretrained = ckpt_dir / "pretrained_model"
    if not pretrained.exists():
        raise FileNotFoundError(f"'pretrained_model' directory not found in {ckpt_dir}")
    return ckpt_dir, pretrained


def _best_device() -> str:
    """Return the best available torch device string."""
    try:
        import torch as _torch
        if _torch.cuda.is_available():
            return "cuda"
        if getattr(_torch.backends, "mps", None) and _torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


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
    from_model: str | None = None,
    resume_model: str | None = None,
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
        from_model: Fine-tune from this existing model (name under ``models/``).
                    Loads its weights and architecture, then trains in a new
                    output directory on ``dataset_name``.
        resume_model: Resume a stopped training run of this model (name under
                      ``models/``).  Continues from the latest checkpoint in the
                      same output directory.

    Raises:
        FileNotFoundError: If no ``project.yaml`` can be found, or the named
                           model/dataset does not exist.
        RuntimeError: If LeRobot is not installed or dataset is missing.
        ValueError: If both ``from_model`` and ``resume_model`` are specified.
    """
    if from_model and resume_model:
        raise ValueError("Specify only one of --from-model or --resume-model, not both.")

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

    try:
        from lerobot.scripts.lerobot_train import train as lerobot_train
        from lerobot.configs.default import DatasetConfig
        from lerobot.configs.train import TrainPipelineConfig
    except ImportError as exc:
        raise RuntimeError(f"LeRobot not available: {exc}") from exc

    # ── Resume stopped training run ───────────────────────────────────────────
    if resume_model is not None:
        resume_dir = models_dir / resume_model
        if not resume_dir.exists():
            raise FileNotFoundError(
                f"Model '{resume_model}' not found in {models_dir}. "
                "Run 'defty models' to list available models."
            )
        ckpt_dir, pretrained_model_dir = _find_latest_checkpoint(resume_dir)
        train_config_path = pretrained_model_dir / "train_config.json"
        if not train_config_path.exists():
            raise FileNotFoundError(
                f"train_config.json not found in {pretrained_model_dir}. "
                "Cannot resume without the original training configuration."
            )
        logger.info("Resuming training from checkpoint: %s", ckpt_dir)

        # Load original training config and switch to resume mode
        cfg = TrainPipelineConfig.from_pretrained(str(pretrained_model_dir))
        cfg.resume = True

        # Update dataset root to current project if path has changed
        if cfg.dataset is not None:
            ds_root = Path(cfg.dataset.root)
            if not ds_root.exists():
                new_ds_root = data_dir / ds_root.name
                if new_ds_root.exists():
                    logger.info(
                        "Dataset path updated: %s → %s", ds_root, new_ds_root
                    )
                    cfg.dataset.root = str(new_ds_root)

        # Allow overriding total training steps for the resumed run
        if steps is not None:
            cfg.steps = steps

        # lerobot's validate() reads --config_path from sys.argv when resume=True.
        # Inject it temporarily so it can locate the checkpoint's training state.
        _old_argv = sys.argv[:]
        sys.argv = [sys.argv[0], f"--config_path={train_config_path}"]
        try:
            _lerobot_train_safe(lerobot_train, cfg, resume_dir)
        finally:
            sys.argv = _old_argv
        return

    # ── Normal / fine-tune training path ─────────────────────────────────────

    # Resolve fine-tune source before dataset (it may override policy type)
    finetune_from_path: Path | None = None
    if from_model is not None:
        from_model_dir = models_dir / from_model
        if not from_model_dir.exists():
            raise FileNotFoundError(
                f"Model '{from_model}' not found in {models_dir}. "
                "Run 'defty models' to list available models."
            )
        _ckpt_dir, finetune_from_path = _find_latest_checkpoint(from_model_dir)

        # Override policy type from the source model's metadata
        info_file = from_model_dir / "defty_model_info.json"
        if info_file.exists():
            with open(info_file, encoding="utf-8") as f:
                info = json.load(f)
            policy = info.get("policy", policy)
        logger.info(
            "Fine-tuning '%s' from %s -> models/%s",
            policy, from_model, model_name or "(auto)",
        )

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
        base = f"{policy}_{dataset_name}"
        if from_model is not None:
            base = f"{from_model}_ft_{dataset_name}"
        model_name = _auto_model_name(models_dir, base)
    else:
        if (models_dir / model_name).exists():
            model_name = _auto_model_name(models_dir, model_name)
    model_output = models_dir / model_name

    repo_id = f"local/{dataset_name}"

    logger.info(
        "Training policy='%s' on dataset='%s' -> models/%s",
        policy, dataset_name, model_name,
    )

    # Build dataset config
    dataset_cfg = DatasetConfig(
        repo_id=repo_id,
        root=str(dataset_root),
    )

    # Build TrainPipelineConfig
    train_kwargs: dict[str, Any] = {
        "dataset": dataset_cfg,
        "output_dir": model_output,
        "steps": steps if steps is not None else 10_000,
    }
    if batch_size is not None:
        train_kwargs["batch_size"] = batch_size

    cfg = TrainPipelineConfig(**train_kwargs)

    # Build policy config
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
        if policy_cls is None:
            raise RuntimeError(f"Unknown policy: {policy}")

        if finetune_from_path is not None:
            # Fine-tune: load architecture config from the source checkpoint so that
            # the model dimensions exactly match the saved weights.
            try:
                from lerobot.configs.policies import PreTrainedConfig as _PTC
                policy_inst = _PTC.from_pretrained(
                    str(finetune_from_path), cli_overrides=[]
                )
            except Exception as _exc:
                logger.warning(
                    "Could not load policy config from %s (%s). "
                    "Using default %s architecture — fine-tuning may fail if "
                    "dimensions do not match the saved weights.",
                    finetune_from_path, _exc, policy,
                )
                policy_inst = policy_cls()
            policy_inst.pretrained_path = finetune_from_path
            logger.info("Fine-tuning from checkpoint: %s", finetune_from_path)
        else:
            policy_inst = policy_cls()

        policy_inst.push_to_hub = False
        if hasattr(policy_inst, "device"):
            policy_inst.device = _best_device()
            logger.info("Training device: %s", policy_inst.device)
        cfg.policy = policy_inst

    except ImportError as exc:
        raise RuntimeError(f"Policy '{policy}' not available: {exc}") from exc

    if learning_rate is not None:
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
        "from_model": from_model,
    }

    _lerobot_train_safe(lerobot_train, cfg, model_output)

    # Write defty metadata AFTER training so lerobot's dir-existence check passes
    try:
        (model_output / "defty_model_info.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not write defty_model_info.json: %s", exc)

    logger.info("Training complete. Model saved to: %s", model_output)


def _lerobot_train_safe(lerobot_train: Any, cfg: Any, output_dir: Path) -> None:
    """Call ``lerobot_train(cfg)`` with error handling common to all training paths.

    Args:
        lerobot_train: The ``lerobot.scripts.lerobot_train.train`` function.
        cfg: A fully-constructed ``TrainPipelineConfig`` instance.
        output_dir: The model output directory (used only for error messages).
    """
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