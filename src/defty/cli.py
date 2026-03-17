# Copyright (c) 2026 APRL Technologies Inc. All rights reserved.
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
"""Defty command-line interface.

Commands that require a project (setup, health, record, train) automatically
search upward for a project.yaml.  If none is found they ask whether to
initialise one in the current directory before proceeding.

Commands that do NOT need a project (scan, upgrade, version) work anywhere.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from defty.__version__ import __version__

logger = logging.getLogger(__name__)

__all__ = ["main"]


# ── Root group ───────────────────────────────────────────────────────────────


@click.group()
@click.version_option(__version__, prog_name="defty")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def main(verbose: bool) -> None:
    """Defty -- Physical AI IDE for robot intelligence development."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(name)s: %(message)s",
    )


# ── Project helpers ──────────────────────────────────────────────────────────


def _ensure_project(path: str | None = None) -> tuple[Path, dict[str, Any]]:
    """Locate or create a project.yaml, then load and return it.

    Search order:
    1. Explicit *path* argument (file or directory).
    2. Walk upward from the current working directory.
    3. If nothing found and stdin is a TTY, ask the user whether to
       initialise a new project in the current directory.
    4. If stdin is not a TTY (scripted/piped), exit with an error.

    Args:
        path: Optional explicit path to ``project.yaml`` or its parent dir.

    Returns:
        ``(yaml_path, project_dict)`` tuple.
    """
    from defty.project import find_project_root, init_project, load_project

    # 1. Explicit path provided
    if path is not None:
        p = Path(path)
        yaml_path = p if p.name == "project.yaml" else p / "project.yaml"
        return yaml_path, load_project(yaml_path)

    # 2. Search upward from cwd
    try:
        yaml_path = find_project_root()
        return yaml_path, load_project(yaml_path)
    except FileNotFoundError:
        pass

    # 3. Not found — ask or fail
    cwd = Path.cwd()
    if sys.stdin.isatty():
        click.echo(f"No project.yaml found (searched upward from {cwd}).")
        if click.confirm(f"Initialise a new Defty project in {cwd}?", default=True):
            yaml_path = init_project(cwd)
            click.echo(f"Initialised project at {yaml_path}")
            return yaml_path, load_project(yaml_path)
        click.echo("Aborted.")
        sys.exit(0)
    else:
        click.echo(
            "Error: No project.yaml found. Run 'defty init' first.", err=True
        )
        sys.exit(1)


# ── defty init ───────────────────────────────────────────────────────────────


@main.command()
@click.argument("directory", default=".")
@click.option("--name", "-n", default=None, help="Project name (defaults to dir name).")
@click.option("--description", "-d", default="", help="Project description.")
def init(directory: str, name: str | None, description: str) -> None:
    """Initialise a new Defty project.

    Creates project.yaml in DIRECTORY (default: current directory).
    If a project.yaml already exists anywhere above the current directory,
    this command will warn but still proceed.
    """
    from defty.project import find_project_root, init_project

    # Warn if already inside a project
    try:
        existing = find_project_root()
        click.echo(f"Warning: already inside a project at {existing}")
        if not click.confirm("Create a nested project anyway?", default=False):
            sys.exit(0)
    except FileNotFoundError:
        pass

    try:
        yaml_path = init_project(directory, name=name, description=description)
        click.echo(f"Initialised project at {yaml_path}")
    except FileExistsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty status ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None, help="Path to project.yaml.")
