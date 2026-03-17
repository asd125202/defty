# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
- `src/defty/cli.py` — full Click CLI: `defty init`, `status`, `scan ports`, `scan cameras`, `setup add-arm`, `setup add-camera`, `setup calibrate`, `setup update`, `setup remove-arm`, `setup remove-camera`, `health`, `record`, `train`, `hardware import`
- `tests/test_project.py` — project.yaml CRUD tests
- `tests/test_registry.py` — hardware registry tests
- `tests/test_platform.py` — OS detection tests
- `spec/project-yaml.md` — project.yaml schema v0.1 draft
- `spec/skill-format.md` — .skill file format v0.1 draft

## [0.0.0] — 2026-03-17

### Added

- Initial repository scaffold: README, CONTRIBUTING, LICENSE, STRUCTURE, CHANGELOG