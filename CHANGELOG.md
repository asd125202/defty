# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`defty run` command** — run a trained policy on the robot autonomously
  - `--model-name` / `--episodes` / `--display` / `--record` / `--no-vision`
  - With vision (cameras + state) or without vision (state-only) mode
  - Optional rollout recording to `data/run_<model>_NNN/`
  - Auto-selects latest model and best available device (CUDA/MPS/CPU)
- `defty datasets` command — list all recorded datasets with episode count, frames, FPS, size, task
- `defty models` command — list all trained models with policy type, steps, source dataset, size
- `defty replay` command — visualize a recorded episode in Rerun (`--episode`, `--save`)
- `defty scan cameras --preview` — live ASCII streaming preview (press `q` to advance cameras)
- `defty teleoperate --display` — Rerun viewer spawned as detached process (no Ctrl+C traceback)
- `defty record --resume` — append episodes to an existing dataset
- Auto-numbered datasets: each `defty record` run creates `<project>_001`, `_002`, …
- Auto-numbered models: each `defty train` run creates `act_<dataset>_001`, `_002`, …
- `defty_model_info.json` written alongside model checkpoints (policy, dataset, steps, lr)
- `src/defty/utils.py` — `spawn_rerun_detached()` shared utility for Ctrl+C-safe Rerun
- SVT-AV1 encoder noise suppressed during recording (fd-level stdout redirect)
- Phase-separator logging for recording: visual `───` banners for episode transitions

### Changed

- `defty train` rewritten: uses `TrainPipelineConfig` directly, `--steps` replaces `--epochs`,
  models stored in `models/<name>/` (not `outputs/`), auto-selects latest dataset
- `defty record` improved: auto-numbered datasets, cleaner banner, partial dir auto-cleanup
- `defty scan cameras --preview` changed from single-frame to live ANSI streaming

### Fixed

- `defty record` crash on empty episode (`ValueError: add_frame before add_episode`) — caught
  with friendly warning; completed episodes are preserved
- `defty record` `FileExistsError` when `data/` already exists — partial dirs auto-cleaned
- `defty record` `ValueError: not enough values to unpack` — auto-prefix `local/` to bare names
- `defty teleoperate --display` traceback on Ctrl+C — rerun spawned in separate process group
- `defty record` `play_sounds` PowerShell failure on Windows — disabled by default

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