# Phase 2 参考：开发模式决策规则

Plan 生成阶段，每个模块需要决定开发模式。Orchestrator 自动决策，不逐个确认。

---

## 开发模式决策树

`
对论文每个核心模块：

Q1: 项目已有等效实现？
├─ Yes → skip
└─ No → Q2

Q2: 是论文核心算法/创新点？
├─ Yes → Q3
└─ No → Q4

Q3: 算法涉及复杂数学/特殊架构？
├─ Yes → p2c_coding（先 P2C 生成，再适配）
└─ No → p2c_reference（看 P2C 分析，手写实现）

Q4: 需要理解论文逻辑才能实现？
├─ Yes → p2c_reference
└─ No → normal（直接手写）
`

---

## 开发模式含义

| 模式 | 含义 | Implementer 行为 |
|------|------|-----------------|
| normal | 直接手写 | 按 task spec 实现，不参考 P2C 产物 |
| p2c_reference | 参考分析结果手写 | 读取 analyzing_artifacts 理解论文逻辑，然后手写 |
| p2c_coding | P2C 生成 + 适配 | 先 run_coding 生成代码到 p2c_temp/，读取后改造适配 |
| skip | 跳过 | 不实现此模块 |

---

## p2c_coding 模块的适配规则

标记为 p2c_coding 的模块，implementer 拿到 P2C 生成代码后需要：

1. **Import 路径改造**
   - 将 rom .base import BaseModel 改为 rom src.model.base import BaseModel
   - 按项目现有代码的 import 风格

2. **基类继承**
   - 如果项目有统一基类，需要继承
   - 例如：class MyModule(BaseModel): 而非独立类

3. **数据接口适配**
   - 输入格式：从论文的格式转为项目的格式
   - 输出格式：从论文格式转为项目下游期望的格式
   - 必要时加 adapter/wrapper

4. **配置整合**
   - 将论文的 config 参数整合到项目的配置系统
   - 参数命名保持项目风格

5. **写入目标路径**
   - 改造后的代码写入项目目录（不是 p2c_temp）
   - p2c_temp 保留作为参考

---

## 模块对照决策表格式

在 plan 中每个 task 应标注：

``markdown
### Task N: {模块名}

**开发模式**: {normal | p2c_reference | p2c_coding | skip}
**决策依据**: {为什么选这个模式}
**论文对应**: {论文中的哪个章节/算法}
**项目落点**: {src/xxx/yyy.py}
**依赖**: Task N-1, ...

**Spec**:
...
``

---

## 自动决策时的注意事项

1. **产生 API 费用**：p2c_coding 模块会调用 OpenAI API 生成代码，在 plan 确认时提醒用户
2. **论文 vs 项目代码量**：如果论文模块很大但项目只需小部分，考虑拆分 task
3. **依赖顺序**：先基础设施，再核心算法，最后辅助模块
