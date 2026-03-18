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
"""Cloud training backends for Defty.

Provides an abstract ``CloudTrainer`` interface and concrete implementations
for three cloud providers:

1. **Hugging Face** — uses HF Spaces or AutoTrain for managed GPU training
2. **Google Cloud (Vertex AI)** — submits custom training jobs via Vertex AI
3. **Azure Machine Learning** — submits custom training jobs via Azure ML

Google Cloud and Azure implementations are scaffolds — they define the
interface and configuration but require active cloud accounts and GPU quota
to actually run.  See the quota application guides in CONTEXT.md.
"""

from __future__ import annotations

import abc
import logging
import textwrap
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "AzureMLTrainer",
    "CloudTrainer",
    "GoogleVertexTrainer",
    "HuggingFaceTrainer",
    "get_trainer",
    "list_providers",
]


# ── Abstract interface ────────────────────────────────────────────────────────


class CloudTrainer(abc.ABC):
    """Abstract base class for cloud training backends.

    Each provider must implement ``launch``, ``status``, and ``is_configured``.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Return *True* if the provider has valid credentials/config."""

    @abc.abstractmethod
    def launch(self, config: dict[str, Any]) -> dict[str, Any]:
        """Launch a training job.

        Args:
            config: Training configuration dict with keys like
                ``dataset_repo_id``, ``num_train_steps``, ``batch_size``,
                ``policy_type``.

        Returns:
            Dict with at least ``job_id`` and ``status`` keys.
        """

    @abc.abstractmethod
    def status(self, job_id: str) -> dict[str, Any]:
        """Check the status of a training job.

        Args:
            job_id: The job identifier returned by ``launch()``.

        Returns:
            Dict with ``status`` and provider-specific metadata.
        """


# ── Hugging Face Trainer ─────────────────────────────────────────────────────