def status(path: str | None) -> None:
    """Show current project status."""
    from defty.platform import detect_os

    yaml_path, project = _ensure_project(path)

    proj = project.get("project", {})
    hw = project.get("hardware", {})
    arms = hw.get("arms", [])
    cameras = hw.get("cameras", [])

    click.echo(f"Project:  {proj.get('name', '(unnamed)')}")
    click.echo(f"Location: {yaml_path.parent}")
    click.echo(f"OS:       {detect_os().value}")
    click.echo(f"Arms:     {len(arms)}")
    for arm in arms:
        calib = "calibrated" if arm.get("calibration") else "not calibrated"
        click.echo(f"  - {arm['id']} ({arm.get('role', '?')}) on {arm.get('port', '?')} [{calib}]")
    click.echo(f"Cameras:  {len(cameras)}")
    for cam in cameras:
        click.echo(f"  - {cam['id']} on {cam.get('device', '?')} ({cam.get('position', '?')})")


# ── defty scan ───────────────────────────────────────────────────────────────


@main.group()
def scan() -> None:
    """Scan for connected hardware. Works without a project."""


@scan.command("ports")
def scan_ports() -> None:
    """List all connected serial ports with fingerprint data."""
    from defty.hardware.detector import list_serial_ports

    ports = list_serial_ports()
    if not ports:
        click.echo("No serial ports found.")
        if sys.platform == "win32":
            click.echo("")
            click.echo("Tip: Feetech/Dynamixel arms use a CH340/CH341 USB-serial chip.")
            click.echo("     If the arm is plugged in but missing here, install the driver:")
            click.echo("     https://www.wch-ic.com/downloads/CH341SER_EXE.html")
            click.echo("     Then re-plug the USB cable and retry.")
            click.echo("")
            click.echo("     To identify the port via plug/unplug, run:  defty scan find-port")
        return
    for p in ports:
        click.echo(f"  {p.port}")
        click.echo(f"    description: {p.description or '(none)'}")
        click.echo(f"    hardware_id: {p.hardware_id or '(none)'}")
        click.echo(f"    vendor:      {p.vendor or '(unknown)'}")
        click.echo(f"    model:       {p.model or '(unknown)'}")
        click.echo(f"    serial:      {p.serial or '(none)'}")


@scan.command("find-port")
def scan_find_port() -> None:
    """Identify a serial port by unplugging and replugging the device.

    Lists ports before and after disconnection, then prints which port
    disappeared -- that is your device's port.  This is the most
    reliable method when 'defty scan ports' shows nothing or multiple
    unknown ports.

    NOTE: This command is intentionally interactive (requires a cable
    unplug).  All other Defty commands are non-interactive.
    """
    import time

    from serial.tools import list_ports as _lp

    def _get_ports() -> set[str]:
        return {p.device for p in _lp.comports()}

    click.echo("=== defty scan find-port ===")
    click.echo("")
    ports_before = _get_ports()
    if ports_before:
        click.echo(f"Ports currently visible ({len(ports_before)}):")
        for p in sorted(ports_before):
            click.echo(f"  {p}")
    else:
        click.echo("No serial ports visible yet.")
    click.echo("")
    click.echo("Unplug the USB cable from your arm, then press Enter...")
    input()

    time.sleep(0.5)
    ports_after = _get_ports()
    disappeared = sorted(ports_before - ports_after)
    appeared = sorted(ports_after - ports_before)

    if len(disappeared) == 1:
        click.echo(f"\n✓ Found it!  Your arm is on port: {disappeared[0]}")
        click.echo("\nPlease reconnect the USB cable.")
    elif len(disappeared) == 0:
        click.echo("\nNo port disappeared.  Possible causes:")
        click.echo("  • The USB cable was not unplugged, or")
        click.echo("  • The driver is not installed (Windows: install CH341SER)")
        click.echo("    https://www.wch-ic.com/downloads/CH341SER_EXE.html")
    else:
        click.echo(f"\nMultiple ports disappeared: {disappeared}")
        click.echo("Unplug one device at a time and retry.")

    if appeared:
        click.echo(f"\nNote: new port(s) appeared during the test: {appeared}")


