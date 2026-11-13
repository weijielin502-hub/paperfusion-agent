# P2C × SDD 集成开发实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 将 Brainstorming + P2C + SDD 三件套整合为"论文技术 → 项目方案 → 开发执行"的完整流水线。

**Architecture:** Brainstorming 两轮负责需求明确和方案设计，P2C 在第二轮前提取论文技术细节作为输入，SDD 负责逐模块执行 adaptation_plan 中的开发任务。

**Tech Stack:** Python, Shell, opencode (Skill + SDD subagent), P2C (external scripts), YAML

---

## 文件结构

```
<original-poc-root>/
├── paper2code/                          ← git clone（只读引用）
├── brainstorming/
│   ├── round1_clarify.md                ← 第一轮：需求明确模板
│   └── round2_adaptation.md             ← 第二轮：结合 P2C 分析出方案
├── p2c_tools/
│   ├── P2C_SKILL.md                     ← P2C 调用接口说明
│   └── p2c_wrapper.py                   ← Python 包装器（一键调用）
├── log/
│   ├── log.py                           ← 日志工具
│   └── LOG_SKILL.md                     ← 日志 Skill 说明
├── adaptation_plan_template.md          ← 适配方案输出格式
├── docs/superpowers/plans/
│   └── 2026-05-29-p2c-sdd-integration.md ← 本计划文件
└── README.md
```

---

## Task 1: 目录搭建 + P2C 克隆 + log 迁移

**操作：**
- 创建 `brainstorming/`、`p2c_tools/`、`log/`、`docs/superpowers/plans/` 目录
- `git clone https://github.com/going-doer/Paper2Code.git` 到 `paper2code/`
- 从 `general_dev_sys/log/` 复制 `log.py` 和 `LOG_SKILL.md` 到项目 `log/`

**验证:** `paper2code/codes/` 目录存在，`log/log.py` 可运行

---

## Task 2: Brainstorming 第一轮模板

**文件:** `brainstorming/round1_clarify.md`

**内容要点:**
- 角色定位：辅助用户明确需求，追问缺失信息
- 必问清单：项目范围、论文定位、复现深度、技术约束
- 输出：结构化需求摘要，供用户确认后传递给第二轮

---

## Task 3: Brainstorming 第二轮模板

**文件:** `brainstorming/round2_adaptation.md`

**内容要点:**
- 前置条件：第一轮需求已确认 + P2C 分析已完成
- 输入：用户确认的需求摘要 + P2C 的 planning/analyzing 产物
- 工作流程：
  1. 读取 P2C 分析结果，提取论文技术要点
  2. 逐模块对照决策，标记开发模式（normal / p2c_reference / p2c_coding / skip）
  3. 产出 adaptation_plan.md（按 adaptation_plan_template.md 格式）
  4. 与用户确认方案
- 注意：所有领域知识（P2C 调用方式、适配改造规则、验收标准）直接写入 adaptation_plan 各模块的任务描述，SDD 的 implementer 和 spec reviewer 以此为准

---

## Task 4: P2C 工具封装

**文件:** `p2c_tools/P2C_SKILL.md` + `p2c_tools/p2c_wrapper.py`

**P2C_SKILL.md 内容要点:**
- 概述 P2C 的各阶段能力（planning / analyzing / coding / debugging）
- 每个阶段的 Shell 调用方式、输入参数、输出位置
- 调用规则：什么时候用哪个阶段，谁调用

**p2c_wrapper.py 内容要点:**
- 封装 P2C 脚本为 Python 函数，提供 CLI 和 import 两种调用方式
- `analyze_paper_full()` 一键运行 planning + config 提取 + analyzing
- 路径自适应：自动定位 `paper2code/codes/` 目录

---

## Task 5: adaptation_plan 输出模板

**文件:** `adaptation_plan_template.md`

**内容要点:**
- 定义 adaptation_plan 的标准输出格式
- 章节结构：项目概述、论文技术拆解、模块对照决策表、开发阶段（含任务描述/模式/依赖/验收标准）、集成测试、风险点

---

## Task 6: 日志系统路径修正

**操作:** 更新 `log/LOG_SKILL.md` 中的 `change_type` 增加 `plan` 类型

---

## Task 7: README 文档

**文件:** `README.md`

**内容要点:** 项目定位、三大组件分工、完整工作流图示、快速开始、核心原则

---

## Task 8: 保存本计划文件

**操作:** 写入 `docs/superpowers/plans/2026-05-29-p2c-sdd-integration.md`

---

## Task 9: 最终验证

**检查项:**
- 所有新建文件存在
- `p2c_wrapper.py` 语法正确
- `log/log.py` 语法正确
- `paper2code/codes/` 目录存在
