# P2C Tools — Paper2Code 论文分析工具

当需要运行 Paper2Code 分析论文时使用。通常由 paper-theory-flow 主流程触发。

## 能力

| 命令 | 说明 |
|------|------|
| `p2c_wrapper.py full` | 一键运行 Planning + Config提取 + Analyzing |
| `p2c_wrapper.py plan` | 仅运行 Planning |
| `p2c_wrapper.py analyze` | 仅运行 Analyzing |
| `p2c_wrapper.py code` | 运行 Coding（生成代码） |

## 使用方式

### 完整分析（Brainstorming 第二轮前调用）

```bash
python p2c_tools/p2c_wrapper.py full \
    --paper <论文名称> \
    --gpt o3-mini \
    --json <论文JSON路径> \
    --out p2c_outputs/<论文名称>
```

### Python import 方式

```python
from p2c_tools.p2c_wrapper import analyze_paper_full, run_coding

# 一键分析
result = analyze_paper_full(
    paper_name="MyPaper",
    gpt_version="o3-mini",
    pdf_json_path="path/to/paper.json",
    output_dir="p2c_outputs/MyPaper"
)

# 生成代码（用于 p2c_coding 模式）
run_coding(
    paper_name="MyPaper",
    gpt_version="o3-mini",
    pdf_json_path="path/to/paper.json",
    output_dir="p2c_outputs/MyPaper",
    output_repo_dir="p2c_temp/MyPaper"
)
```

## 输入要求
- 论文 JSON 文件（通过 s2orc-doc2json 转换 PDF 得到，或 LaTeX 源码）
- `OPENAI_API_KEY` 环境变量（如果用 OpenAI API）
- 或 vLLM 本地模型（如果用开源模型）

## 输出产物

```
p2c_outputs/<论文名称>/
├── planning_artifacts/
│   ├── 架构设计文档
│   ├── 任务列表
│   └── 实验计划
├── analyzing_artifacts/
│   └── 逐文件逻辑分析
└── planning_config.yaml
```

## 注意事项
- P2C 仓库为外部项目，只读使用
- P2C 生成代码是独立仓库，需按项目骨架改造