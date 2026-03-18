# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`defty datasets rename OLD NEW`** — rename a dataset directory and
  automatically update the `dataset` field in all model metadata files
  (`defty_model_info.json`) and lerobot checkpoint `train_config.json` files
  that reference the old name.
- **`defty models rename OLD NEW`** — rename a model directory and update
  the `output_dir` field stored in its checkpoint training configs.
- **`defty train --from-model MODEL`** — fine-tune from an existing trained model.
  Loads the source model's architecture and weights via `pretrained_path`, then
  trains in a new auto-numbered output directory on any dataset.  Output names are
  auto-generated as `<source>_ft_<dataset>_001`, etc.
- **`defty train --resume-model MODEL`** — resume a stopped training run in-place.
  Continues from the latest checkpoint of the named model, restoring step counter
  and optimizer state.  Optionally combine with `--steps N` to extend total steps.

## [0.2.4] — 2026-03-18

### Fixed

- **`defty agent run` not connecting hardware** — agent runner now auto-detects
  project configuration (follower arm + cameras) from `project.yaml` in the
  current or parent directory. Previously required explicit `--port` flag.
- **SO-101 interface camera backend** — changed from DSHOW (Windows-specific)
  to CAP_ANY (default) for consistency with `recorder.py`.

### Added

- `defty agent run --path` option — specify path to `project.yaml` explicitly.
- `defty agent run --no-hardware` flag — run agent without connecting hardware
  (useful for testing tree logic).

## [0.2.3] — 2026-03-18

### Fixed

- **Motor communication stability** — monkey-patch LeRobot's motor bus to retry
  failed reads/writes 3 times (default was 0), preventing single-packet-loss from
  killing the entire recording session. Applied to `sync_read`, `sync_write`,
  `read`, and `write` operations.
- **Serial timeout too aggressive** — increased Feetech motor bus default timeout
  from 1000 ms to 2000 ms, giving more margin during USB bus contention.
- **Image encoding blocking motor bus** — set `num_image_writer_processes=1` to
  offload video frame encoding to a subprocess instead of the main thread.
- **Reconnect too slow / gives up too early** — reduced retry interval from 10 s
  to 5 s, extended timeout from 60 s to 120 s.
- Patches applied consistently to `record`, `teleoperate`, `calibrate`, and `run`
  commands via shared `_apply_motor_stability_patches()`.

## [0.2.2] — 2026-03-18

### Fixed

- **`defty health` / `defty status` arm checks broken** — `FeetechMotorsBus.__init__()`
  API changed to require a `motors` parameter; replaced direct instantiation with
  `FeetechMotorsBus.scan_port()` which probes the port without prior motor config.
- **`defty health` / `defty status` camera checks broken on Windows** — still used
  `CAP_MSMF` backend which was reverted everywhere else in v0.2.1; now uses
  `cv2.VideoCapture(dev_arg)` (CAP_ANY) matching the rest of the codebase.

## [0.2.1] — 2026-03-18

### Fixed

- **Camera recording failure on Windows** — disabled OpenCV's obsensor UVC backend
  (`OPENCV_VIDEOIO_PRIORITY_OBSENSOR=0`) which was interfering with simultaneous
  camera access: opening Camera 1 while Camera 2 was already streaming triggered
  obsensor driver errors that corrupted the USB state, causing `ConnectionError`.
- Obsensor `[ERROR] obsensor_uvc_stream_channel.cpp` noise eliminated from all
  camera operations (scan, record, teleoperate, preview).

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

- **Cloud Upload** - upload recorded datasets to Hugging Face Hub
  - `defty cloud setup` - configure HF API token
  - `defty cloud status` - show cloud configuration and provider status
  - `defty cloud upload` - upload dataset directory to HF Hub with progress display
  - Post-record upload prompt: after `defty record`, asks to upload to Hub
  - Interactive token prompt if not configured when uploading
- **Cloud Training** - train models on cloud GPUs
  - `defty cloud train` - launch training on HF Spaces, Google Vertex AI, or Azure ML
  - `defty cloud check` - check cloud training job status
  - Abstract `CloudTrainer` interface with provider registry
  - HuggingFaceTrainer: creates HF Spaces with Docker for training
  - GoogleVertexTrainer: scaffold for Vertex AI custom training jobs
  - AzureMLTrainer: scaffold for Azure ML custom training jobs
- `src/defty/cloud/` module - config, uploader, and trainer submodules
- `huggingface-hub>=0.20.0` added to core dependencies
- `[cloud-google]` and `[cloud-azure]` optional dependency groups
- **Phase 1 - Node Engine** (`src/defty/nodes/`)
  - `Node` ABC with `tick(context)` pattern
  - `NodeStatus` result type with SUCCESS / FAILURE / RUNNING states
  - `Context` data container (cameras, joint_states, memory blackboard, robot)
  - `RobotInterface` ABC for hardware abstraction
  - `SequenceNode`, `SelectorNode`, `RepeatNode`, `ParallelNode` - flow control
  - `BehaviorTreeRunner` - main tick loop with frequency control + SIGINT handling
- **Phase 2 - Leaf Nodes** (`src/defty/nodes/`)
  - `CameraCaptureNode`, `JointControlNode`, `GripperOpenNode`, `GripperCloseNode`
  - `RelativeMoveNode`, `ACTPolicyNode`, `WaitNode`, `ConditionNode`
  - `LeRobotSO101Interface` - RobotInterface implementation for SO-101 arm
- **Phase 3 - Agent System** (`src/defty/agents/`)
  - `.defty` file format - restricted Python syntax for safe behavior-tree definitions
  - AST-based parser with security validation (no imports, no function/class defs)
  - `NodeRegistry` - maps node type names to classes with auto-discovery
  - `AgentRef` node - compose agents by referencing other .defty files
  - `AgentManager` - CRUD operations for agents stored in `~/.defty/agents/`
  - `defty agent create <name>` - generate agent from template
  - `defty agent run <name>` - parse then build tree then connect hardware then execute
  - `defty agent list` - list agents with version, robot type, node count
  - `defty agent info <name>` - show tree structure and dependencies
- `tests/test_nodes.py` - 49 tests for node engine and leaf nodes
- `tests/test_agents.py` - 32 tests for parser, registry, manager, AgentRef

### Added (earlier)

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