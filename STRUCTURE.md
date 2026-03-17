# Repository Structure

```
defty/
├── spec/                        # Open format specification docs
│   ├── project-yaml.md          # project.yaml schema (v0.x)
│   └── skill-format.md          # .skill file format (v0.x)
├── src/
│   └── defty/                   # Core Python library (pip install defty)
│       ├── __init__.py
│       ├── project.py           # Project create / load / validate
│       ├── hardware/            # Hardware drivers
│       │   ├── __init__.py
│       │   └── so100.py         # SO-100 robot arm driver
│       ├── recording/           # Data recording
│       │   ├── __init__.py
│       │   └── recorder.py
│       ├── training/            # Policy training
│       │   ├── __init__.py
│       │   └── trainer.py
│       ├── execution/           # Skill execution engine
│       │   ├── __init__.py
│       │   └── runner.py
│       ├── skill/               # Skill pack / install / parse
│       │   ├── __init__.py
│       │   ├── packer.py
│       │   ├── installer.py
│       │   └── skill_file.py
│       └── doctor.py            # Environment diagnostics
├── cli/                         # CLI (calls core)
│   └── src/defty_cli/
│       └── cli.py
├── skills/                      # Example Skills
├── docs/
│   ├── robots/                  # Per-robot doc pages
│   └── api/                     # API reference
├── tests/
├── install.sh                   # macOS/Linux one-liner installer
├── install.ps1                  # Windows one-liner installer
├── pyproject.toml
├── CONTRIBUTING.md
├── CHANGELOG.md
└── STRUCTURE.md                 # this file
```