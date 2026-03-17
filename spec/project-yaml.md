# project.yaml — Specification v0.1 (Draft)

A `project.yaml` is the entry point of every Defty project folder.

## Required Fields

```yaml
defty_version: "0.1"          # spec version
name: my_robot_project         # human-readable project name
hardware:
  type: so100                  # robot hardware identifier
  serial_port: /dev/ttyUSB0
```

## Optional Fields

```yaml
description: "Pick-and-place demo with SO-100"
created_at: "2026-03-17"
skills:
  - skills/pick_up/
actions: []
agents: []
```