@scan.command("cameras")
def scan_cameras() -> None:
    """List all connected cameras with fingerprint data."""
    from defty.hardware.detector import list_cameras

    cameras = list_cameras()
    if not cameras:
        click.echo("No cameras found.")
        return
    for c in cameras:
        click.echo(f"  [{c.index}] {c.name or '(unnamed)'}")
        click.echo(f"    device:      {c.device}")
        click.echo(f"    hardware_id: {c.hardware_id or '(none)'}")


# ── defty setup ──────────────────────────────────────────────────────────────


@main.group()
def setup() -> None:
    """Add, configure, or calibrate hardware."""


@setup.command("add-arm")
@click.option("--port", required=True, help="Serial port (e.g. /dev/ttyACM0, COM3).")
@click.option("--role", required=True, type=click.Choice(["leader", "follower"]))
@click.option("--robot-type", default="so101", help="Robot type (default: so101).")
@click.option("--id", "arm_id", default=None, help="Arm ID (auto-generated if omitted).")
@click.option("--label", default="", help="Human-readable position label.")
@click.option("--hardware-id", default="", help="Hardware fingerprint (auto-detected if omitted).")
@click.option("--path", "-p", default=None, hidden=True)
def setup_add_arm(port, role, robot_type, arm_id, label, hardware_id, path) -> None:
    """Register a new robot arm in the project."""
    from defty.hardware.detector import list_serial_ports
    from defty.hardware.registry import add_arm
    from defty.project import save_project

    yaml_path, project = _ensure_project(path)

    if not hardware_id:
        for sp in list_serial_ports():
            if sp.port == port and sp.hardware_id:
                hardware_id = sp.hardware_id
                click.echo(f"Auto-detected hardware_id: {hardware_id}")
                break

    try:
        add_arm(project, arm_id=arm_id, port=port, hardware_id=hardware_id,
                robot_type=robot_type, role=role, label=label)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    save_project(yaml_path, project)
    final_id = arm_id or project["hardware"]["arms"][-1]["id"]
    click.echo(f"Added arm '{final_id}' on {port}")


@setup.command("add-camera")
@click.option("--device", required=True, help="Camera device path or index.")
@click.option("--position", default="", help="Position label (e.g. wrist, overhead).")
@click.option("--id", "camera_id", default=None, help="Camera ID (auto-generated if omitted).")
@click.option("--hardware-id", default="", help="Hardware fingerprint (auto-detected if omitted).")
@click.option("--width", default=640, type=int)
@click.option("--height", default=480, type=int)
@click.option("--fps", default=30.0, type=float)
@click.option("--path", "-p", default=None, hidden=True)
def setup_add_camera(device, position, camera_id, hardware_id, width, height, fps, path) -> None:
    """Register a new camera in the project."""
    from defty.hardware.fingerprint import resolve_camera_hardware_id
    from defty.hardware.registry import add_camera
    from defty.project import save_project

    yaml_path, project = _ensure_project(path)

    if not hardware_id:
        hw_id = resolve_camera_hardware_id(device)
        if hw_id:
            hardware_id = hw_id
            click.echo(f"Auto-detected hardware_id: {hardware_id}")

    try:
        add_camera(project, camera_id=camera_id, device=device, hardware_id=hardware_id,
                   position=position, width=width, height=height, fps=fps)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    save_project(yaml_path, project)
    final_id = camera_id or project["hardware"]["cameras"][-1]["id"]
    click.echo(f"Added camera '{final_id}' -> {device}")


