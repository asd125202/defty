# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-03-18

### Added

- `defty version` command — shows version, Python, platform, binary path, LeRobot/PyTorch versions
- `defty --version` flag (via click)
- Stale installation detection — `defty upgrade` and `defty version` warn about conda/pip copies that shadow the uv-managed binary
- PATH check on Windows — warns if `~/.local/bin` is not in PATH
- Versioning section in CONTRIBUTING.md

### Fixed

- Reverted camera backend to CAP_ANY — MSMF and DSHOW both broken on Windows; let OpenCV auto-select
- Removed `import platform` from recorder.py and runner.py (no longer needed)
- Upgrade now shows post-upgrade verification hint (`defty version`)

## [Unreleased]

### Added

- **Cloud Upload** — upload recorded datasets to Hugging Face Hub
  - `defty cloud setup` — configure HF API token (stored in `~/.defty/config.yaml`)
  - `defty cloud status` — show cloud configuration and provider status
  - `defty cloud upload` — upload dataset directory to HF Hub with progress display
  - Post-record upload prompt: after `defty record`, asks to upload to Hub
  - Interactive token prompt if not configured when uploading
- **Cloud Training** — train models on cloud GPUs
  - `defty cloud train` — launch training on HF Spaces, Google Vertex AI, or Azure ML
  - `defty cloud check` — check cloud training job status
  - Abstract `CloudTrainer` interface with provider registry
  - HuggingFaceTrainer: creates HF Spaces with Docker for training
  - GoogleVertexTrainer: scaffold for Vertex AI custom training jobs
  - AzureMLTrainer: scaffold for Azure ML custom training jobs
- `src/defty/cloud/` module — config, uploader, and trainer submodules
- `huggingface-hub>=0.20.0` added to core dependencies
- `[cloud-google]` and `[cloud-azure]` optional dependency groups

### Added

- **`SPEC.md`** — comprehensive project specification: vision, node system architecture,
  six Physical AI paths, agent concept, file formats, and Alpha roadmap (M0–M5)
- **`defty run` command** — run a trained policy on the robot autonomously
  - `--model-name` / `--episodes` / `--display` / `--record` / `--no-vision`
  - With vision (cameras + state) or without vision (state-only) mode
  - Optional rollout recording to `data/run_<model>_NNN/`
  - Auto-selects latest model and best available device (CUDA/MPS/CPU)
- `defty datasets` command — list all recorded datasets with episode count, frames, FPS, size, task
- `defty models` command — list all trained models with policy type, steps, source dataset, size
- `defty replay` command — visualize a recorded episode in Rerun (`--episode`, `--save`)
- `defty scan cameras --preview` — live ASCII streaming preview (press `q` to advance cameras)
- `defty scan cameras --opencv` — probe real OpenCV VideoCapture indices to find working cameras
- `defty teleoperate --display` — Rerun viewer spawned as detached process (no Ctrl+C traceback)
- `defty record --resume` — append episodes to an existing dataset
- Auto-numbered datasets: each `defty record` run creates `<project>_001`, `_002`, …
- Auto-numbered models: each `defty train` run creates `act_<dataset>_001`, `_002`, …
- `defty_model_info.json` written alongside model checkpoints (policy, dataset, steps, lr)
- `src/defty/utils.py` — `spawn_rerun_detached()` shared utility for Ctrl+C-safe Rerun
- SVT-AV1 encoder noise suppressed during recording (fd-level stdout redirect)
- Phase-separator logging for recording: visual `───` banners for episode transitions
- `probe_opencv_cameras()` in `detector.py` — try indices 0-9 with real OpenCV capture

### Changed

- `defty train` rewritten: uses `TrainPipelineConfig` directly, `--steps` replaces `--epochs`,
  models stored in `models/<name>/` (not `outputs/`), auto-selects latest dataset
- `defty record` improved: auto-numbered datasets, cleaner banner, partial dir auto-cleanup
- `defty scan cameras --preview` changed from single-frame to live ANSI streaming
- `defty status` now verifies hardware connectivity (opens serial ports and cameras)
- Camera backend changed to MSMF (Media Foundation) on Windows — DSHOW and CAP_ANY
  both fail for standard USB cameras due to obsensor driver interference

### Fixed

- `defty record` crash on empty episode (`ValueError: add_frame before add_episode`) — caught
  with friendly warning; completed episodes are preserved
- `defty record` `FileExistsError` when `data/` already exists — partial dirs auto-cleaned
- `defty record` `ValueError: not enough values to unpack` — auto-prefix `local/` to bare names
- `defty teleoperate --display` traceback on Ctrl+C — rerun spawned in separate process group
- `defty record` `play_sounds` PowerShell failure on Windows — disabled by default
- `defty record` ConnectionError retry: smart resume detection (no episodes → fresh start)
- Camera health check used CAP_ANY backend which fails on Windows — now uses MSMF

### Added (earlier)

- `pyproject.toml` — package definition with LeRobot, Click, PySerial deps (Python 3.12+)
- `src/defty/__init__.py`, `__version__.py` — package skeleton (v0.1.0)
- `src/defty/platform.py` — cross-platform OS detection (Linux, macOS, Windows)
- `src/defty/project.py` — project.yaml init / load / save / find
- `src/defty/hardware/fingerprint.py` — USB hardware fingerprinting (serial adapters + cameras, cross-platform)
- `src/defty/hardware/detector.py` — serial port scanning (pyserial) + camera scanning (udevadm / system_profiler / pnputil)
- `src/defty/hardware/registry.py` — add/remove arms & cameras, port update via fingerprints, auto-ID generation
- `src/defty/hardware/health.py` — per-motor ping via FeetechMotorsBus, camera frame-grab health check
- `src/defty/recording/recorder.py` — wrap LeRobot record pipeline
- `src/defty/training/trainer.py` — wrap LeRobot training pipeline
- `src/defty/cli.py` — full Click CLI: `defty init`, `status`, `scan ports`, `scan cameras`, `setup add-arm`, `setup add-camera`, `setup calibrate`, `setup update`, `setup remove-arm`, `setup remove-camera`, `health`, `teleoperate`, `record`, `datasets`, `train`, `models`, `replay`, `hardware import`, `upgrade`, `uninstall`
- `install.sh` / `install.ps1` — one-line installers (uv + Python 3.12 + defty)
- `tests/test_project.py` — project.yaml CRUD tests
- `tests/test_registry.py` — hardware registry tests
- `tests/test_platform.py` — OS detection tests
- `spec/project-yaml.md` — project.yaml schema v0.1 draft
- `spec/skill-format.md` — .skill file format v0.1 draft

## [0.0.0] — 2026-03-17

### Added

- Initial repository scaffold: README, CONTRIBUTING, LICENSE, STRUCTURE, CHANGELOG