# Defty — Repository Structure

```
defty/
├── LICENSE                          # Apache 2.0
├── README.md                        # Project overview
├── CONTRIBUTING.md                  # Coding standards & PR checklist
├── CHANGELOG.md                     # Keep-a-changelog format
├── STRUCTURE.md                     # This file
├── pyproject.toml                   # Package definition, deps, ruff config
│
├── src/
│   └── defty/
│       ├── __init__.py              # Package root, re-exports __version__
│       ├── __version__.py           # Single-source version string
│       ├── cli.py                   # Click CLI — all `defty` commands
│       ├── platform.py              # OS detection (Linux/macOS/Windows)
│       ├── project.py               # project.yaml CRUD (init/load/save)
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