@setup.command("calibrate")
@click.option("--arm-id", required=True, help="ID of the arm to calibrate.")
@click.option("--path", "-p", default=None, hidden=True)
def setup_calibrate(arm_id, path) -> None:
    """Calibrate a robot arm (interactive -- requires physical arm movement)."""
    import json

    from defty.project import save_project

    yaml_path, project = _ensure_project(path)

    arms = project.get("hardware", {}).get("arms", [])
    arm = next((a for a in arms if a["id"] == arm_id), None)
    if arm is None:
        click.echo(f"Error: Arm '{arm_id}' not found. Run 'defty status' to list arms.", err=True)
        sys.exit(1)

    port = arm.get("port", "")
    role = arm.get("role", "follower")
    robot_type = arm.get("robot_type", "so101")

    if not port:
        click.echo(f"Error: Arm '{arm_id}' has no port. Run 'defty setup update' first.", err=True)
        sys.exit(1)

    # Calibration files are stored alongside project.yaml under calibration/
    calibration_dir = yaml_path.parent / "calibration"
    calibration_dir.mkdir(exist_ok=True)

    click.echo(f"Calibrating '{arm_id}' ({robot_type} {role}) on {port}...")
    click.echo("Follow the prompts to physically move the arm.")

    try:
        if robot_type in ("so101", "so100") and role == "follower":
            from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig
            robot = SOFollower(SOFollowerRobotConfig(
                port=port, id=arm_id, calibration_dir=calibration_dir,
            ))
            robot.connect(calibrate=False)
            robot.calibrate()
            robot.disconnect()
        elif robot_type in ("so101", "so100") and role == "leader":
            from lerobot.teleoperators.so_leader import SOLeader, SOLeaderTeleopConfig
            leader = SOLeader(SOLeaderTeleopConfig(
                port=port, id=arm_id, calibration_dir=calibration_dir,
            ))
            leader.connect(calibrate=False)
            leader.calibrate()
            leader.disconnect()
        else:
            click.echo(f"Error: Calibration not implemented for {robot_type} {role}", err=True)
            sys.exit(1)

        # Load the JSON calibration file LeRobot saved and store a reference in project.yaml
        cal_file = calibration_dir / f"{arm_id}.json"
        if cal_file.exists():
            arm["calibration"] = json.loads(cal_file.read_text(encoding="utf-8"))

        save_project(yaml_path, project)
        click.echo(f"Calibration saved for '{arm_id}'.")
    except ImportError:
        click.echo("Error: LeRobot is not installed. Run: defty upgrade", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Calibration failed: {exc}", err=True)
        sys.exit(1)


@setup.command("update")
@click.option("--path", "-p", default=None, hidden=True)
def setup_update(path) -> None:
    """Re-scan hardware and update port assignments using fingerprints."""
    from defty.hardware.registry import update_ports
    from defty.project import save_project

    yaml_path, project = _ensure_project(path)
    update_ports(project)
    save_project(yaml_path, project)
    click.echo("Hardware port assignments updated.")


@setup.command("remove-arm")
@click.option("--arm-id", required=True)
@click.option("--path", "-p", default=None, hidden=True)
def setup_remove_arm(arm_id, path) -> None:
    """Remove a registered arm from the project."""
    from defty.hardware.registry import remove_arm
    from defty.project import save_project

    yaml_path, project = _ensure_project(path)
    try:
        remove_arm(project, arm_id)
        save_project(yaml_path, project)
        click.echo(f"Removed arm '{arm_id}'.")
    except KeyError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@setup.command("remove-camera")
@click.option("--camera-id", required=True)
@click.option("--path", "-p", default=None, hidden=True)
def setup_remove_camera(camera_id, path) -> None:
    """Remove a registered camera from the project."""
    from defty.hardware.registry import remove_camera
    from defty.project import save_project

    yaml_path, project = _ensure_project(path)
    try:
        remove_camera(project, camera_id)
        save_project(yaml_path, project)
        click.echo(f"Removed camera '{camera_id}'.")
    except KeyError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty health ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None, help="Path to project.yaml.")
