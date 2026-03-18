# Defty — Repository Structure

```
defty/
├── LICENSE                          # Apache 2.0
├── README.md                        # Full command reference & usage guide
├── CONTRIBUTING.md                  # Coding standards & PR checklist
├── CHANGELOG.md                     # Keep-a-changelog format
├── STRUCTURE.md                     # This file
├── SPEC.md                          # Project specification — vision, architecture, roadmap
├── pyproject.toml                   # Package definition, deps, ruff config
├── install.sh                       # One-line installer: Linux / macOS
├── install.ps1                      # One-line installer: Windows PowerShell
│
├── src/
│   └── defty/
│       ├── __init__.py              # Package root, re-exports __version__
│       ├── __version__.py           # Single-source version string
│       ├── cli.py                   # Click CLI — all `defty` commands
│       ├── platform.py              # OS detection (Linux/macOS/Windows)
│       ├── project.py               # project.yaml CRUD (init/load/save)
│       ├── utils.py                 # Shared utilities (spawn_rerun_detached)
│       │
│       ├── cloud/
│       │   ├── __init__.py          # Re-exports key cloud symbols
│       │   ├── config.py            # Token & config management (~/.defty/config.yaml)
│       │   ├── uploader.py          # Upload datasets to HF Hub
│       │   └── trainer.py           # Cloud training (HF/Google/Azure)
│       │
│       ├── hardware/
│       │   ├── __init__.py          # Re-exports from submodules
│       │   ├── detector.py          # Serial port & camera scanning
│       │   ├── fingerprint.py       # Cross-platform hardware fingerprinting
│       │   ├── health.py            # Per-motor ping, camera connectivity
│       │   └── registry.py          # Add/remove/update arms & cameras
│       │
│       ├── recording/
│       │   ├── __init__.py          # Re-exports record()
│       │   └── recorder.py          # Wrap LeRobot recording pipeline
│       │
│       ├── inference/
│       │   ├── __init__.py          # Re-exports run()
│       │   └── runner.py            # Run trained policy on robot
│       │
│       └── training/
│           ├── __init__.py          # Re-exports train()
│           └── trainer.py           # Wrap LeRobot training pipeline
│
├── tests/
│   ├── __init__.py
│   ├── test_platform.py             # OS detection tests
│   ├── test_project.py              # project.yaml CRUD tests
│   └── test_registry.py             # Hardware registry tests
│
└── spec/
    ├── project-yaml.md              # project.yaml schema v0.1
    └── skill-format.md              # .skill file format v0.1
```

## Runtime project layout (created by `defty init`)

```
<project>/
├── project.yaml              ← hardware config, project metadata
├── calibration/              ← arm calibration files (.json per arm)
│   ├── so101_follower_1.json
│   └── so101_leader_1.json
├── data/                     ← recorded datasets (one dir per defty record run)
│   ├── my-robot_001/
│   │   ├── data/chunk-000/   ← joint positions + states (Parquet)
│   │   ├── meta/info.json    ← episode count, fps, features
│   │   ├── meta/tasks.parquet
│   │   └── videos/           ← camera recordings (AV1/mp4)
│   └── my-robot_002/
├── models/                   ← trained models (one dir per defty train run)
│   └── act_my-robot_001_001/
│       ├── defty_model_info.json   ← policy, dataset, steps metadata
│       ├── config.json
│       └── checkpoints/
└── replays/                  ← .rrd files saved by defty replay --save
```