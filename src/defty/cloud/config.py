# Copyright (c) 2026 APRL Technologies Inc.
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
"""Cloud configuration management for Defty.

Stores Hugging Face API tokens and cloud provider settings in
``~/.defty/config.yaml``.  Tokens are stored in plain text — the file
permissions are set to owner-only (600) on Unix systems.
"""

from __future__ import annotations

import contextlib
import logging
import os
import platform
import stat
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

__all__ = [
    "DEFTY_CONFIG_DIR",
    "DEFTY_CONFIG_FILE",
    "get_cloud_provider_config",
    "get_hf_token",
    "load_cloud_config",
    "save_cloud_config",
    "save_cloud_provider_config",
    "save_hf_token",
]

DEFTY_CONFIG_DIR = Path.home() / ".defty"
DEFTY_CONFIG_FILE = DEFTY_CONFIG_DIR / "config.yaml"


def _ensure_config_dir() -> Path:
    """Create ``~/.defty/`` if it doesn't exist, with restrictive permissions."""
    DEFTY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if platform.system() != "Windows":
        with contextlib.suppress(OSError):
            DEFTY_CONFIG_DIR.chmod(stat.S_IRWXU)  # 700
    return DEFTY_CONFIG_DIR


def load_cloud_config() -> dict[str, Any]:
    """Load the cloud configuration from ``~/.defty/config.yaml``.

    Returns:
        Configuration dictionary.  Empty dict if the file doesn't exist.
    """
    if not DEFTY_CONFIG_FILE.exists():
        return {}
    try:
        text = DEFTY_CONFIG_FILE.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Failed to read %s: %s", DEFTY_CONFIG_FILE, exc)
        return {}


def save_cloud_config(config: dict[str, Any]) -> None:
    """Save the cloud configuration to ``~/.defty/config.yaml``.

    Args:
        config: Configuration dictionary to persist.
    """
    _ensure_config_dir()
    DEFTY_CONFIG_FILE.write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    # Restrict file permissions on Unix
    if platform.system() != "Windows":
        with contextlib.suppress(OSError):
            DEFTY_CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
    logger.debug("Saved cloud config to %s", DEFTY_CONFIG_FILE)


def get_hf_token() -> str | None:
    """Retrieve the Hugging Face API token.

    Checks (in order):
    1. ``HF_TOKEN`` environment variable
    2. ``~/.defty/config.yaml`` → ``huggingface.token``
    3. ``huggingface-cli`` cached token (``~/.cache/huggingface/token``)

    Returns:
        The token string, or *None* if not configured.
    """
    # 1. Environment variable
    env_token = os.environ.get("HF_TOKEN")
    if env_token:
        return env_token

    # 2. Defty config
    config = load_cloud_config()
    defty_token = config.get("huggingface", {}).get("token")
    if defty_token:
        return defty_token

    # 3. huggingface-cli cached token
    hf_cache = Path.home() / ".cache" / "huggingface" / "token"
    if hf_cache.exists():
        try:
            token = hf_cache.read_text(encoding="utf-8").strip()
            if token:
                return token
        except OSError:
            pass

    return None


def save_hf_token(token: str) -> None:
    """Save a Hugging Face API token to ``~/.defty/config.yaml``.

    Args:
        token: The HF API token (starts with ``hf_``).
    """
    config = load_cloud_config()
    if "huggingface" not in config:
        config["huggingface"] = {}
    config["huggingface"]["token"] = token
    save_cloud_config(config)
    logger.info("Hugging Face token saved to %s", DEFTY_CONFIG_FILE)


def get_cloud_provider_config(provider: str) -> dict[str, Any]:
    """Get configuration for a specific cloud provider.

    Args:
        provider: Provider name (``huggingface``, ``google``, ``azure``).

    Returns:
        Provider-specific configuration dictionary.
    """
    config = load_cloud_config()
    return config.get(provider, {})


def save_cloud_provider_config(provider: str, provider_config: dict[str, Any]) -> None:
    """Save configuration for a specific cloud provider.

    Args:
        provider: Provider name (``huggingface``, ``google``, ``azure``).
        provider_config: Provider-specific configuration dictionary.
    """
    config = load_cloud_config()
    config[provider] = provider_config
    save_cloud_config(config)