def health(path: str | None) -> None:
    """Check the health of all registered hardware."""
    from defty.hardware.health import check_all_health

    yaml_path, project = _ensure_project(path)
    report = check_all_health(project)

    for arm_report in report.arms:
        icon = "OK  " if arm_report.all_motors_ok else "FAIL"
        click.echo(f"[{icon}] Arm {arm_report.arm_id}  port={arm_report.port}")
        if arm_report.error:
            click.echo(f"       Error: {arm_report.error}")
        for m in arm_report.motors:
            m_icon = "OK  " if m.online else "FAIL"
            click.echo(f"       [{m_icon}] motor {m.motor_id} ({m.name})")
            if m.error:
                click.echo(f"              {m.error}")

    for cam_report in report.cameras:
        icon = "OK  " if cam_report.online else "FAIL"
        click.echo(f"[{icon}] Camera {cam_report.camera_id}  device={cam_report.device}")
        if cam_report.error:
            click.echo(f"       Error: {cam_report.error}")

    click.echo("")
    if report.all_ok:
        click.echo("All hardware checks passed.")
    else:
        click.echo("Some hardware checks failed.", err=True)
        sys.exit(1)


# ── defty teleoperate ────────────────────────────────────────────────────────


@main.command("teleoperate")
@click.option("--leader-id", default=None, help="ID of the leader arm (auto-detected if unique).")
@click.option("--follower-id", default=None, help="ID of the follower arm (auto-detected if unique).")
@click.option("--fps", default=60, type=int, show_default=True, help="Control loop target FPS.")
@click.option("--duration", default=None, type=float, help="Stop after N seconds (default: until Ctrl+C).")
@click.option("--display", is_flag=True, help="Show motor values and camera feeds via Rerun.")
@click.option("--path", "-p", default=None, hidden=True)
def teleoperate(leader_id, follower_id, fps, duration, display, path) -> None:
    """Control a follower arm in real-time by moving a leader arm.

    Leader and follower are read from project.yaml.  If the project has
    exactly one arm of each role they are selected automatically; otherwise
    pass ``--leader-id`` / ``--follower-id`` explicitly.

    Press Ctrl+C to stop.
    """
    yaml_path, project = _ensure_project(path)
    arms = project.get("hardware", {}).get("arms", [])

    leaders = [a for a in arms if a.get("role") == "leader"]
    followers = [a for a in arms if a.get("role") == "follower"]

    # Resolve leader arm
    if leader_id:
        leader_arm = next((a for a in arms if a["id"] == leader_id), None)
        if leader_arm is None:
            click.echo(f"Error: leader arm '{leader_id}' not found.", err=True)
            sys.exit(1)
    elif len(leaders) == 1:
        leader_arm = leaders[0]
    elif len(leaders) == 0:
        click.echo("Error: no leader arm registered. Run 'defty setup add-arm --role leader'.", err=True)
        sys.exit(1)
    else:
        ids = [a["id"] for a in leaders]
        click.echo(f"Error: multiple leaders found {ids}. Specify one with --leader-id.", err=True)
        sys.exit(1)

    # Resolve follower arm
    if follower_id:
        follower_arm = next((a for a in arms if a["id"] == follower_id), None)
        if follower_arm is None:
            click.echo(f"Error: follower arm '{follower_id}' not found.", err=True)
            sys.exit(1)
    elif len(followers) == 1:
        follower_arm = followers[0]
    elif len(followers) == 0:
        click.echo("Error: no follower arm registered. Run 'defty setup add-arm --role follower'.", err=True)
        sys.exit(1)
    else:
        ids = [a["id"] for a in followers]
        click.echo(f"Error: multiple followers found {ids}. Specify one with --follower-id.", err=True)
        sys.exit(1)

    for arm in (leader_arm, follower_arm):
        if not arm.get("port"):
            click.echo(
                f"Error: Arm '{arm['id']}' has no port. Run 'defty setup update'.", err=True
            )
            sys.exit(1)

    calibration_dir = yaml_path.parent / "calibration"

    try:
        from lerobot.processor import make_default_processors
        from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig
        from lerobot.scripts.lerobot_teleoperate import teleop_loop
        from lerobot.teleoperators.so_leader import SOLeader, SOLeaderTeleopConfig
    except ImportError as exc:
        click.echo(f"Error: LeRobot not available — {exc}", err=True)
        sys.exit(1)

    teleop = SOLeader(SOLeaderTeleopConfig(
        port=leader_arm["port"],
        id=leader_arm["id"],
        calibration_dir=calibration_dir,
    ))
    robot = SOFollower(SOFollowerRobotConfig(
        port=follower_arm["port"],
        id=follower_arm["id"],
        calibration_dir=calibration_dir,
    ))

    teleop_action_proc, robot_action_proc, robot_obs_proc = make_default_processors()

    click.echo(f"Teleoperate  leader={leader_arm['id']} ({leader_arm['port']})  "
               f"→  follower={follower_arm['id']} ({follower_arm['port']})")
    click.echo(f"FPS: {fps}   Duration: {f'{duration}s' if duration else 'until Ctrl+C'}")
    click.echo("Press Ctrl+C to stop.")

    teleop.connect()
    robot.connect()

    try:
        teleop_loop(
            teleop=teleop,
            robot=robot,
            fps=fps,
            display_data=display,
            duration=duration,
            teleop_action_processor=teleop_action_proc,
            robot_action_processor=robot_action_proc,
            robot_observation_processor=robot_obs_proc,
        )
    except KeyboardInterrupt:
        click.echo("\nTeleoperation stopped.")
    finally:
        teleop.disconnect()
        robot.disconnect()


