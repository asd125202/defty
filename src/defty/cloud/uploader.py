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
"""Upload Defty datasets to the Hugging Face Hub.

Uses ``huggingface_hub.HfApi`` to upload the full dataset directory
(Parquet data, metadata, and video recordings) to a Hub dataset
repository.  Displays real-time upload progress.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from defty.cloud.config import get_hf_token, save_hf_token

logger = logging.getLogger(__name__)

__all__ = ["upload_dataset"]


def _ensure_token(*, interactive: bool = True) -> str:
    """Get the HF token, prompting interactively if needed.

    Args:
        interactive: If *True* and no token is found, prompt the user.

    Returns:
        A valid HF API token string.

    Raises:
        RuntimeError: If no token is available and not interactive.
    """
    token = get_hf_token()
    if token:
        return token

    if not interactive or not sys.stdin.isatty():
        raise RuntimeError(
            "Hugging Face API token not configured.\n"
            "  Run 'defty cloud setup' to set your token, or\n"
            "  set the HF_TOKEN environment variable."
        )

    # Interactive prompt
    import click

    click.echo("\n⚠  No Hugging Face API token found.")
    click.echo("   Get one at: https://huggingface.co/settings/tokens")
    click.echo("   (Select 'Write' permission)\n")
    token = click.prompt("Paste your HF token (hf_...)", hide_input=True)
    token = token.strip()
    if not token:
        raise RuntimeError("Empty token provided. Upload cancelled.")

    if click.confirm("Save this token for future use?", default=True):
        save_hf_token(token)
        click.echo("✓ Token saved to ~/.defty/config.yaml")

    return token


def _get_dataset_size(dataset_dir: Path) -> int:
    """Calculate total size of dataset directory in bytes."""
    total = 0
    for f in dataset_dir.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def upload_dataset(
    dataset_dir: str | Path,
    *,
    repo_id: str | None = None,
    private: bool = False,
    token: str | None = None,
    interactive: bool = True,
) -> str:
    """Upload a dataset directory to the Hugging Face Hub.

    Args:
        dataset_dir: Path to the dataset directory (e.g. ``data/test_001/``).
        repo_id: Hub repository ID (``username/dataset-name``).  If *None*,
                 auto-generates from dataset directory name.
        private: Whether the Hub repository should be private.
        token: HF API token.  If *None*, uses configured token or prompts.
        interactive: Allow interactive prompts for token and confirmation.

    Returns:
        The Hub URL of the uploaded dataset.

    Raises:
        RuntimeError: If dependencies are missing, token unavailable, or upload fails.
        FileNotFoundError: If dataset directory doesn't exist.
    """
    dataset_path = Path(dataset_dir)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_path}")

    meta_file = dataset_path / "meta" / "info.json"
    if not meta_file.exists():
        raise RuntimeError(
            f"'{dataset_path.name}' doesn't look like a valid dataset (missing meta/info.json)."
        )

    # Resolve token
    if token is None:
        token = _ensure_token(interactive=interactive)

    # Resolve repo_id
    if repo_id is None:
        try:
            from huggingface_hub import HfApi

            api = HfApi(token=token)
            user_info = api.whoami()
            username = user_info.get("name", "defty-user")
        except Exception:
            username = "defty-user"
        repo_id = f"{username}/{dataset_path.name}"

    dataset_size = _get_dataset_size(dataset_path)
    logger.info(
        "Uploading dataset '%s' (%s) to %s",
        dataset_path.name,
        _format_size(dataset_size),
        repo_id,
    )

    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError(
            "huggingface-hub is required for cloud uploads.\n  Install it with: pip install huggingface-hub"
        ) from exc

    api = HfApi(token=token)

    # Create or ensure the repository exists
    try:
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to create/access Hub repository '{repo_id}': {exc}\n"
            "  Check that your token has 'Write' permission."
        ) from exc

    # Upload the dataset folder with progress
    import click

    click.echo(f"\n{'─' * 55}")
    click.echo("  ☁  Uploading to Hugging Face Hub")
    click.echo(f"  Repo    : {repo_id}")
    click.echo(f"  Size    : {_format_size(dataset_size)}")
    click.echo(f"  Private : {'yes' if private else 'no'}")
    click.echo(f"{'─' * 55}\n")

    try:
        api.upload_folder(
            folder_path=str(dataset_path),
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"Upload dataset {dataset_path.name} via Defty",
        )
    except KeyboardInterrupt:
        click.echo("\n⚠  Upload interrupted by user.")
        raise
    except Exception as exc:
        raise RuntimeError(f"Upload failed: {exc}") from exc

    hub_url = f"https://huggingface.co/datasets/{repo_id}"
    click.echo("\n✓ Upload complete!")
    click.echo(f"  View at: {hub_url}\n")

    return hub_url
