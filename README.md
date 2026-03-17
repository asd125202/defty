# Defty

> **Physical AI IDE** — a local-first IDE and open skill format standard for robot intelligence development.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)

---

## What is Defty?

Defty is the **Jupyter Notebook + npm for Physical AI** — a local-first development environment that lets you record demonstrations, train robot policies, and run skills on real hardware.  
It also defines an open **Skill format** (`.skill` files) so that trained robot behaviours can be packaged, shared, installed, and composed — much like npm packages or Docker images.

## Architecture

```
┌──────────────────────────────────────┐
│  GUI Desktop App (closed-source)      │  ← Electron / Tauri (future)
└────────────────┬─────────────────────┘
                 │ import
┌────────────────▼─────────────────────┐
│  Core Library  (open-source)          │  ← pip install defty
│  project · hardware · recording       │
│  training · execution · skill engine  │
└────────────────┬─────────────────────┘
                 │ import
┌────────────────▼─────────────────────┐
│  CLI  (open-source)                   │  ← defty init / record / train / run
└──────────────────────────────────────┘
```

## Quick Start

```bash
# Install (one-liner, coming soon)
curl -fsSL https://defty.dev/install.sh | sh

# Or install from source
git clone https://github.com/asd125202/defty.git && cd defty
pip install -e .

# Core workflow
defty init my_robot        # create project
defty connect              # connect hardware
defty record               # record demonstrations
defty train                # train a policy
defty run pick_up          # run a skill
defty doctor               # diagnose environment
```

## Repository Structure

```
defty/
├── spec/                  # Open format specification (Markdown)
│   ├── project-yaml.md
│   └── skill-format.md
├── src/defty/             # Core Python library
│   ├── project.py
│   ├── hardware/
│   ├── recording/
│   ├── training/
│   ├── execution/
│   └── hub/
├── cli/                   # CLI entry-point (calls core)
├── skills/                # Example skill library
├── docs/
├── install.sh             # One-line installer (uv-based)
└── pyproject.toml
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).  
Portions derived from [LeRobot](https://github.com/huggingface/lerobot) by HuggingFace Inc., used under Apache 2.0.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).