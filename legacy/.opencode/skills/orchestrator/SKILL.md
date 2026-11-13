---
name: orchestrator
description: "PaperFusion 主编排 skill。当用户提到'更新工具''更新技术''论文融入'等关键词时自动触发。串联 4 个阶段：自动分析 > Plan生成 > SDD执行 > 集成验证。"
---

# Orchestrator — PaperFusion 主编排

Harness 架构的中心调度器。串联 brainstorming 分析、P2C 论文理解、writing-plans 计划生成、SDD 开发执行。

## 触发条件

用户消息需同时满足：
1. 包含关键词：更新工具 / 更新技术 / 论文融入 / 实现论文 / paper to code
2. 包含论文路径（PDF/JSON/链接）

解析后提取：
- paper_path: 论文文件路径
- goal: 用户目标描述
- project_path: 当前工作目录（默认）或用户指定路径

---

## Phase 0: 触发识别

1. 扫描日志上下文（python log/log.py scan --lines 30）
2. 确认论文路径存在
3. 确认项目目录结构
4. 向用户输出确认：
   - 论文：{paper_path}
   - 目标：{goal}
   - 项目：{project_path}
   - 预计耗时：取决于论文复杂度

---

## Phase 1: 自动分析

### 1a. 探索项目结构

Dispatch Task (explore agent):

扫描 {project_path}：
- 目录树（排除 node_modules/, .git/, __pycache__/）
- 核心模块：src/ 或 lib/ 下的 Python 文件
- 技术栈：requirements.txt / pyproject.toml / package.json
- 接口风格：统一基类、配置格式、命名规范
- 关键入口点：main.py / app.py / __main__.py

产出写入：artifacts/project_context.md

### 1b. 运行 P2C 分析

Dispatch Task (general-purpose):

运行 P2C 完整分析：

python p2c_tools/p2c_wrapper.py full --paper {论文名} --gpt o3-mini --json {paper_path} --out p2c_outputs/{论文名}

产出：
- p2c_outputs/{论文名}/planning_artifacts/
- p2c_outputs/{论文名}/analyzing_artifacts/
- p2c_outputs/{论文名}/planning_config.yaml

### 1c. 综合设计摘要

Orchestrator 自行分析（不 dispatch，保留上下文）：

读取：
- artifacts/project_context.md
- p2c_outputs/{论文名}/ 全部产物
- .opencode/skills/orchestrator/references/round1_clarify.md（必问清单参考）

参考 round1_clarify.md 的必问清单：
- 项目范围（从 project_context 提取）
- 论文定位（从 P2C 分析提取）
- 复现深度（默认 B：理解核心逻辑，按项目改造）
- 技术约束（从项目依赖提取）

自动决策，产出：
1. 论文核心模块清单
2. 各模块与项目的映射关系
3. 跳过/保留/改造初步判断

展示给用户 -> 一次性确认

---

## Phase 2: Plan 生成

加载 **.opencode/skills/writing-plans** skill，结合：
- Phase 1 产出的设计摘要
- P2C 分析结果
- references/adaptation_plan_template.md 格式
- references/round2_adaptation.md 开发模式规则

### 开发模式决策（系统自动）

| 条件 | 决策 |
|------|------|
| 论文核心算法，涉及复杂数学/架构 | p2c_coding |
| 需要理解论文逻辑但可简单实现 | p2c_reference |
| 业务胶水代码，与论文无关 | normal |
| 项目已有替代，或与论文不匹配 | skip |

### Plan 产出格式

plans/{date}-{论文名}-plan.md

包含：
- 每个 task 的完整 spec（输入/输出/算法/测试/命令）
- 每个 task 标注开发模式
- 每个 task 标注文件落点和依赖关系
- system 自动决定，不逐个确认

展示给用户 -> 确认 plan

---

## Phase 3: SDD 执行

遍历 plans/ 中的 plan 文件，逐 task 执行以下 3 步：

1. **Implementer** — dispatch @implementer subagent（实现 + 测试 + 自修复）
2. **Reviewer** — dispatch @reviewer subagent（Spec 合规审查 + 代码质量审查）
3. **Integration Monitor** — dispatch @integration-monitor subagent（论文技术对齐核对）

**熔断规则**：任一角色失败 >=3 次，PAUSE 用户介入（见 AGENTS.md 核心原则）。
**调度说明**：每个 task 按 implementer → reviewer → monitor 顺序执行。Reviewer 不通过时 implementer 修复后重新 review。Monitor 严重偏离时 implementer 修正后重新 review → monitor。

---
## Phase 4: 集成验证

全部 task 完成后：

1. 运行完整 pipeline 测试（数据加载 -> 模块处理 -> 输出结果）
2. 对比论文预期结果（如有参考数据）
3. 性能基准测试（如涉及）
4. 写入日志：python log/log.py add --message "论文 {论文名} 技术融合完成" --type code --rationale "{简述}"

---

## 日志规则

Phase 开始: add("进入 Phase {N}: {描述}", "plan")
重要决策: add("{决策内容}", "plan", "{原因}")
方案变更: add("{变更内容}", "plan", "{旧方案问题} 改为 {新方案理由}")
Task 完成: add("Task {N} 完成: {简述}", "code")
PAUSE 介入: add("Task {N} 用户介入: {原因}", "agent")
全部完成: add("论文技术融合完成: {论文名}", "code", "{整体变更概述}")

---

## 关键约束

1. **P2C 只读** — paper2code/ 目录不修改任何文件
2. **Plan 是唯一依据** — implementer 严格按 plan 执行，不自行修改技术方案
3. **先 scan 再行动** — 每次提方案前 python log/log.py scan --lines 30
4. **方案变化记日志** — rationale 必填
5. **失败 3 次熔断** — 任一角色失败 >=3次必须用户介入
6. **Monitor 必过** — Integration Monitor 不通过不能标记 task 完成

---

## 目录约定

PaperFusion/
- artifacts/              Phase 1 产出（project_context.md）
- plans/                  Phase 2 产出（*-plan.md）
- p2c_outputs/{论文名}/   P2C 分析 + 代码产出
  - planning_artifacts/
  - analyzing_artifacts/
  - planning_config.yaml
  - p2c_temp/             P2C code 生成的独立仓库
- p2c_tools/              P2C 工具
- log/                    日志
- paper2code/             外部仓库（只读）

---

## 快速命令

# 扫描日志
python log/log.py scan --lines 30

# P2C 完整分析
python p2c_tools/p2c_wrapper.py full --paper {名} --gpt o3-mini --json {路径} --out p2c_outputs/{名}

# P2C Code 生成（p2c_coding 模块）
python p2c_tools/p2c_wrapper.py code --paper {名} --gpt o3-mini --json {路径} --out p2c_outputs/{名} --repo p2c_outputs/{名}/p2c_temp

# 记录日志
python log/log.py add --message "{内容}" --type {类型} --rationale "{原因}"