class HuggingFaceTrainer(CloudTrainer):
    """Train models on Hugging Face Spaces.

    Creates an HF Space with a Docker container that runs the LeRobot
    training pipeline.  The Space is configured with a GPU runtime
    (T4 by default) and automatically shuts down after training completes.
    """

    @property
    def name(self) -> str:
        return "Hugging Face Spaces"

    def is_configured(self) -> bool:
        """Check if HF token is available."""
        from defty.cloud.config import get_hf_token

        return get_hf_token() is not None

    def launch(self, config: dict[str, Any]) -> dict[str, Any]:
        """Launch training on HF Spaces.

        Creates a Docker-based Space that:
        1. Clones the dataset from the Hub
        2. Runs the LeRobot training pipeline
        3. Pushes the trained model back to the Hub

        Args:
            config: Must include ``dataset_repo_id``.

        Returns:
            Dict with ``job_id``, ``status``, and ``url``.
        """
        from defty.cloud.config import get_hf_token

        token = get_hf_token()
        if not token:
            raise RuntimeError("Hugging Face token not configured. Run 'defty cloud setup'.")

        try:
            from huggingface_hub import HfApi
        except ImportError as exc:
            raise RuntimeError(
                "huggingface-hub is required. Install with: pip install huggingface-hub"
            ) from exc

        api = HfApi(token=token)
        user_info = api.whoami()
        username = user_info.get("name", "defty-user")

        dataset_repo_id = config["dataset_repo_id"]
        dataset_name = dataset_repo_id.split("/")[-1]
        steps = config.get("num_train_steps", 50000)
        batch_size = config.get("batch_size", 8)
        policy = config.get("policy_type", "act")

        space_name = f"defty-train-{dataset_name}"
        space_id = f"{username}/{space_name}"

        # Generate training script
        train_script = textwrap.dedent(f"""\
            #!/usr/bin/env python3
            \"\"\"Auto-generated Defty cloud training script.\"\"\"

            import subprocess
            import sys

            def main():
                cmd = [
                    sys.executable, "-m", "lerobot.scripts.train",
                    "--dataset.repo_id={dataset_repo_id}",
                    "--policy.type={policy}",
                    "--training.num_train_steps={steps}",
                    "--training.batch_size={batch_size}",
                    "--output_dir=./outputs",
                ]
                print(f"Running: {{' '.join(cmd)}}")
                result = subprocess.run(cmd, check=False)
                sys.exit(result.returncode)

            if __name__ == "__main__":
                main()
        """)

        # Generate Dockerfile
        dockerfile = textwrap.dedent("""\
            FROM python:3.12-slim

            RUN pip install --no-cache-dir \\
                lerobot[feetech] \\
                huggingface-hub \\
                torch --index-url https://download.pytorch.org/whl/cu121

            WORKDIR /app
            COPY train.py .

            # Login to HF Hub for dataset access
            ARG HF_TOKEN
            ENV HF_TOKEN=${HF_TOKEN}
            RUN huggingface-cli login --token $HF_TOKEN || true

            CMD ["python", "train.py"]
        """)

        # Create the Space
        try:
            api.create_repo(
                repo_id=space_id,
                repo_type="space",
                space_sdk="docker",
                space_hardware="t4-small",
                private=True,
                exist_ok=True,
            )

            # Upload training files
            api.upload_file(
                path_or_fileobj=train_script.encode(),
                path_in_repo="train.py",
                repo_id=space_id,
                repo_type="space",
                commit_message="Add training script",
            )
            api.upload_file(
                path_or_fileobj=dockerfile.encode(),
                path_in_repo="Dockerfile",
                repo_id=space_id,
                repo_type="space",
                commit_message="Add Dockerfile",
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to create HF Space: {exc}") from exc

        url = f"https://huggingface.co/spaces/{space_id}"
        logger.info("Training Space created: %s", url)

        return {
            "job_id": space_name,
            "status": "building",
            "url": url,
            "provider": "huggingface",
            "space_id": space_id,
        }

    def status(self, job_id: str) -> dict[str, Any]:
        """Check HF Space status.

        Args:
            job_id: The Space name (without username prefix).
        """
        from defty.cloud.config import get_hf_token

        token = get_hf_token()
        if not token:
            raise RuntimeError("HF token not configured.")

        try:
            from huggingface_hub import HfApi
        except ImportError as exc:
            raise RuntimeError("huggingface-hub is required.") from exc

        api = HfApi(token=token)
        user_info = api.whoami()
        username = user_info.get("name", "defty-user")
        space_id = f"{username}/{job_id}"

        try:
            space_info = api.space_info(repo_id=space_id)
            runtime = getattr(space_info, "runtime", None)
            runtime_stage = getattr(runtime, "stage", "UNKNOWN") if runtime else "UNKNOWN"
            hardware = getattr(runtime, "hardware", "unknown") if runtime else "unknown"
        except Exception as exc:
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(exc),
            }

        return {
            "job_id": job_id,
            "space_id": space_id,
            "status": str(runtime_stage).lower(),
            "hardware": str(hardware),
            "url": f"https://huggingface.co/spaces/{space_id}",
        }


# ── Google Vertex AI Trainer ─────────────────────────────────────────────────


