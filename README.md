# Defty — Physical AI IDE

> Local-first IDE and skill format standard for robot intelligence development.

Defty wraps [LeRobot](https://github.com/huggingface/lerobot) with a clean CLI and project system
so you can go from unboxing a robot arm to recording teleoperation data in minutes.

---

## Installation

### One-line install (recommended)

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/asd125202/defty/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/asd125202/defty/main/install.ps1 | iex
```

The installer automatically:
- Downloads and installs [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- Installs Python 3.12 via uv
- Installs the `defty` CLI
- Adds `defty` to your PATH

No admin/root required. No conda. No virtual environment to activate.

### Manual install (for contributors)

```bash
git clone https://github.com/asd125202/defty.git
cd defty
pip install -e ".[dev]"
```

### GPU acceleration (NVIDIA CUDA)

After installation, switch to the CUDA-enabled torch wheel:

```bash
uv tool install "git+https://github.com/asd125202/defty.git" --extra cuda --force
```

Apple Silicon (MPS) and CPU are supported out of the box — no extra steps needed.

---

## Quick start

```bash
# 1. Create a project
mkdir my-robot && cd my-robot
defty init --name "my-robot"

# 2. See what hardware is connected
defty scan ports      # serial adapters (robot arms)
defty scan cameras    # video devices

# 3. Register hardware (use port from scan output)
defty setup add-arm --port /dev/ttyACM0 --role follower
defty setup add-arm --port /dev/ttyACM1 --role leader
defty setup add-camera --device /dev/video0 --position wrist

# 4. Calibrate (only interactive step — requires physical arm movement)
defty setup calibrate --arm-id so101_follower_1
defty setup calibrate --arm-id so101_leader_1

# 5. Health check (pings all 6 motors + cameras)
defty health

# 6. Record teleoperation data
defty record --episodes 10

# 7. Train a policy
defty train --policy act --epochs 100
```

> **Windows**: replace `/dev/ttyACM0` with `COM3` and `/dev/video0` with `0`.

---

## Architecture

```
defty/
├── src/defty/
│   ├── cli.py          ← Click CLI (all commands)
│   ├── project.py      ← project.yaml CRUD
│   ├── platform.py     ← cross-platform OS detection
│   ├── hardware/       ← detection, fingerprinting, health, registry
│   ├── recording/      ← wraps lerobot-record
│   └── training/       ← wraps lerobot-train
├── install.sh          ← one-line installer (Linux/macOS)
└── install.ps1         ← one-line installer (Windows)
```

Three-layer design:
1. **Core library** (`src/defty/`) — open source, Apache 2.0
2. **CLI** (`defty` command) — open source, Apache 2.0
3. **GUI** — future closed-source layer on top

---

## License

Apache License 2.0 — Copyright (c) 2026 APRL Technologies Inc.