# ── defty record ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None, help="Path to project.yaml.")
@click.option("--episodes", "-e", default=1, type=int, show_default=True, help="Number of episodes to record.")
@click.option("--fps", default=None, type=int, help="Override recording FPS.")
@click.option("--task", default=None, help="One-line task description, e.g. 'Pick the red cube'.")
@click.option("--dataset-name", default=None, help="Dataset name / HuggingFace repo_id.")
@click.option("--episode-time", default=60.0, type=float, show_default=True, help="Seconds per episode.")
@click.option("--reset-time", default=60.0, type=float, show_default=True, help="Seconds to reset between episodes.")
@click.option("--display", is_flag=True, help="Show camera feeds via Rerun.")
@click.option("--push-to-hub", is_flag=True, help="Push dataset to HuggingFace Hub.")
def record(path, episodes, fps, task, dataset_name, episode_time, reset_time, display, push_to_hub) -> None:
    """Record teleoperation episodes.

    Uses the leader arm to control the follower arm and records the
    resulting trajectories as a LeRobot dataset.

    Example:

    \b
        defty record --episodes 20 --task "Pick the red cube"
    """
    from defty.recording.recorder import record as do_record

    _ensure_project(path)
    try:
        do_record(
            project_path=path,
            num_episodes=episodes,
            fps=fps,
            task=task,
            dataset_name=dataset_name,
            episode_time_s=episode_time,
            reset_time_s=reset_time,
            display=display,
            push_to_hub=push_to_hub,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty train ──────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None)
@click.option("--policy", default="act")
@click.option("--dataset-name", default=None)
@click.option("--output-dir", default=None)
@click.option("--epochs", default=None, type=int)
@click.option("--batch-size", default=None, type=int)
@click.option("--lr", default=None, type=float)
@click.option("--push-to-hub", is_flag=True)
def train(path, policy, dataset_name, output_dir, epochs, batch_size, lr, push_to_hub) -> None:
    """Train a policy on recorded data."""
    from defty.training.trainer import train as do_train

    _ensure_project(path)
    try:
        do_train(project_path=path, policy=policy, dataset_name=dataset_name,
                 output_dir=output_dir, num_epochs=epochs, batch_size=batch_size,
                 learning_rate=lr, push_to_hub=push_to_hub)
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty hardware import ────────────────────────────────────────────────────


@main.group()
def hardware() -> None:
    """Hardware data management."""