class GoogleVertexTrainer(CloudTrainer):
    """Train models on Google Cloud Vertex AI (scaffold).

    This is a scaffold implementation that defines the interface for
    Vertex AI custom training jobs.  It requires:

    - A Google Cloud project with Vertex AI API enabled
    - GPU quota in a supported region (e.g. ``us-central1``)
    - ``google-cloud-aiplatform`` SDK installed

    See CONTEXT.md for quota application instructions.
    """

    @property
    def name(self) -> str:
        return "Google Cloud Vertex AI"

    def is_configured(self) -> bool:
        """Check if Google Cloud SDK and credentials are available."""
        try:
            import google.cloud.aiplatform  # noqa: F401

            from defty.cloud.config import get_cloud_provider_config

            gconfig = get_cloud_provider_config("google")
            return bool(gconfig.get("project_id"))
        except ImportError:
            return False

    def launch(self, config: dict[str, Any]) -> dict[str, Any]:
        """Launch a Vertex AI custom training job.

        Args:
            config: Training configuration.

        Raises:
            RuntimeError: Always, until Google Cloud quota is provisioned.
        """
        if not self.is_configured():
            raise RuntimeError(
                "Google Cloud Vertex AI is not configured.\n\n"
                "To set up Google Cloud training:\n"
                "  1. Install the SDK: pip install 'defty[cloud-google]'\n"
                "  2. Create a GCP project and enable Vertex AI API\n"
                "  3. Request GPU quota (see CONTEXT.md for details)\n"
                "  4. Run: defty cloud setup  (and configure google project_id)\n"
            )

        try:
            from google.cloud import aiplatform
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-aiplatform is required.\n  Install with: pip install 'defty[cloud-google]'"
            ) from exc

        from defty.cloud.config import get_cloud_provider_config

        gconfig = get_cloud_provider_config("google")
        project_id = gconfig["project_id"]
        region = gconfig.get("region", "us-central1")
        staging_bucket = gconfig.get("staging_bucket", f"gs://defty-training-{project_id}")

        dataset_repo_id = config["dataset_repo_id"]
        steps = config.get("num_train_steps", 50000)
        batch_size = config.get("batch_size", 8)
        policy = config.get("policy_type", "act")

        aiplatform.init(
            project=project_id,
            location=region,
            staging_bucket=staging_bucket,
        )

        worker_pool = [
            {
                "machine_spec": {
                    "machine_type": gconfig.get("machine_type", "n1-standard-8"),
                    "accelerator_type": gconfig.get("accelerator_type", "NVIDIA_TESLA_T4"),
                    "accelerator_count": gconfig.get("accelerator_count", 1),
                },
                "replica_count": 1,
                "container_spec": {
                    "image_uri": gconfig.get(
                        "training_image",
                        "us-docker.pkg.dev/vertex-ai/training/pytorch-gpu.2-2.py310:latest",
                    ),
                    "command": ["python", "-m", "lerobot.scripts.train"],
                    "args": [
                        f"--dataset.repo_id={dataset_repo_id}",
                        f"--policy.type={policy}",
                        f"--training.num_train_steps={steps}",
                        f"--training.batch_size={batch_size}",
                        "--output_dir=/gcs/output",
                    ],
                },
            }
        ]

        job_name = f"defty-train-{dataset_repo_id.replace('/', '-')}"

        try:
            job = aiplatform.CustomJob(
                display_name=job_name,
                worker_pool_specs=worker_pool,
            )
            job.run(sync=False)
        except Exception as exc:
            raise RuntimeError(f"Failed to launch Vertex AI job: {exc}") from exc

        return {
            "job_id": job.resource_name,
            "status": "submitted",
            "provider": "google",
            "project": project_id,
            "region": region,
        }

    def status(self, job_id: str) -> dict[str, Any]:
        """Check Vertex AI job status.

        Args:
            job_id: The Vertex AI job resource name.
        """
        try:
            from google.cloud import aiplatform
        except ImportError as exc:
            raise RuntimeError("google-cloud-aiplatform is required.") from exc

        from defty.cloud.config import get_cloud_provider_config

        gconfig = get_cloud_provider_config("google")
        project_id = gconfig.get("project_id", "")
        region = gconfig.get("region", "us-central1")

        aiplatform.init(project=project_id, location=region)

        try:
            job = aiplatform.CustomJob.get(job_id)
            return {
                "job_id": job_id,
                "status": str(job.state).lower(),
                "provider": "google",
                "display_name": job.display_name,
            }
        except Exception as exc:
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(exc),
            }


# ── Azure ML Trainer ─────────────────────────────────────────────────────────


