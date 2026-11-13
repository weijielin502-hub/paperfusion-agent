---
name: writing-plans
description: "PaperFusion Plan 生成 skill。被 orchestrator 在 Phase 2 加载，结合设计摘要 + P2C 分析产物，产出结构化开发计划。"
---

# Writing Plans — PaperFusion Plan 生成

被 orchestrator 在 Phase 2 加载。输入 Phase 1 设计摘要和 P2C 分析产物，输出 plans/{date}-{论文名}-plan.md。

## 输入

- artifacts/project_context.md（Phase 1 探索产出）
- p2c_outputs/{论文名}/ 全部产物（P2C 分析）
- 综合设计摘要（Phase 1c 产出）

## 开发模式决策

参考 ../orchestrator/references/round2_adaptation.md 的决策树，自动决定：

| 条件 | 决策 |
|------|------|
| 论文核心算法，涉及复杂数学/架构 | p2c_coding |
| 需要理解论文逻辑但可简单实现 | p2c_reference |
| 业务胶水代码，与论文无关 | normal |
| 项目已有替代，或与论文不匹配 | skip |

## 产出格式

严格按 ../orchestrator/references/adaptation_plan_template.md 的模板格式。

plan 文件路径：plans/{date}-{论文名}-plan.md

每个 task 包含：
- 完整 spec（输入/输出/算法/测试/命令）
- 开发模式标注
- 文件落点
- 依赖关系

system 自动决定所有 task，不逐个确认。产出后展示给用户确认。
