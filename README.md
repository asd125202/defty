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
- Downloads [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- Installs Python 3.12
- Installs the `defty` CLI and adds it to your PATH

No admin/root required. No conda. No virtual environment to activate manually.

### GPU acceleration (NVIDIA CUDA)

After the standard install, switch to the CUDA-enabled torch wheel:

```bash
uv tool install "git+https://github.com/asd125202/defty.git" --extra cuda --force
```

Apple Silicon (MPS) and CPU are supported out of the box with no extra steps.

### Manual install (for contributors)

```bash
git clone https://github.com/asd125202/defty.git
cd defty
pip install -e ".[dev]"
```

---

## Update & Uninstall

```bash
# Update to latest
defty upgrade

# Uninstall defty
uv tool uninstall defty

# Also remove uv (optional)
# Linux/macOS:
rm ~/.local/bin/uv ~/.local/bin/uvx
# Windows:
Remove-Item $env:USERPROFILE\.local\bin\uv.exe
```

---

## Complete Command Reference

### Project

| Command | Description |
|---------|-------------|
| `defty init [DIRECTORY]` | Create a new Defty project (`project.yaml`) |
| `defty status` | Show project summary: arms, cameras, calibration state |

```bash
defty init                          # init in current directory
defty init ~/my-robot --name "my-robot" --description "SO-101 follower"
defty status
defty status --path /other/project/project.yaml
```

---

### Hardware — Scanning

| Command | Description |
|---------|-------------|
| `defty scan ports` | List all connected serial adapters with hardware fingerprint |
| `defty scan cameras` | List all connected cameras with hardware fingerprint |
| `defty scan cameras --preview` | Live ASCII stream from each camera — press `q` to advance, Ctrl+C to quit |
| `defty scan find-port` | Identify an arm's port by unplugging/replugging *(interactive)* |

```bash
defty scan ports
defty scan cameras
defty scan cameras --preview    # streams live ASCII art — match camera index to physical device

# If 'scan ports' shows nothing on Windows, install the CH341 driver first:
# https://www.wch-ic.com/downloads/CH341SER_EXE.html
# Then use find-port to confirm which COM port your arm is on:
defty scan find-port
```

---

### Hardware — Setup

| Command | Description |
|---------|-------------|
| `defty setup add-arm` | Register a robot arm in the project |
| `defty setup add-camera` | Register a camera in the project |
| `defty setup calibrate` | Calibrate an arm *(only interactive command)* |
| `defty setup update` | Re-scan and update port assignments via fingerprints |
| `defty setup remove-arm` | Remove a registered arm |
| `defty setup remove-camera` | Remove a registered camera |

```bash
# Add arms
defty setup add-arm --port /dev/ttyACM0 --role follower
defty setup add-arm --port /dev/ttyACM1 --role leader
defty setup add-arm --port COM3 --role follower --robot-type so101 --label "right arm"
defty setup add-arm --port /dev/ttyACM0 --role follower --id my_follower

# Add cameras
defty setup add-camera --device /dev/video0 --position wrist
defty setup add-camera --device 0 --position overhead --width 1280 --height 720 --fps 30
defty setup add-camera --device /dev/video2 --position "front" --id cam_front

# Calibrate (physically move the arm when prompted)
defty setup calibrate --arm-id so101_follower_1
defty setup calibrate --arm-id so101_leader_1

# If port names changed after reboot — auto-fix via hardware fingerprint
defty setup update

# Remove
defty setup remove-arm --arm-id so101_follower_1
defty setup remove-camera --camera-id cam_wrist
```

---

### Hardware — Health

| Command | Description |
|---------|-------------|
| `defty health` | Ping all 6 motors per arm + grab a frame from each camera |

```bash
defty health
defty health --path /other/project/project.yaml
```

Output shows per-motor OK/FAIL (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper).

---

### Hardware — Import

| Command | Description |
|---------|-------------|
| `defty hardware import SOURCE` | Copy hardware config from another project |

```bash
# Re-use calibration from a previous project
defty hardware import ~/old-project/project.yaml
defty hardware import ~/old-project/   # also works (finds project.yaml automatically)
```

---

### Teleoperation

| Command | Description |
|---------|-------------|
| `defty teleoperate` | Control follower arm in real-time by moving the leader arm |

```bash
# Auto-selects arms if exactly one leader + one follower is registered
defty teleoperate

# Explicit arm IDs (required when multiple leaders or followers exist)
defty teleoperate --leader-id so101_leader_1 --follower-id so101_follower_1

# Options
defty teleoperate --fps 30              # control loop frequency (default: 60)
defty teleoperate --duration 60         # stop after 60 seconds
defty teleoperate --display             # show motor values + camera feeds via Rerun
```

Press **Ctrl+C** to stop. Both arms disconnect cleanly.

---

### Recording

| Command | Description |
|---------|-------------|
| `defty record` | Record teleoperation episodes as a LeRobot dataset |

```bash
# Basic — creates a new numbered dataset automatically (e.g. my-robot_001)
defty record

# Specify task description (recommended — used during training)
defty record --episodes 20 --task "Pick the red cube"

# Options
defty record --episodes 10 --fps 60
defty record --episode-time 30          # seconds of recording per episode (default: 60)
defty record --reset-time 10            # seconds to reset between episodes (default: 60)
defty record --display                  # show camera feeds + motor values via Rerun
defty record --push-to-hub              # push dataset to HuggingFace Hub after recording

# Name a dataset explicitly
defty record --dataset-name my_run --episodes 10 --task "Push the block"

# Resume (add more episodes to an existing dataset)
defty record --resume                                   # appends to most recent dataset
defty record --resume --dataset-name my_run --episodes 5
```

Each `defty record` run **automatically creates a new numbered dataset** (`my-robot_001`, `_002`, …)
so you never overwrite previous data.  Datasets are stored under `data/` in the project directory.

**Keyboard controls while recording:**

| Key | Action |
|-----|--------|
| `→` Right arrow | End current episode early (saves it, moves to reset phase) |
| `←` Left arrow | Re-record last episode (discards it, starts again) |
| `Esc` | Stop recording immediately |

> **Tip — adding cameras:** register cameras first with `defty setup add-camera`, then they
> are automatically included in every `defty record` session. Use `defty scan cameras --preview`
> to stream live ASCII art from each camera and match its index to the physical device before adding.

---

### Datasets

| Command | Description |
|---------|-------------|
| `defty datasets` | List all recorded datasets with stats |

```bash
defty datasets
```

Example output:
```
Dataset                Episodes   Frames   FPS     Size  Task
────────────────────────────────────────────────────────────────────────────
  my-robot_001               20     1200    30   124.3 MB  Pick the red cube
  my-robot_002               15      900    30    93.1 MB  Push the block
  my-robot_003                5      300    30    31.0 MB  Pick the red cube
```

---

### Training

| Command | Description |
|---------|-------------|
| `defty train` | Train a policy on a recorded dataset |

```bash
# Auto-selects the most recently recorded dataset, uses ACT policy
defty train

# Specify dataset and policy
defty train --dataset-name my-robot_001
defty train --policy act                 # act (default), diffusion, tdmpc, vqbet, pi0, pi0_fast, pi05, smolvla, sac, groot, xvla, wall_x
defty train --policy diffusion

# Training hyperparameters
defty train --steps 100000               # total training steps (default: 10k)
defty train --batch-size 32
defty train --lr 1e-4

# Name the output model explicitly
defty train --model-name my_experiment

# Full example
defty train --dataset-name my-robot_001 --policy act --steps 50000 --batch-size 16

# Push trained model to HuggingFace Hub
defty train --push-to-hub
```

Each training run creates a **new numbered model directory** (`act_my-robot_001_001`, `_002`, …)
under `models/` in the project directory.

---

### Models

| Command | Description |
|---------|-------------|
| `defty models` | List all trained models with stats |

```bash
defty models
```

Example output:
```
Model                      Policy    Steps     Size  Dataset
──────────────────────────────────────────────────────────────────────
  act_my-robot_001_001          act   100000   512.0 MB  my-robot_001
  diffusion_my-robot_001_001  diffusion   50000   340.2 MB  my-robot_001
```

---

### Replay

| Command | Description |
|---------|-------------|
| `defty replay` | Visualize a recorded episode in Rerun |

```bash
# Replay episode 0 from the most recent dataset (opens Rerun viewer)
defty replay

# Specify dataset and episode
defty replay --dataset-name my-robot_001
defty replay --dataset-name my-robot_001 --episode 3    # episode index (0-based)
defty replay -e 5                                        # shorthand

# Save as .rrd file instead of live viewing
defty replay --save                                      # saved to replays/ directory
defty replay --dataset-name my-robot_001 --episode 2 --save
```

Opens the **Rerun viewer** showing synchronized camera frames and joint positions for the selected episode.

---

### Run (Model Inference)

| Command | Description |
|---------|-------------|
| `defty run` | Run a trained policy on the robot |

```bash
# Run the latest model for 1 episode
defty run

# Run a specific model
defty run --model-name act_test_002_001

# Run 5 episodes with live camera feed in Rerun
defty run --episodes 5 --display

# State-only mode (no cameras) — for state-only policies or debugging
defty run --no-vision

# Save the rollout as a dataset for later analysis
defty run --record
defty run --episodes 3 --record --dataset-name my_experiment

# Combined: 10 episodes, display + record
defty run -e 10 --display --record
```

**Controls during execution:**
- **→ (Right arrow)**: End current episode, move to next
- **Esc**: Stop immediately

**Two vision modes:**
| Mode | Flag | Description |
|------|------|-------------|
| With vision | `--vision` (default) | Cameras active, policy sees images + joint state |
| Without vision | `--no-vision` | Cameras disabled, state-only observations |

When `--record` is used, the rollout is saved to `data/run_<model>_001/` (auto-numbered).

---

### Cloud -- Upload & Training

| Command | Description |
|---------|-------------|
| `defty cloud setup` | Configure Hugging Face API token |
| `defty cloud status` | Show cloud configuration and provider status |
| `defty cloud upload` | Upload a dataset to Hugging Face Hub |
| `defty cloud train` | Start a cloud training job |
| `defty cloud check JOB_ID` | Check cloud training job status |

```bash
# Set up your HF token (get one at https://huggingface.co/settings/tokens)
defty cloud setup

# Upload the latest recorded dataset
defty cloud upload
defty cloud upload -d my_robot_003          # specific dataset
defty cloud upload --repo-id user/my-data   # custom repo name
defty cloud upload --private                # private repository

# Cloud training
defty cloud train -d username/my-dataset                 # HF Spaces (default)
defty cloud train -d username/my-dataset --provider google  # Google Vertex AI
defty cloud train -d username/my-dataset --steps 100000

# Check training status
defty cloud check my-training-space
```

After `defty record` completes, you will be prompted to upload the dataset to Hugging Face Hub.
Google Cloud (Vertex AI) and Azure ML providers are available as scaffolds.

---

### Agent System -- .defty Agents

> Define, manage, and run behavior-tree agents using `.defty` files.

| Command | Description |
|---------|-------------|
| `defty agent create <name>` | Generate a new .defty agent from a template |
| `defty agent run <name>` | Parse .defty, build behavior tree, connect hardware, execute |
| `defty agent list` | List all agents with name, version, node count, robot type |
| `defty agent info <name>` | Show agent details: tree structure, dependencies |

```bash
# Create a new agent
defty agent create bread_loop

# Edit the generated .defty file (~/.defty/agents/bread_loop/bread_loop.defty)
# Then run it
defty agent run bread_loop

# List all agents
defty agent list

# Show details
defty agent info bread_loop
```

#### .defty File Format

Agents are defined using `.defty` files -- a restricted Python syntax that is safe to share:

```python
# bread_loop.defty
name = "bread_loop"
version = "1.0"
robot = "so101"

tree = Repeat(
    times=-1,  # infinite loop
    child=Sequence(
        ACTPolicy("models/act_bread_pick"),   # pick bread from plate
        Wait(seconds=2),
        ACTPolicy("models/act_bread_place"),  # place bread back
        Wait(seconds=2),
    )
)
```

**Security:** `.defty` files are parsed with AST validation -- no imports, no function/class
definitions, no attribute access. Only node constructors and basic literals are allowed.

#### Built-in Nodes

| Category | Nodes | Description |
|----------|-------|-------------|
| **Control** | `Sequence`, `Selector`, `Repeat`, `Parallel` | Flow control |
| **Perception** | `CameraCapture` | Read all camera frames into context |
| **Motion** | `JointControl`, `GripperOpen`, `GripperClose`, `RelativeMove` | Direct hardware control |
| **Policy** | `ACTPolicy` | Run trained models (ACT, Diffusion, VQBet) |
| **Utility** | `Wait`, `Condition` | Timing and conditional branching |
| **Composition** | `Agent("name")` | Load another .defty as a sub-tree |

---

### Maintenance

| Command | Description |
|---------|-------------|
| `defty upgrade` | Upgrade defty to the latest version |
| `defty uninstall` | Print uninstall instructions |
| `defty --version` | Show version |

```bash
defty upgrade
defty uninstall
defty --version
defty --help
defty <command> --help    # help for any subcommand
```

---

### Global flags

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Enable debug logging |
| `--version` | Show version and exit |
| `--help` | Show help |

```bash
defty -v health            # debug output
defty -v record --episodes 5
```

---

## Typical Workflow

```bash
# 1. Create project
mkdir ~/my-robot && cd ~/my-robot
defty init --name "my-robot"

# 2. Scan for hardware
defty scan ports                        # find serial ports
defty scan cameras --preview            # visually identify cameras

# 3. Register hardware
defty setup add-arm --port COM3 --role follower
defty setup add-arm --port COM4 --role leader
defty setup add-camera --device 1 --position wrist
defty setup add-camera --device 2 --position overhead

# 4. Calibrate
defty setup calibrate --arm-id so101_follower_1
defty setup calibrate --arm-id so101_leader_1

# 5. Test teleoperation
defty teleoperate --display

# 6. Record data
defty record --episodes 20 --task "Pick the burger" --display

# 7. List what you recorded
defty datasets

# 8. Train
defty train --policy act --steps 10000

# 9. Check trained models
defty models

# 10. Run the model on the robot
defty run                                   # 1 episode, latest model
defty run --episodes 5 --display            # 5 episodes with Rerun
defty run --episodes 3 --record             # run + save rollout

# 11. Replay an episode to review data
defty replay --dataset-name my-robot_001 --episode 0
```

---

## project.yaml structure

```yaml
defty_version: "0.1.0"
project:
  name: my-robot
  description: ""
hardware:
  arms:
    - id: so101_follower_1
      robot_type: so101
      role: follower
      port: /dev/ttyACM0
      hardware_id: "serial:CP2102_USB_to_UART@1-1.2"
      label: "right arm"
      calibration: {}
  cameras:
    - id: cam_wrist
      device: /dev/video0
      hardware_id: "serial:Suyin_HD_Camera_001@platform-usb-0:2.4"
      position: wrist
      width: 640
      height: 480
      fps: 30.0
recording:
  fps: 30
training: {}
```

---

## Project directory layout

```
my-robot/
├── project.yaml              ← hardware config, project metadata
├── calibration/              ← arm calibration files (.json per arm)
│   ├── so101_follower_1.json
│   └── so101_leader_1.json
├── data/                     ← recorded datasets (one dir per run)
│   ├── my-robot_001/         ← defty record run #1
│   │   ├── data/chunk-000/   ← joint positions (parquet)
│   │   ├── meta/info.json    ← episode count, fps, features
│   │   ├── meta/tasks.parquet
│   │   └── videos/           ← camera recordings (AV1)
│   └── my-robot_002/
├── models/                   ← trained models (one dir per run)
│   └── act_my-robot_001_001/
│       ├── defty_model_info.json   ← policy, dataset, steps
│       ├── config.json
│       └── checkpoints/
└── replays/                  ← saved .rrd files from defty replay --save
```

---

## Architecture

```
defty/
├── install.sh / install.ps1   ← one-line installers
├── src/defty/
│   ├── cli.py                 ← all CLI commands (Click)
│   ├── project.py             ← project.yaml CRUD
│   ├── platform.py            ← OS detection
│   ├── utils.py               ← shared utilities (Rerun spawner)
│   ├── hardware/
│   │   ├── detector.py        ← serial + camera scanning
│   │   ├── fingerprint.py     ← USB hardware fingerprinting
│   │   ├── registry.py        ← add/remove/update arms & cameras
│   │   └── health.py          ← motor ping + camera check
│   ├── recording/recorder.py  ← wraps lerobot-record
│   └── training/trainer.py    ← wraps lerobot-train
└── tests/
```

**Supports**: Linux · macOS · Windows  
**Python**: 3.12+  
**Hardware**: SO-101 (leader + follower), USB cameras

---

## License

Apache License 2.0 — Copyright (c) 2026 APRL Technologies Inc.

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
- Downloads [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- Installs Python 3.12
- Installs the `defty` CLI and adds it to your PATH

No admin/root required. No conda. No virtual environment to activate manually.

### GPU acceleration (NVIDIA CUDA)

After the standard install, switch to the CUDA-enabled torch wheel:

```bash
uv tool install "git+https://github.com/asd125202/defty.git" --extra cuda --force
```

Apple Silicon (MPS) and CPU are supported out of the box with no extra steps.

### Manual install (for contributors)

```bash
git clone https://github.com/asd125202/defty.git
cd defty
pip install -e ".[dev]"
```

---

## Update & Uninstall

```bash
# Update to latest
defty upgrade

# Uninstall defty
uv tool uninstall defty

# Also remove uv (optional)
# Linux/macOS:
rm ~/.local/bin/uv ~/.local/bin/uvx
# Windows:
Remove-Item $env:USERPROFILE\.local\bin\uv.exe
```

---

## Complete Command Reference

### Project

| Command | Description |
|---------|-------------|
| `defty init [DIRECTORY]` | Create a new Defty project (`project.yaml`) |
| `defty status` | Show project summary: arms, cameras, calibration state |

```bash
defty init                          # init in current directory
defty init ~/my-robot --name "my-robot" --description "SO-101 follower"
defty status
defty status --path /other/project/project.yaml
```

---

### Hardware — Scanning

| Command | Description |
|---------|-------------|
| `defty scan ports` | List all connected serial adapters with hardware fingerprint |
| `defty scan cameras` | List all connected cameras with hardware fingerprint |
| `defty scan cameras --preview` | Show ASCII art snapshot from each camera to visually identify it |
| `defty scan find-port` | Identify an arm's port by unplugging/replugging *(interactive)* |

```bash
defty scan ports
defty scan cameras
defty scan cameras --preview    # ASCII art frame from each camera — match index to physical device

# If 'scan ports' shows nothing on Windows, install the CH341 driver first:
# https://www.wch-ic.com/downloads/CH341SER_EXE.html
# Then use find-port to confirm which COM port your arm is on:
defty scan find-port
```

---

### Hardware — Setup

| Command | Description |
|---------|-------------|
| `defty setup add-arm` | Register a robot arm in the project |
| `defty setup add-camera` | Register a camera in the project |
| `defty setup calibrate` | Calibrate an arm *(only interactive command)* |
| `defty setup update` | Re-scan and update port assignments via fingerprints |
| `defty setup remove-arm` | Remove a registered arm |
| `defty setup remove-camera` | Remove a registered camera |

```bash
# Add arms
defty setup add-arm --port /dev/ttyACM0 --role follower
defty setup add-arm --port /dev/ttyACM1 --role leader
defty setup add-arm --port COM3 --role follower --robot-type so101 --label "right arm"
defty setup add-arm --port /dev/ttyACM0 --role follower --id my_follower

# Add cameras
defty setup add-camera --device /dev/video0 --position wrist
defty setup add-camera --device 0 --position overhead --width 1280 --height 720 --fps 30
defty setup add-camera --device /dev/video2 --position "front" --id cam_front

# Calibrate (physically move the arm when prompted)
defty setup calibrate --arm-id so101_follower_1
defty setup calibrate --arm-id so101_leader_1

# If port names changed after reboot — auto-fix via hardware fingerprint
defty setup update

# Remove
defty setup remove-arm --arm-id so101_follower_1
defty setup remove-camera --camera-id cam_wrist
```

---

### Hardware — Health

| Command | Description |
|---------|-------------|
| `defty health` | Ping all 6 motors per arm + grab a frame from each camera |

```bash
defty health
defty health --path /other/project/project.yaml
```

Output shows per-motor OK/FAIL (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper).

---

### Hardware — Import

| Command | Description |
|---------|-------------|
| `defty hardware import SOURCE` | Copy hardware config from another project |

```bash
# Re-use calibration from a previous project
defty hardware import ~/old-project/project.yaml
defty hardware import ~/old-project/   # also works (finds project.yaml automatically)
```

---

### Teleoperation

| Command | Description |
|---------|-------------|
| `defty teleoperate` | Control follower arm in real-time by moving the leader arm |

```bash
# Auto-selects arms if exactly one leader + one follower is registered
defty teleoperate

# Explicit arm IDs (required when multiple leaders or followers exist)
defty teleoperate --leader-id so101_leader_1 --follower-id so101_follower_1

# Options
defty teleoperate --fps 30              # control loop frequency (default: 60)
defty teleoperate --duration 60         # stop after 60 seconds
defty teleoperate --display             # show motor values + camera feeds via Rerun
```

Press **Ctrl+C** to stop. Both arms disconnect cleanly.

---

### Recording

| Command | Description |
|---------|-------------|
| `defty record` | Record teleoperation episodes via LeRobot |

```bash
defty record                                              # 1 episode, defaults from project.yaml
defty record --episodes 20 --task "Pick the red cube"    # task description is recommended
defty record --episodes 10 --fps 60
defty record --dataset-name my_dataset
defty record --episode-time 30 --reset-time 10           # seconds per episode / reset
defty record --display                                    # show camera feeds via Rerun
defty record --push-to-hub                               # push to HuggingFace Hub after recording
```

**Keyboard controls while recording:**

| Key | Action |
|-----|--------|
| `→` Right arrow | End current episode early (saves it, moves to reset phase) |
| `←` Left arrow | Re-record last episode (discards it, records again) |
| `Esc` | Stop recording immediately |

> **Tip — adding cameras:** register cameras first with `defty setup add-camera`, then they
> are automatically included in every `defty record` session. Use `defty scan cameras --preview`
> to match each camera index to a physical device before adding.

---

### Training

| Command | Description |
|---------|-------------|
| `defty train` | Train a policy on recorded data via LeRobot |

```bash
defty train                             # ACT policy, settings from project.yaml
defty train --policy act
defty train --policy diffusion
defty train --epochs 200 --batch-size 32 --lr 1e-4
defty train --dataset-name my_dataset --output-dir outputs/run1
defty train --push-to-hub               # push model to HuggingFace Hub
```

---

### Maintenance

| Command | Description |
|---------|-------------|
| `defty upgrade` | Upgrade defty to the latest version |
| `defty uninstall` | Print uninstall instructions |
| `defty --version` | Show version |

```bash
defty upgrade
defty uninstall
defty --version
defty --help
defty <command> --help    # help for any subcommand
```

---

### Global flags

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Enable debug logging |
| `--version` | Show version and exit |
| `--help` | Show help |

```bash
defty -v health            # debug output
defty -v record --episodes 5
```

---

## project.yaml structure

```yaml
defty_version: "0.1.0"
project:
  name: my-robot
  description: ""
hardware:
  arms:
    - id: so101_follower_1
      robot_type: so101
      role: follower
      port: /dev/ttyACM0
      hardware_id: "serial:CP2102_USB_to_UART@1-1.2"
      label: "right arm"
      calibration: {}
  cameras:
    - id: cam_wrist
      device: /dev/video0
      hardware_id: "serial:Suyin_HD_Camera_001@platform-usb-0:2.4"
      position: wrist
      width: 640
      height: 480
      fps: 30.0
recording:
  fps: 30
  dataset_dir: data
training: {}
```

---

## Architecture

```
defty/
├── install.sh / install.ps1   ← one-line installers
├── src/defty/
│   ├── cli.py                 ← all CLI commands (Click)
│   ├── project.py             ← project.yaml CRUD
│   ├── platform.py            ← OS detection
│   ├── hardware/
│   │   ├── detector.py        ← serial + camera scanning
│   │   ├── fingerprint.py     ← USB hardware fingerprinting
│   │   ├── registry.py        ← add/remove/update arms & cameras
│   │   └── health.py          ← motor ping + camera check
│   ├── recording/recorder.py  ← wraps lerobot-record
│   └── training/trainer.py    ← wraps lerobot-train
└── tests/
```

**Supports**: Linux · macOS · Windows  
**Python**: 3.12+  
**Hardware**: SO-101 (leader + follower), USB cameras

---

## License

Apache License 2.0 — Copyright (c) 2026 APRL Technologies Inc.