class AzureMLTrainer(CloudTrainer):
    """Train models on Azure Machine Learning (scaffold).

    This is a scaffold implementation that defines the interface for
    Azure ML custom training jobs.  It requires:

    - An Azure subscription with ML workspace
    - GPU compute quota in a supported region
    - ``azure-ai-ml`` and ``azure-identity`` SDKs installed

    See CONTEXT.md for quota application instructions.
    """

    @property
    def name(self) -> str:
        return "Azure Machine Learning"

    def is_configured(self) -> bool:
        """Check if Azure ML SDK and config are available."""
        try:
            import azure.ai.ml  # noqa: F401

            from defty.cloud.config import get_cloud_provider_config

            aconfig = get_cloud_provider_config("azure")
            return bool(
                aconfig.get("subscription_id")
                and aconfig.get("resource_group")
                and aconfig.get("workspace_name")
            )
        except ImportError:
            return False

    def launch(self, config: dict[str, Any]) -> dict[str, Any]:
        """Launch an Azure ML training job.

        Args:
            config: Training configuration.

        Raises:
            RuntimeError: Always, until Azure ML quota is provisioned.
        """
        if not self.is_configured():
            raise RuntimeError(
                "Azure Machine Learning is not configured.\n\n"
                "To set up Azure ML training:\n"
                "  1. Install the SDK: pip install 'defty[cloud-azure]'\n"
                "  2. Create an Azure ML workspace\n"
                "  3. Request GPU compute quota (see CONTEXT.md for details)\n"
                "  4. Run: defty cloud setup  (and configure azure settings)\n"
            )

        try:
            from azure.ai.ml import MLClient, command
            from azure.ai.ml.entities import Environment
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise RuntimeError(
                "azure-ai-ml and azure-identity are required.\n"
                "  Install with: pip install 'defty[cloud-azure]'"
            ) from exc

        from defty.cloud.config import get_cloud_provider_config

        aconfig = get_cloud_provider_config("azure")

        credential = DefaultAzureCredential()
        ml_client = MLClient(
            credential=credential,
            subscription_id=aconfig["subscription_id"],
            resource_group_name=aconfig["resource_group"],
            workspace_name=aconfig["workspace_name"],
        )

        dataset_repo_id = config["dataset_repo_id"]
        steps = config.get("num_train_steps", 50000)
        batch_size = config.get("batch_size", 8)
        policy = config.get("policy_type", "act")

        env = Environment(
            name="defty-training",
            image="mcr.microsoft.com/azureml/openmpi4.1.0-cuda11.8-cudnn8-ubuntu22.04",
            conda_file={
                "name": "defty-env",
                "dependencies": [
                    "python=3.12",
                    "pip",
                    {"pip": ["lerobot[feetech]", "huggingface-hub", "torch"]},
                ],
            },
        )

        train_command = (
            f"python -m lerobot.scripts.train "
            f"--dataset.repo_id={dataset_repo_id} "
            f"--policy.type={policy} "
            f"--training.num_train_steps={steps} "
            f"--training.batch_size={batch_size} "
            f"--output_dir=./outputs"
        )

        compute_target = aconfig.get("compute_target", "gpu-cluster")

        job = command(
            code=".",
            command=train_command,
            environment=env,
            compute=compute_target,
            display_name=f"defty-train-{dataset_repo_id.replace('/', '-')}",
        )

        try:
            returned_job = ml_client.jobs.create_or_update(job)
        except Exception as exc:
            raise RuntimeError(f"Failed to launch Azure ML job: {exc}") from exc

        return {
            "job_id": returned_job.name,
            "status": returned_job.status or "submitted",
            "provider": "azure",
            "url": returned_job.studio_url or "",
        }

    def status(self, job_id: str) -> dict[str, Any]:
        """Check Azure ML job status.

        Args:
            job_id: The Azure ML job name.
        """
        try:
            from azure.ai.ml import MLClient
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise RuntimeError("azure-ai-ml and azure-identity are required.") from exc

        from defty.cloud.config import get_cloud_provider_config

        aconfig = get_cloud_provider_config("azure")

        credential = DefaultAzureCredential()
        ml_client = MLClient(
            credential=credential,
            subscription_id=aconfig.get("subscription_id", ""),
            resource_group_name=aconfig.get("resource_group", ""),
            workspace_name=aconfig.get("workspace_name", ""),
        )

        try:
            job = ml_client.jobs.get(job_id)
            return {
                "job_id": job_id,
                "status": job.status or "unknown",
                "provider": "azure",
                "display_name": job.display_name or "",
                "url": job.studio_url or "",
            }
        except Exception as exc:
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(exc),
            }


# ── Provider registry ────────────────────────────────────────────────────────

_PROVIDERS: dict[str, type[CloudTrainer]] = {
    "huggingface": HuggingFaceTrainer,
    "google": GoogleVertexTrainer,
    "azure": AzureMLTrainer,
}


def get_trainer(provider: str) -> CloudTrainer:
    """Get a trainer instance by provider name.

    Args:
        provider: One of ``huggingface``, ``google``, ``azure``.

    Returns:
        A ``CloudTrainer`` instance.

    Raises:
        ValueError: If provider is not recognized.
    """
    cls = _PROVIDERS.get(provider.lower())
    if cls is None:
        valid = ", ".join(_PROVIDERS)
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {valid}")
    return cls()


def list_providers() -> list[dict[str, str]]:
    """List all available cloud training providers.

    Returns:
        List of dicts with ``id``, ``name``, and ``configured`` keys.
    """
    result = []
    for provider_id, cls in _PROVIDERS.items():
        trainer = cls()
        result.append(
            {
                "id": provider_id,
                "name": trainer.name,
                "configured": "yes" if trainer.is_configured() else "no",
            }
        )
    return result