@hardware.command("import")
@click.argument("source_path", type=click.Path(exists=True))
@click.option("--path", "-p", default=None, hidden=True)
def hardware_import(source_path, path) -> None:
    """Import hardware config from another project or file."""
    import yaml

    from defty.project import save_project

    yaml_path, project = _ensure_project(path)

    source = Path(source_path)
    if source.is_dir():
        source = source / "project.yaml"
    if not source.exists():
        click.echo(f"Error: Source not found: {source}", err=True)
        sys.exit(1)

    with open(source, encoding="utf-8") as fh:
        source_data = yaml.safe_load(fh)

    source_hw = source_data.get("hardware", {})
    hw = project.setdefault("hardware", {})
    arms = hw.setdefault("arms", [])
    cameras = hw.setdefault("cameras", [])

    existing_arm_ids = {a["id"] for a in arms}
    existing_cam_ids = {c["id"] for c in cameras}

    added_arms = sum(1 for a in source_hw.get("arms", [])
                     if a["id"] not in existing_arm_ids and not arms.append(a))
    added_cams = sum(1 for c in source_hw.get("cameras", [])
                     if c["id"] not in existing_cam_ids and not cameras.append(c))

    save_project(yaml_path, project)
    click.echo(f"Imported {added_arms} arm(s) and {added_cams} camera(s) from {source}")


# ── defty upgrade ────────────────────────────────────────────────────────────


@main.command()
def upgrade() -> None:
    """Upgrade defty to the latest version from GitHub."""
    repo_url = "https://github.com/asd125202/defty.git"

    uv = _find_uv()
    if uv is None:
        click.echo("Error: 'uv' not found. Install: https://docs.astral.sh/uv/", err=True)
        sys.exit(1)

    if sys.platform == "win32":
        # On Windows the running defty.exe locks its own Scripts\ directory, so
        # uv cannot overwrite it while this process is alive.  Workaround:
        # write a small batch script to a temp location, spawn it in a new
        # console window (so the user can see progress), then exit immediately
        # so the lock is released.  The batch script waits for our PID to
        # disappear before calling uv.
        import os
        import tempfile

        pid = os.getpid()
        bat_lines = [
            "@echo off",
            f"echo Waiting for defty to exit (PID {pid})...",
            ":wait",
            f'tasklist /FI "PID eq {pid}" 2>nul | find /I "{pid}" >nul',
            "if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait)",
            f"echo Upgrading defty from {repo_url}...",
            f'"{uv}" tool install git+{repo_url} --force',
            "if errorlevel 1 (echo. & echo Upgrade FAILED. & pause) else (echo. & echo defty upgraded successfully. & timeout /t 3)",
        ]
        bat_path = Path(tempfile.gettempdir()) / "defty_upgrade.bat"
        bat_path.write_text("\r\n".join(bat_lines), encoding="utf-8")

        subprocess.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        click.echo("Upgrade started in a new window — please wait for it to complete.")
        sys.exit(0)

    # Linux / macOS: no file-locking issue, run directly.
    click.echo(f"Upgrading defty from {repo_url}...")
    result = subprocess.run([uv, "tool", "install", f"git+{repo_url}", "--force"], check=False)
    if result.returncode != 0:
        click.echo("Upgrade failed. Check the output above.", err=True)
        sys.exit(result.returncode)
    click.echo("defty upgraded successfully.")


@main.command()
def uninstall() -> None:
    """Print uninstall instructions for defty."""
    click.echo("To uninstall defty:")
    click.echo("  uv tool uninstall defty")
    click.echo("")
    click.echo("To also remove uv:")
    click.echo("  Linux/macOS:  rm ~/.local/bin/uv ~/.local/bin/uvx")
    click.echo("  Windows:      Remove-Item $env:USERPROFILE\\.local\\bin\\uv.exe")


# ── helpers ───────────────────────────────────────────────────────────────────


def _find_uv() -> str | None:
    """Find the uv executable path."""
    return shutil.which("uv")