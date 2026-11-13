# PaperFusion

论文技术到项目代码的端到端流水线。Harness 架构，Orchestrator 中心调度。

## 架构

Orchestrator 串联 4 个阶段，每个阶段调度专用 Subagent：

| Phase | 职责 | 产出 |
|-------|------|------|
| **Phase 1: 自动分析** | 探索项目 + P2C 论文理解 + 设计摘要 | artifacts/project_context.md, p2c_outputs/ |
| **Phase 2: Plan 生成** | writing-plans + 开发模式决策 | plans/*-plan.md |
| **Phase 3: SDD 执行** | Implementer + Reviewer + Monitor 逐 task 开发 | 项目代码 |
| **Phase 4: 集成验证** | 完整 pipeline 测试 | 测试通过 |

---

## 目录结构

``
PaperFusion/
├── AGENTS.md                               <- Agent 系统提示
├── README.md                               <- 本文件
├── opencode.jsonc                          <- opencode 配置
├── .opencode/
│   └── skills/
│       ├── orchestrator/                   <- 主编排 skill
│       │   ├── SKILL.md                    <- 4 Phase + 3 Subagent 调度规则
│       │   └── references/
│       │       ├── round1_clarify.md       <- Phase 1c 需求分析参考
│       │       ├── round2_adaptation.md    <- Phase 2 开发模式决策规则
│       │       └── adaptation_plan_template.md <- Plan 输出格式模板
│       └── p2c-tools/                      <- P2C 工具 skill
│           └── SKILL.md
├── p2c_tools/                              <- P2C 工具脚本
│   ├── P2C_SKILL.md
│   └── p2c_wrapper.py
├── log/                                    <- 日志系统
│   ├── LOG_SKILL.md
│   └── log.py
├── paper2code/                             <- P2C 外部仓库（只读）
├── artifacts/                              <- Phase 1 产出
│   ├── project_context.md
│   └── design_summary.md
├── plans/                                  <- Phase 2 产出
│   └── YYYY-MM-DD-{论文名}-plan.md
└── p2c_outputs/                            <- P2C 分析+代码产出
    └── {论文名}/
        ├── planning_artifacts/
        ├── analyzing_artifacts/
        ├── planning_config.yaml
        └── p2c_temp/                       <- P2C code 生成的独立仓库
``

---

## SDD Subagent 角色

每个 task 按顺序经过 3 个 Subagent：

``
Task N:
  1. Implementer ──> 2. Reviewer ──> 3. Integration Monitor
     (实现+测试)    (spec+quality)    (论文对齐核对)

  每个角色 <=3次失败自动重试，=3次 PAUSE 用户介入
``

### Implementer

- 按 task spec 实现代码
- p2c_coding 模式：先调 P2C 生成代码，再适配项目
- 内置 fixer：验证失败时自修复
- 报告：DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT

### Reviewer（合一）

- 双重审查：Spec 合规 + 代码质量
- 先 spec 后 quality，spec 不过不进 quality
- 必须读实际代码，不只看报告

### Integration Monitor

- 核对实现是否与论文技术一致
- 读取 P2C analyzing_artifacts 作为论文官方参考
- 严重偏离时触发修正循环

---

## 触发方式

用户说类似以下的话：

- "使用这个论文的技术来更新我们的工具"
- "将这篇论文融入项目：{论文路径}"
- "实现论文的 XX 方法，路径是 {路径}"

---

## 开发模式

Plan 中每个 task 标注开发模式：

| 模式 | 含义 | Implementer 行为 |
|------|------|-----------------|
| normal | 直接手写 | 按 spec 实现，不参考 P2C |
| p2c_reference | 参考分析手写 | 读 P2C 分析产物理解后手写 |
| p2c_coding | P2C 生成+适配 | 先 run_coding，读取后改造适配 |
| skip | 跳过 | 不实现 |

系统自动决定开发模式（基于模块复杂度、与论文的关联度）。

---

## 3 次熔断机制

任一 Subagent 角色重试 >=3 次仍不通过：

``
PAUSE 用户介入

展示：
- 已失败次数 + 每次失败原因
- Implementer 诊断结论
- Monitor 偏离点说明

选项：
1. 提供修改方向
2. 修改 plan
3. 跳过此模块
``

---

## 核心原则

| 原则 | 说明 |
|------|------|
| P2C 只读引用 | paper2code/ 不修改任何文件 |
| Plan 是唯一依据 | implementer 不自行修改技术方案 |
| 先 scan 再行动 | 提方案前 python log/log.py scan --lines 30 |
| 方案变化记日志 | rationale 必填 |
| 3 次熔断 | 任一角色失败 >=3次必须用户介入 |
| Monitor 必过 | 论文对齐是硬性要求 |
