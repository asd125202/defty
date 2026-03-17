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
""""""Defty command-line interface.

All commands are strictly non-interactive — every parameter is passed
via flags.  The only exception is `defty setup calibrate` which
requires the user to physically move the robot arm.
""""""

from __future__ import annotations

import json
import logging
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
    """"""Defty — Physical AI IDE for robot intelligence development.""""""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(name)s: %(message)s",
    )


# ── defty init ───────────────────────────────────────────────────────────────


@main.command()
@click.argument("directory", default=".")
@click.option("--name", "-n", default=None, help="Project name (defaults to dir name).")
@click.option("--description", "-d", default="", help="Project description.")
def init(directory: str, name: str | None, description: str) -> None:
    """"""Initialise a new Defty project.""""""
    from defty.project import init_project

    try:
        path = init_project(directory, name=name, description=description)
        click.echo(f"Initialised project at {path}")
    except FileExistsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty status ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None, help="Path to project.yaml.")
def status(path: str | None) -> None:
    """"""Show current project status.""""""
    from defty.platform import detect_os
    from defty.project import load_project

    try:
        project = load_project(path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    proj = project.get("project", {})
    hw = project.get("hardware", {})
    arms = hw.get("arms", [])
    cameras = hw.get("cameras", [])

    click.echo(f"Project:  {proj.get('name', '(unnamed)')}")
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
    """"""Scan for connected hardware.""""""


@scan.command("ports")
def scan_ports() -> None:
    """"""List all connected serial ports with fingerprint data.""""""
    from defty.hardware.detector import list_serial_ports

    ports = list_serial_ports()
    if not ports:
        click.echo("No serial ports found.")
        return

    for p in ports:
        click.echo(f"  {p.port}")
        click.echo(f"    hardware_id: {p.hardware_id or '(none)'}")
        click.echo(f"    vendor:      {p.vendor or '(unknown)'}")
        click.echo(f"    model:       {p.model or '(unknown)'}")
        click.echo(f"    serial:      {p.serial or '(none)'}")


@scan.command("cameras")
def scan_cameras() -> None:
    """"""List all connected cameras with fingerprint data.""""""
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
    """"""Add, configure, or calibrate hardware.""""""


@setup.command("add-arm")
@click.option("--port", required=True, help="Serial port (e.g. /dev/ttyACM0, COM3).")
@click.option("--role", required=True, type=click.Choice(["leader", "follower"]))
@click.option("--robot-type", default="so101", help="Robot type (default: so101).")
@click.option("--id", "arm_id", default=None, help="Arm ID (auto-generated if omitted).")
@click.option("--label", default="", help="Human-readable position label.")
@click.option("--hardware-id", default="", help="Hardware fingerprint (auto-detected if omitted).")
def setup_add_arm(
    port: str,
    role: str,
    robot_type: str,
    arm_id: str | None,
    label: str,
    hardware_id: str,
) -> None:
    """"""Register a new robot arm in the project.""""""
    from defty.hardware.detector import list_serial_ports
    from defty.hardware.registry import add_arm
    from defty.project import find_project_root, load_project, save_project

    try:
        yaml_path = find_project_root()
        project = load_project(yaml_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Auto-detect hardware_id if not provided
    if not hardware_id:
        for sp in list_serial_ports():
            if sp.port == port and sp.hardware_id:
                hardware_id = sp.hardware_id
                click.echo(f"Auto-detected hardware_id: {hardware_id}")
                break

    try:
        add_arm(
            project,
            arm_id=arm_id,
            port=port,
            hardware_id=hardware_id,
            robot_type=robot_type,
            role=role,
            label=label,
        )
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
@click.option("--width", default=640, type=int, help="Capture width (default: 640).")
@click.option("--height", default=480, type=int, help="Capture height (default: 480).")
@click.option("--fps", default=30.0, type=float, help="Capture FPS (default: 30).")
def setup_add_camera(
    device: str,
    position: str,
    camera_id: str | None,
    hardware_id: str,
    width: int,
    height: int,
    fps: float,
) -> None:
    """"""Register a new camera in the project.""""""
    from defty.hardware.detector import list_cameras
    from defty.hardware.fingerprint import resolve_camera_hardware_id
    from defty.hardware.registry import add_camera
    from defty.project import find_project_root, load_project, save_project

    try:
        yaml_path = find_project_root()
        project = load_project(yaml_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Auto-detect hardware_id if not provided
    if not hardware_id:
        hw_id = resolve_camera_hardware_id(device)
        if hw_id:
            hardware_id = hw_id
            click.echo(f"Auto-detected hardware_id: {hardware_id}")

    try:
        add_camera(
            project,
            camera_id=camera_id,
            device=device,
            hardware_id=hardware_id,
            position=position,
            width=width,
            height=height,
            fps=fps,
        )
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    save_project(yaml_path, project)
    final_id = camera_id or project["hardware"]["cameras"][-1]["id"]
    click.echo(f"Added camera '{final_id}' -> {device}")


@setup.command("calibrate")
@click.option("--arm-id", required=True, help="ID of the arm to calibrate.")
def setup_calibrate(arm_id: str) -> None:
    """"""Calibrate a robot arm (interactive — requires physical arm movement).""""""
    from defty.project import find_project_root, load_project, save_project

    try:
        yaml_path = find_project_root()
        project = load_project(yaml_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    arms = project.get("hardware", {}).get("arms", [])
    arm = next((a for a in arms if a["id"] == arm_id), None)
    if arm is None:
        click.echo(f"Error: Arm '{arm_id}' not found in project.", err=True)
        sys.exit(1)

    port = arm.get("port", "")
    role = arm.get("role", "follower")
    robot_type = arm.get("robot_type", "so101")

    if not port:
        click.echo(f"Error: Arm '{arm_id}' has no port configured.", err=True)
        sys.exit(1)

    click.echo(f"Calibrating arm '{arm_id}' ({robot_type} {role}) on {port}...")
    click.echo("This requires physical interaction with the robot arm.")

    try:
        if robot_type == "so101" and role == "follower":
            from lerobot.robots.so_follower import SOFollower, SOFollowerConfig

            config = SOFollowerConfig(port=port)
            robot = SOFollower(config)
            robot.connect(calibrate=False)
            robot.calibrate()
            calibration_data = robot.calibration
            robot.disconnect()

        elif robot_type == "so101" and role == "leader":
            from lerobot.teleoperators.so100 import SO100Leader, SO100LeaderConfig

            config = SO100LeaderConfig(port=port)
            leader = SO100Leader(config)
            leader.connect(calibrate=False)
            leader.calibrate()
            calibration_data = leader.calibration
            leader.disconnect()
        else:
            click.echo(f"Error: Calibration not implemented for {robot_type} {role}", err=True)
            sys.exit(1)

        arm["calibration"] = calibration_data
        save_project(yaml_path, project)
        click.echo(f"Calibration saved for arm '{arm_id}'.")

    except ImportError:
        click.echo("Error: LeRobot is not installed. Run: pip install defty", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Calibration failed: {exc}", err=True)
        sys.exit(1)


@setup.command("update")
def setup_update() -> None:
    """"""Re-scan hardware and update port assignments using fingerprints.""""""
    from defty.hardware.registry import update_ports
    from defty.project import find_project_root, load_project, save_project

    try:
        yaml_path = find_project_root()
        project = load_project(yaml_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    update_ports(project)
    save_project(yaml_path, project)
    click.echo("Hardware port assignments updated.")


@setup.command("remove-arm")
@click.option("--arm-id", required=True, help="ID of the arm to remove.")
def setup_remove_arm(arm_id: str) -> None:
    """"""Remove a registered arm from the project.""""""
    from defty.hardware.registry import remove_arm
    from defty.project import find_project_root, load_project, save_project

    try:
        yaml_path = find_project_root()
        project = load_project(yaml_path)
        remove_arm(project, arm_id)
        save_project(yaml_path, project)
        click.echo(f"Removed arm '{arm_id}'.")
    except (FileNotFoundError, KeyError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@setup.command("remove-camera")
@click.option("--camera-id", required=True, help="ID of the camera to remove.")
def setup_remove_camera(camera_id: str) -> None:
    """"""Remove a registered camera from the project.""""""
    from defty.hardware.registry import remove_camera
    from defty.project import find_project_root, load_project, save_project

    try:
        yaml_path = find_project_root()
        project = load_project(yaml_path)
        remove_camera(project, camera_id)
        save_project(yaml_path, project)
        click.echo(f"Removed camera '{camera_id}'.")
    except (FileNotFoundError, KeyError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty health ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None, help="Path to project.yaml.")
def health(path: str | None) -> None:
    """"""Check the health of all registered hardware.""""""
    from defty.hardware.health import check_all_health
    from defty.project import load_project

    try:
        project = load_project(path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    report = check_all_health(project)

    # Arms
    for arm_report in report.arms:
        status_icon = "OK" if arm_report.all_motors_ok else "FAIL"
        click.echo(f"Arm {arm_report.arm_id} [{status_icon}]  port={arm_report.port}")
        if arm_report.error:
            click.echo(f"  Error: {arm_report.error}")
        for m in arm_report.motors:
            m_icon = "OK" if m.online else "FAIL"
            click.echo(f"  Motor {m.motor_id} ({m.name}): {m_icon}")
            if m.error:
                click.echo(f"    {m.error}")

    # Cameras
    for cam_report in report.cameras:
        status_icon = "OK" if cam_report.online else "FAIL"
        click.echo(f"Camera {cam_report.camera_id} [{status_icon}]  device={cam_report.device}")
        if cam_report.error:
            click.echo(f"  Error: {cam_report.error}")

    # Summary
    if report.all_ok:
        click.echo("\nAll hardware checks passed.")
    else:
        click.echo("\nSome hardware checks failed.", err=True)
        sys.exit(1)


# ── defty record ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None, help="Path to project.yaml.")
@click.option("--episodes", "-e", default=1, type=int, help="Number of episodes to record.")
@click.option("--fps", default=None, type=int, help="Override recording FPS.")
@click.option("--dataset-name", default=None, help="Override dataset name.")
@click.option("--push-to-hub", is_flag=True, help="Push dataset to HuggingFace Hub.")
def record(
    path: str | None,
    episodes: int,
    fps: int | None,
    dataset_name: str | None,
    push_to_hub: bool,
) -> None:
    """"""Record teleoperation episodes.""""""
    from defty.recording.recorder import record as do_record

    try:
        do_record(
            project_path=path,
            num_episodes=episodes,
            fps=fps,
            dataset_name=dataset_name,
            push_to_hub=push_to_hub,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty train ──────────────────────────────────────────────────────────────


@main.command()
@click.option("--path", "-p", default=None, help="Path to project.yaml.")
@click.option("--policy", default="act", help="Policy architecture (default: act).")
@click.option("--dataset-name", default=None, help="Override dataset name.")
@click.option("--output-dir", default=None, help="Override output directory.")
@click.option("--epochs", default=None, type=int, help="Number of training epochs.")
@click.option("--batch-size", default=None, type=int, help="Training batch size.")
@click.option("--lr", default=None, type=float, help="Learning rate.")
@click.option("--push-to-hub", is_flag=True, help="Push model to HuggingFace Hub.")
def train(
    path: str | None,
    policy: str,
    dataset_name: str | None,
    output_dir: str | None,
    epochs: int | None,
    batch_size: int | None,
    lr: float | None,
    push_to_hub: bool,
) -> None:
    """"""Train a policy on recorded data.""""""
    from defty.training.trainer import train as do_train

    try:
        do_train(
            project_path=path,
            policy=policy,
            dataset_name=dataset_name,
            output_dir=output_dir,
            num_epochs=epochs,
            batch_size=batch_size,
            learning_rate=lr,
            push_to_hub=push_to_hub,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── defty hardware import ───────────────────────────────────────────────────


@main.group()
def hardware() -> None:
    """"""Hardware data management.""""""


@hardware.command("import")
@click.argument("source_path", type=click.Path(exists=True))
def hardware_import(source_path: str) -> None:
    """"""Import hardware configuration from another project or file.""""""
    import yaml

    from defty.project import find_project_root, load_project, save_project

    try:
        yaml_path = find_project_root()
        project = load_project(yaml_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    source = Path(source_path)
    if source.is_dir():
        source = source / "project.yaml"

    if not source.exists():
        click.echo(f"Error: Source not found: {source}", err=True)
        sys.exit(1)

    with open(source, encoding="utf-8") as fh:
        source_data = yaml.safe_load(fh)

    source_hw = source_data.get("hardware", {})
    imported_arms = source_hw.get("arms", [])
    imported_cams = source_hw.get("cameras", [])

    current_hw = project.setdefault("hardware", {})
    current_arms = current_hw.setdefault("arms", [])
    current_cams = current_hw.setdefault("cameras", [])

    existing_arm_ids = {a["id"] for a in current_arms}
    existing_cam_ids = {c["id"] for c in current_cams}

    added_arms = 0
    for arm in imported_arms:
        if arm["id"] not in existing_arm_ids:
            current_arms.append(arm)
            added_arms += 1

    added_cams = 0
    for cam in imported_cams:
        if cam["id"] not in existing_cam_ids:
            current_cams.append(cam)
            added_cams += 1

    save_project(yaml_path, project)
    click.echo(f"Imported {added_arms} arm(s) and {added_cams} camera(s) from {source}")