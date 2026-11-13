# P2C Skill — Paper2Code 工具集成

## 概述
此 Skill 封装 Paper2Code 仓库的能力，使 SDD 的 implementer subagent 可通过 Shell 调用 P2C 的 planning、analyzing、coding、debugging 脚本。

## 前置条件
- P2C 仓库位于: `paper2code/`
- 依赖已安装: `pip install openai`（如果用 OpenAI API）或 `pip install vllm`（如果本地模型）
- 待分析论文的 JSON 文件已准备好（PDF 需先通过 s2orc-doc2json 转换）
- 环境变量: `OPENAI_API_KEY` 已设置

## 接口

### 1. 论文分析 — Planning 阶段

**用途**: 提取论文的架构设计、实验计划、配置信息

**调用方式**:
```bash
python paper2code/codes/1_planning.py \
    --paper_name <PAPER_NAME> \
    --gpt_version <GPT_VERSION> \
    --pdf_json_path <PAPER_JSON_PATH> \
    --output_dir <OUTPUT_DIR>
```

**输入参数**:
- `PAPER_NAME`: 论文名称（如 "Transformer"）
- `GPT_VERSION`: 使用的 GPT 版本（如 "o3-mini"）
- `PAPER_JSON_PATH`: 论文 JSON 文件路径
- `OUTPUT_DIR`: 输出目录（如 `p2c_outputs/<PAPER_NAME>`）

**输出**: `{OUTPUT_DIR}/planning_artifacts/`
- 架构设计文档
- 任务列表
- 实验计划

**后续步骤**: 运行配置提取
```bash
python paper2code/codes/1.1_extract_config.py \
    --paper_name <PAPER_NAME> \
    --output_dir <OUTPUT_DIR>
```
输出: `{OUTPUT_DIR}/planning_config.yaml`

---

### 2. 论文分析 — Analyzing 阶段

**用途**: 对论文中每个待实现文件进行详细的逻辑分析

**调用方式**:
```bash
python paper2code/codes/2_analyzing.py \
    --paper_name <PAPER_NAME> \
    --gpt_version <GPT_VERSION> \
    --pdf_json_path <PAPER_JSON_PATH> \
    --output_dir <OUTPUT_DIR>
```

**输出**: `{OUTPUT_DIR}/analyzing_artifacts/`
- 逐文件的算法逻辑分析
- 依赖关系
- 实现注意事项

---

### 3. 代码生成 — Coding 阶段

**用途**: 根据论文分析结果生成代码文件。仅在 adaptation_plan 中标记 `p2c_coding` 的模块调用。

**调用方式**:
```bash
python paper2code/codes/3_coding.py \
    --paper_name <PAPER_NAME> \
    --gpt_version <GPT_VERSION> \
    --pdf_json_path <PAPER_JSON_PATH> \
    --output_dir <OUTPUT_DIR> \
    --output_repo_dir <OUTPUT_REPO_DIR>
```

**输入**: 同 Planning + 分析阶段已完成的输出目录

**输出**: `{OUTPUT_REPO_DIR}/` — 生成的代码仓库。包含按模块组织的 Python 文件、配置文件和运行脚本。

---

### 4. 调试修复 — Debugging 阶段（可选）

**用途**: 运行代码后根据错误自动生成修复补丁

**调用方式**:
```bash
python paper2code/codes/4_debugging.py \
    --paper_name <PAPER_NAME> \
    --gpt_version <GPT_VERSION> \
    --output_repo_dir <OUTPUT_REPO_DIR>
```

---

### 5. 一键分析 — analyze_paper_full()

**用途**: 运行 Planning + Config提取 + Analyzing 三个步骤（Brainstorming 第二轮前调用）

**Python 调用**:
```python
from p2c_tools.p2c_wrapper import analyze_paper_full

result = analyze_paper_full(
    paper_name="Transformer",
    gpt_version="o3-mini",
    pdf_json_path="examples/Transformer_cleaned.json",
    output_dir="p2c_outputs/Transformer"
)
# result 包含 planning_dir, analyzing_dir, config_yaml 路径
```

**CLI 调用**:
```bash
python p2c_tools/p2c_wrapper.py full --paper Transformer --gpt o3-mini --json examples/Transformer_cleaned.json --out p2c_outputs/Transformer
```

---

## 调用规则

| 阶段 | 调用时机 | 谁调用 |
|------|---------|--------|
| Planning | Brainstorming 第二轮之前 | `analyze_paper_full()` |
| Analyzing | Brainstorming 第二轮之前 | `analyze_paper_full()` |
| Coding | adaptation_plan 中标记 `p2c_coding` 的模块 | SDD implementer subagent |
| Debugging | Coding 后代码有运行错误时 | SDD implementer subagent |

## 注意事项
- P2C 仓库为外部项目，只读使用，不修改其内部代码
- P2C 生成的代码是独立仓库，implementer 拿到后需要按项目骨架改造（改 import、改 base class、适配数据接口）
- Planning + Analyzing 的输出是纯自然语言 + JSON + YAML，implementer 需自行提取结构化信息
