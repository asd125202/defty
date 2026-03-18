# Defty — 项目说明书 / Project Specification

> **The Physical AI IDE:** Build, test, and share Physical AI Agents like building blocks.

*版本: v0.1 — 2026-03-18*

---

## 目录 / Table of Contents

1. [产品定位 / Vision & Positioning](#1-产品定位--vision--positioning)
2. [Physical AI 六大实现路径 / Six Paths](#2-physical-ai-六大实现路径--the-six-paths)
3. [核心架构：节点系统 / Node System](#3-核心架构节点系统--the-node-system)
4. [Agent 概念 / The Agent Concept](#4-agent-概念--the-agent-concept)
5. [文件格式规范 / File Formats](#5-文件格式规范--file-formats)
6. [技术选型 / Technology Stack](#6-技术选型--technology-stack)
7. [当前状态 / Current State (v0.1.0-dev)](#7-当前状态--current-state)
8. [Alpha 路线图 / Roadmap to Alpha](#8-alpha-路线图--roadmap-to-alpha)
9. [待解决问题 / Open Questions](#9-待解决问题--open-questions)

---

## 1. 产品定位 / Vision & Positioning

### 一句话描述

**LangChain 让开发者编排 AI Agent 完成软件任务，Defty 让开发者编排 Physical AI Agent 完成现实世界的任务。**

### 类比参考

| 参考产品 | 领域 | Defty |
|---------|------|-------|
| ComfyUI | AI 图像生成节点编排 | Physical AI 动作节点编排 |
| LangChain | 软件 Agent 编排 | Physical Agent 编排 |
| Groot2 | 行为树可视化编辑器 | 带 AI 模型的行为树 IDE |

### 核心价值

- 任何人都可以把视觉模型、操作策略、运动规划**像搭积木一样组合**
- 构建能操控机械臂的 AI Agent
- **一键分享**给全球任何一台同型号机械臂

### 市场背景

> *"机器人数量将在 5 年内超过智能手机"* — 黄仁勋

**痛点**：构建机器人 AI 的门槛极高。开发者需要同时掌握硬件控制、运动学、深度学习。90% 的开发者被挡在门外。

**Defty 的答案**：Physical AI Agent 的 IDE。让任何开发者都能构建、测试、分享能在真实世界执行任务的 AI Agent。

**壁垒**：第一个开放的 Physical Agent 节点生态。开发者贡献节点，社区组合复用。网络效应驱动的平台。

---

## 2. Physical AI 六大实现路径 / The Six Paths

平台兼容所有路径，用户自由选择。

| 路径 | 名称 | 数据需求 | 核心特点 | LeRobot 支持 |
|-----|------|---------|---------|-------------|
| 路径一 | 模仿学习 (ACT / Diffusion Policy) | 高 (人工演示) | 从演示中学 | ✅ 支持 |
| 路径二 | 端到端 VLA (SmolVLA / π₀) | 低 (微调) | 预训练+微调，泛化强 | ✅ 支持 |
| 路径三 | LLM 高层规划 + 低层 API | 无 | 大模型看图调 API | ❌ 需自己实现 |
| 路径四 | LLM Agent 直接控制 | 无 | 迭代推理，零样本 | ❌ 需自己实现 |
| 路径五 | 强化学习 (HIL-SERL / SAC) | 无 (需奖励函数) | 边执行边学，能超越演示 | ✅ 支持 |
| 路径六 | 世界模型 + 合成数据 | 极低 (种子数据) | NVIDIA Cosmos 级别 | ❌ 暂不考虑 |

### 关键区别

```
训练方式：
  路径一/二：离线训练（数据集是静态文件，可在任何电脑训练）
  路径五：  在线训练（必须连着机械臂实时交互，但权重可迁移）
  路径三/四：无需训练（直接用 LLM API）

时间尺度：
  路径一/二/五：毫秒级（50Hz 输出关节角度）→ 执行层
  路径三/四：  秒级（LLM 推理 2–5 秒）→ 决策层

收敛特性：
  路径一/二：训练步数 ∝ 性能（近似线性关系）
  路径五：  有收敛概念，收敛后继续训练无意义
```

---

## 3. 核心架构：节点系统 / The Node System

### 3.1 节点是什么

**所有东西都是节点。** 节点分两类：

#### Control Nodes（决策 / 组合 — 不直接碰机械臂）

| 节点 | 行为 |
|------|------|
| `Sequence` | 顺序执行子节点，全部成功才返回成功 |
| `Selector` | 依次尝试子节点，第一个成功即返回成功 (if-else) |
| `Repeat` | 重复执行 N 次或直到条件满足 |
| `LLMDecision` | 智能的 Selector — 由大模型决定走哪条分支 |

#### Leaf Nodes（直接产生动作或感知结果）

**模型类 (Policy Nodes)：**
| 节点 | 路径 | 说明 |
|------|------|------|
| `ACTPolicyNode` | 路径一 | ACT 策略推理 |
| `DiffusionPolicyNode` | 路径一 | Diffusion Policy 推理 |
| `SmolVLANode` | 路径二 | VLA 模型推理 |
| `HILSERLNode` | 路径五 | RL 在线策略 |
| `VLMDirectControlNode` | 路径三 | VLM 直接输出舵机角度 |
| `LLMAgentNode` | 路径四 | LLM 迭代推理控制 |

**感知类 (Perception Nodes)：**
| 节点 | 说明 |
|------|------|
| `CameraCaptureNode` | 摄像头帧捕获 |
| `YOLODetectNode` | YOLO 物体检测 |
| `DepthCameraNode` | 深度相机测距 |

**运动类 (Motion Nodes)：**
| 节点 | 说明 |
|------|------|
| `IKSolverNode` | 逆运动学解算 (xyz → 关节角度) |
| `JointControlNode` | 关节角度直接控制 |
| `RelativeMoveNode` | 末端执行器相对移动 (Δcm) |
| `GripperOpenNode` | 张开夹爪 |
| `GripperCloseNode` | 闭合夹爪 |

**工具类 (Utility Nodes)：**
| 节点 | 说明 |
|------|------|
| `WaitNode` | 等待 N 秒 |
| `ConditionNode` | 条件判断 |
| `VLMSuccessDetectorNode` | VLM 判断任务是否完成 |

### 3.2 统一节点接口

```python
class Node:
    """Every node implements exactly one method."""

    def tick(self, context: Context) -> NodeStatus:
        ...


class Context:
    """Shared state passed to every node on each tick."""

    cameras: dict[str, np.ndarray]   # 所有摄像头图像
    joint_states: np.ndarray         # 当前关节状态 (6D)
    language: str                    # 语言指令
    memory: dict                     # Blackboard — 节点间通信
    robot: RobotInterface            # 控制机械臂的接口


class NodeStatus:
    """Return value from tick()."""

    state: Literal["Success", "Failure", "Running"]
    output: dict  # 写入 context.memory
```

### 3.3 Blackboard 模式（节点间通信）

节点之间不直接传数据，通过 `context.memory` (Blackboard) 共享：

```python
# YOLODetectNode 执行完 → 写入 memory
context.memory["target_position"] = [0.3, 0.1, 0.2]
context.memory["target_class"] = "red_block"

# IKSolverNode 从 memory 读取
target = context.memory["target_position"]

# ACTPolicyNode 不看 memory — 直接用摄像头图像
```

### 3.4 节点完成判断

| 节点类型 | 完成信号 |
|---------|---------|
| HIL-SERL | 自带训练好的奖励分类器 → Success / Failure |
| ACT / SmolVLA | 执行完固定帧数后 → Success；或用户后接 `VLMSuccessDetectorNode` |
| Motion 节点 | 到达目标位置 → Success |
| LLM 节点 | API 响应返回 → Success |

这是系统最复杂的问题。采用**用户自主决定**方案 — 平台不强制完成判断策略，用户在行为树里自由组合。

### 3.5 LLM 节点的双重角色

同一个 LLM 节点可以扮演两种角色：

**作为 Leaf Node（直接控制）：**
```
摄像头图像 → LLM → 舵机角度
最简单的用法，不需要任何训练
```

**作为 Control Node（智能决策）：**
```
摄像头图像 → LLM → 决定执行哪个技能
context.memory["next_skill"] = llm.decide()
行为树根据这个值选分支
```

### 3.6 嵌套结构示例（System 1 / System 2 架构）

```
外层 LLM（高层，慢，2–5 秒/次）
  ↓ 理解任务语义，决定下一步做什么
Selector 节点（根据 LLM 决策分支）
  ├── [抓取红块] → ACTPolicyNode（快，50Hz）
  ├── [抓取蓝块] → SmolVLANode
  └── [任务完成] → 返回 Success
```

等价于 NVIDIA GR00T N1 的 System1（快）/ System2（慢）架构。

> ⚠️ **实时性警告：** LLM 节点推理需要 2–5 秒。不能直接连到 50Hz 的舵机控制节点，否则机械臂会抽搐。正确用法：LLM 节点 → 决策 → 选择执行哪个快速节点。平台应对这种连接给出警告。

---

## 4. Agent 概念 / The Agent Concept

### 4.1 什么是 Agent

**整棵行为树跑起来 = 一个 Physical Agent。**

```
感知（摄像头节点）
  + 决策（LLM / Control 节点）
  + 执行（Leaf 节点）
  + 反馈（Success / Failure）
  = 完整的闭环自主系统
  = Agent
```

单个节点不是 Agent，是 Agent 的组成部分。

### 4.2 用户视角的核心概念

| 概念 | 说明 |
|------|------|
| **Agent** | 核心单位 — 用户创建、运行、分享的东西 |
| **Node** | Agent 内部的积木 |
| **Node Library** | 社区贡献的节点（未来在线市场） |
| **Global Cache** | 公共大模型的本地存储（共享，不重复下载） |

### 4.3 与现有项目系统的关系

当前 Defty 的 `defty init` 项目系统（用于 Record → Train → Run 工作流）**继续保留**。
Agent 系统是在其之上的新一层抽象：

```
项目 (Project)  = 开发工作区，包含数据、模型、校准
Agent            = 可部署的行为单元，从项目中提取
```

用户的典型工作流：
1. `defty init` → 创建项目
2. `defty record` / `defty train` → 开发阶段
3. 把训练好的模型包装成 Agent → 部署/分享阶段

---

## 5. 文件格式规范 / File Formats

### 5.1 Agent 文件结构

```
my_agent/
├── agent.yaml              ← 行为树结构 + 依赖声明（核心）
├── nodes/
│   └── my_act_finetuned.pt ← Agent 私有的模型权重
├── datasets/               ← 训练数据（可选）
│   └── episodes/
└── calibration/
    └── main_follower.json  ← 机械臂校准文件（不可迁移）
```

### 5.2 agent.yaml 格式

```yaml
name: pick_and_sort_blocks
version: "1.0"

robot:
  model: so101
  calibration: ./calibration/main_follower.json
  cameras:
    front: {index: 0, fps: 30, width: 640, height: 480}
    wrist: {index: 2, fps: 30, width: 640, height: 480}

# 依赖的公共模型（从全局缓存取，不打包）
dependencies:
  - smolvla_base
  - yolo_v8_nano

# 行为树结构
tree:
  type: Repeat
  until: "no_blocks_detected"
  child:
    type: Sequence
    children:
      - type: YoloDetectNode
        target: "block"
        output_key: "target_pos"

      - type: LLMDecisionNode
        model: "gpt-4o"
        prompt: "根据检测结果决定执行哪个技能"
        branches:
          pick_red: SmolVLANode
          pick_blue: ACTNode
          done: SuccessNode

      - type: IKMoveNode
        target_key: "target_pos"

      - type: GripperCloseNode

      - type: VLMSuccessDetector
        condition: "方块是否已放入盒中"
```

### 5.3 全局存储结构

```
~/.defty/
├── models/               ← 全局模型缓存（所有 Agent 共享）
│   ├── smolvla_base/
│   ├── yolo_v8_nano/
│   └── ...
└── agents/               ← 用户的所有 Agent
    ├── pick_red_block/
    └── sort_blocks/
```

### 5.4 分享与复现机制

```
分享时打包：agent.yaml + nodes/（私有模型）+ datasets/
不打包：    公共模型（太大，接收方自动下载）

接收方运行时：
  平台检测缺少 smolvla_base
  → 自动从 HuggingFace 下载
  → 放入全局缓存
  → 运行

⚠️ calibration/ 不可迁移
  每台机械臂物理上不完全一样
  新机器必须重新校准
  这是唯一无法自动化的步骤
```

---

## 6. 技术选型 / Technology Stack

### 6.1 现有依赖（已集成）

| 功能 | 库 | 备注 |
|-----|-----|------|
| 机械臂控制 | LeRobot ≥ 0.5.0 | SO-101 原生支持 |
| ML 框架 | PyTorch ≥ 2.3.0 | 训练 & 推理 |
| CLI 框架 | Click ≥ 8.1.0 | 命令解析 |
| 配置格式 | PyYAML ≥ 6.0 | project.yaml / agent.yaml |
| 串口通讯 | PySerial ≥ 3.5 | 舵机通讯 |
| 可视化 | Rerun (可选) | 实时 3D 可视化 |

### 6.2 计划新增依赖

| 功能 | 库 | 引入时间 |
|-----|-----|---------|
| 行为树引擎 | **自研** (不用 py_trees) | Milestone 1 |
| 物体检测 | ultralytics (YOLOv8) | Milestone 4 |
| 逆运动学 | lerobot-kinematics | Milestone 4 |
| LLM API | openai / anthropic | Milestone 4 |
| VLM 推理 | transformers (本地) 或 API | Milestone 4 |

### 6.3 为什么自研行为树引擎而非 py_trees

1. 行为树是平台的**核心灵魂** — 需要完全掌控
2. 我们的需求精确：Sequence, Selector, Repeat + 自定义节点
3. 与 Context / Blackboard 模式需要深度集成
4. 更少的外部依赖 = 更简单的安装
5. 未来 GUI 可视化需要自定义的树表示

---

## 7. 当前状态 / Current State

### v0.1.0-dev 已完成功能

| 组件 | 状态 | 说明 |
|------|------|------|
| CLI | ✅ 30+ 命令 | 完整命令套件：硬件、录制、训练、推理 |
| 硬件抽象 | ✅ | SO-101 机械臂、USB 摄像头、指纹识别、跨平台 |
| 录制管道 | ✅ | 遥操 → 数据集，自动编号、续录、可视化 |
| 训练管道 | ✅ | ACT / Diffusion / TDMPC / VQBet 策略 |
| 推理管道 | ✅ | 视觉+状态 / 纯状态 模式，可录制 rollout |
| 项目系统 | ✅ | project.yaml, calibration, data/, models/ |
| 安装器 | ✅ | 一键安装 (Win/Linux/macOS)，GPU 自动检测 |
| 可视化 | ✅ | Rerun 集成 (遥操、回放、推理) |
| 测试 | ✅ | 30 单元测试通过 |

### 通往愿景还缺什么

| 组件 | 状态 | 说明 |
|------|------|------|
| 节点系统 | ❌ | 核心抽象层尚未构建 |
| 行为树引擎 | ❌ | Sequence / Selector / Repeat + tick 循环 |
| Agent 系统 | ❌ | agent.yaml, create / run / share 工作流 |
| 感知节点 | ❌ | YOLO, 深度相机, IK |
| 智能节点 | ❌ | LLM 决策, VLM 成功检测 |
| 全局模型缓存 | ❌ | ~/.defty/models/ |
| Agent 分享 | ❌ | 导出/导入/市场 |

---

## 8. Alpha 路线图 / Roadmap to Alpha

### 总览

```
M0 (已完成)     M1            M2             M3            M4             M5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 LeRobot     节点引擎      硬件节点       Agent系统     感知+智能       Alpha
 Wrapper     Node Engine   Hardware      Agent YAML    Perception     Release
  CLI        + BT Runner   Leaf Nodes    + CLI         + Intelligence  v0.2.0-α
```

---

### Milestone 0: 基础框架 ✅ (已完成)

LeRobot wrapper + 完整 CLI。

- ✅ 硬件管理 (scan, setup, calibrate, health)
- ✅ Record → Train → Run 完整管道
- ✅ 跨平台支持 (Windows / Linux / macOS)
- ✅ 一键安装器 + GPU 自动检测
- ✅ 30 单元测试通过

---

### Milestone 1: 节点引擎 / Node Engine

构建平台的核心抽象层。

**新增文件：**
```
src/defty/nodes/
├── __init__.py           # 公共 API 导出
├── base.py               # Node, Context, NodeStatus, RobotInterface
├── control.py            # SequenceNode, SelectorNode, RepeatNode
└── engine.py             # BehaviorTreeRunner — tick 循环 + 频率控制
```

**具体任务：**
| 任务 | 说明 |
|------|------|
| `Node` 基类 | 抽象 `tick(context) -> NodeStatus` 接口 |
| `Context` 数据类 | cameras, joint_states, language, memory, robot |
| `NodeStatus` | Success / Failure / Running + output dict |
| `Blackboard` | context.memory 读/写 + 键类型验证 |
| `SequenceNode` | 依次 tick 子节点，全部成功才成功 |
| `SelectorNode` | 依次 tick 子节点，第一个成功即成功 |
| `RepeatNode` | N 次循环或条件终止 |
| `BehaviorTreeRunner` | 主循环：刷新 context → tick 根节点 → 发送动作 |
| 单元测试 | 每个节点类型的行为测试 |

**交付标准：** 可以用 Python 代码定义行为树并通过 `BehaviorTreeRunner` 执行。

---

### Milestone 2: 硬件叶节点 / Hardware Leaf Nodes

把现有硬件控制能力包装成节点。

**新增文件：**
```
src/defty/nodes/
├── perception.py         # CameraCaptureNode
├── motion.py             # JointControlNode, RelativeMoveNode, GripperNode
├── policy.py             # ACTPolicyNode (包装现有 runner.py)
└── utility.py            # WaitNode, ConditionNode
```

**具体任务：**
| 节点 | 说明 |
|------|------|
| `CameraCaptureNode` | 读取所有摄像头帧到 context.cameras |
| `JointControlNode` | 从 memory 读取目标角度 → 发送到机械臂 |
| `RelativeMoveNode` | 末端执行器相对移动 (Δx, Δy, Δz) |
| `GripperOpenNode` / `GripperCloseNode` | 夹爪控制 |
| `ACTPolicyNode` | 包装现有 inference/runner.py → 输出 action |
| `WaitNode` | 等待 N 秒 |
| `ConditionNode` | 检查 memory 中的条件 |
| 集成测试 | Sequence(CameraCapture → ACTPolicy) 端到端 |

**交付标准：** 可以用节点树驱动 SO-101 机械臂执行 ACT 策略。

---

### Milestone 3: Agent 系统 / Agent System

agent.yaml 工作流完整实现。

**新增文件：**
```
src/defty/agents/
├── __init__.py
├── schema.py             # agent.yaml v1 schema 定义 + 验证
├── parser.py             # YAML → 行为树实例
├── builder.py            # 节点注册表 + 工厂方法
└── manager.py            # 创建、列表、运行 Agent
```

**新增 CLI 命令：**
| 命令 | 说明 |
|------|------|
| `defty agent create <name>` | 脚手架新 Agent (生成 agent.yaml 模板) |
| `defty agent run <name>` | 执行 Agent 行为树 |
| `defty agent list` | 列出所有 Agent |
| `defty agent info <name>` | 显示 Agent 详情 (节点树、依赖) |

**其他任务：**
| 任务 | 说明 |
|------|------|
| agent.yaml v1 schema | 正式 schema 文档 + JSON Schema 验证 |
| 节点注册表 | 字符串名 → 节点类的映射 (如 "ACTPolicyNode" → ACTPolicyNode) |
| YAML → 行为树 | 递归解析 tree 字段 → 构建节点树实例 |
| 全局模型缓存 | `~/.defty/models/` — 下载、缓存、版本管理 |
| 测试 | YAML 解析、节点构建、Agent 生命周期 |

**交付标准：** 写好 agent.yaml → `defty agent run pick_red` 直接在机械臂上执行。

---

### Milestone 4: 感知 + 智能节点 / Perception & Intelligence

让平台真正 "AI"。

**新增节点：**
| 节点 | 依赖 | 说明 |
|------|------|------|
| `YOLODetectNode` | ultralytics | 物体检测 → 写入 memory |
| `IKSolverNode` | lerobot-kinematics | xyz 坐标 → 关节角度 |
| `LLMDecisionNode` | openai / anthropic | LLM 看图 → 决定分支 |
| `VLMSuccessDetectorNode` | API 或本地模型 | 判断任务是否完成 |
| `SmolVLANode` | lerobot | VLA 模型推理 (路径二) |

**关键 Demo：Zero-Shot Pick-and-Place**
```yaml
# 不需要任何训练数据！纯零样本！
tree:
  type: Sequence
  children:
    - type: CameraCaptureNode
    - type: YOLODetectNode
      target: "red_block"
      output_key: "target_pos"
    - type: IKSolverNode
      target_key: "target_pos"
      output_key: "joint_target"
    - type: JointControlNode
      source_key: "joint_target"
    - type: GripperCloseNode
```

这个 Demo 是平台核心价值的最佳展示：**零训练、纯组合、积木式**。

**交付标准：** YOLO 检测 → IK 解算 → 抓取的零样本 Demo 可运行。

---

### Milestone 5: Alpha 发布 / Alpha Release (v0.2.0-alpha)

打磨与发布。

| 任务 | 说明 |
|------|------|
| Agent 导出/导入 | `defty agent export` → .zip, `defty agent import` |
| 参考 Agent | 3–5 个示例 Agent 附带文档 |
| 端到端教程 | 从零到部署的完整教程 |
| 错误处理 | 优雅降级、友好错误信息 |
| 实时性警告 | 检测 LLM → Motor 直连并提示 |
| 性能基准 | tick 频率、延迟测量 |
| Tagged Release | v0.2.0-alpha Git tag, PyPI 发布 |

**Alpha 标准：**
- ✅ 节点系统可用 (10+ 内置节点)
- ✅ agent.yaml 工作流端到端
- ✅ 至少一个零样本 Demo 可运行
- ✅ 至少一个训练 Demo 可运行 (ACT)
- ✅ Agent 导出/导入
- ✅ 文档齐全

---

## 9. 待解决问题 / Open Questions

1. **默认完成帧数**：ACT / SmolVLA 没有接成功检测节点时，执行多少帧算完成？

2. **LLM 实时性警告**：平台如何检测并提示 "这个连接会导致机械臂响应很慢"？

3. **冷启动节点**：平台发布时自己先提供多少个高质量原子节点？优先做哪些？

4. **多机械臂类型**：v1 只支持 SO-101，v2 扩展到哪些型号？

5. **节点版本管理**：节点接口发生 breaking change 时如何处理？

6. **LLM 节点安全性**：如何防止 LLM 输出危险的关节角度导致机械臂损坏？

7. **可选依赖策略**：YOLO / IK / LLM 是否应作为可选 extras (`defty[vision]`, `defty[llm]`)？

---

*项目说明书版本: v0.1 | 2026-03-18*
*基于 Physical AI IDE 设计文档 v0.1 整理*
