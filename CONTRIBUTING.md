# Contributing to Defty

Welcome, and thank you for your interest in contributing!  
Defty is a fully open-source project licensed under the **Apache License 2.0**, copyright 2026 APRL Technologies Inc.  
Contributions of all kinds are welcome — bug fixes, new hardware drivers, algorithm integrations, documentation, and example Skills.

---

## Development Setup

```bash
git clone https://github.com/asd125202/defty.git ~/defty
cd ~/defty
conda create -n defty python=3.12 -y
conda activate defty
pip install -e ".[dev]"
pre-commit install
```

---

## Code Standards

Every contribution must follow these rules — no exceptions.

### 1. License Header

Every `.py` file must begin with the following header:

**Original code:**
```python
# Copyright (c) 2026 APRL Technologies Inc.
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
```

**Code derived from LeRobot (HuggingFace):**
```python
# Copyright (c) 2026 APRL Technologies Inc.
# Author: Yiju Li
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Portions of this file are derived from LeRobot by HuggingFace Inc.
# (https://github.com/huggingface/lerobot), used under the Apache License 2.0.
# Original copyright: Copyright 2024 The HuggingFace Inc. team.
```

### 2. Docstrings

- Every module must have a module-level docstring.
- Every public class must have a class docstring.
- Every public method and function must have a docstring.
- Use Google style for Args/Returns when the signature is non-obvious.

### 3. `__all__`

Every `__init__.py` that re-exports symbols must define `__all__`.

### 4. Logging

Every module that logs must use:
```python
import logging
logger = logging.getLogger(__name__)
```

### 5. Code Style

Run before committing:
```bash
ruff check --fix .
ruff format .
```

Or install pre-commit hooks (done once after cloning):
```bash
pre-commit install
```

---

## Adding a New Robot

1. Create `src/defty/robots/<robot_name>/` with `__init__.py` and `<robot_name>.py`.
2. Subclass `Robot` and `RobotConfig` from `defty.robots.robot`.
3. Implement all abstract methods: `connect`, `calibrate`, `configure`, `get_observation`, `send_action`, `disconnect`.
4. Add the appropriate license header (original or LeRobot-derived).
5. Add a doc page at `docs/robots/<robot_name>.md`.
6. Update `STRUCTURE.md` and `CHANGELOG.md`.

## Adding a New Motor Bus

1. Create `src/defty/motors/<brand>/` with `__init__.py`, `<brand>.py`, and `tables.py`.
2. Subclass `SerialMotorsBus` from `defty.motors.motors_bus`.
3. Implement all abstract methods.
4. Add the LeRobot-derived license header.
5. Add a doc page at `docs/api/motors.md` (extend the existing file).
6. Update `STRUCTURE.md` and `CHANGELOG.md`.

---

## Pull Request Checklist

- [ ] License header on all new `.py` files
- [ ] Module, class, and function docstrings present
- [ ] `__all__` updated in relevant `__init__.py` files
- [ ] `CHANGELOG.md` entry added under `[Unreleased]`
- [ ] `STRUCTURE.md` updated if new files/dirs were added
- [ ] `SETUP.md` updated if the setup procedure changed
- [ ] `ruff check` and `ruff format` pass with no errors