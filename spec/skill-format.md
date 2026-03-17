# Skill Format — Specification v0.1 (Draft)

A `.skill` file is a **self-contained**, **portable** package for a single robot behaviour.  
Internally it is a ZIP archive with a `.skill` extension.

## Internal Structure

```
pick_up-v1.0.skill
├── skill.yaml          # metadata, hardware requirements, done_when
├── model.pt            # model weights
├── eval_summary.json   # evaluation results
└── eval_video.mp4      # best execution recording (optional)
```

## skill.yaml Schema

```yaml
defty_version: "0.1"
name: pick_up
version: "1.0"
hardware:
  type: so100
done_when: "gripper.holding == true"
timeout: 10s
model: model.pt
```

## Packaging and Installing

```bash
defty pack skills/pick_up          # → pick_up-v1.0.skill
defty install pick_up-v1.0.skill   # install into current project
defty run pick_up                  # execute
```