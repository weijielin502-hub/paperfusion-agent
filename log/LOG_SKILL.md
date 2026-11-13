# 日志系统

项目决策和变更的追踪工具，避免重复踩坑。

## 接口

### 读日志
```bash
python log/log.py scan --lines 30
```
```python
from log.log import scan, today
context = scan(30)
today_log = today()
```

### 写日志
```bash
python log/log.py add --message "做了什么" --type config --rationale "替换原因（方案替换必须填）"
```
```python
from log.log import add
add("改了什么", "code", "旧方案有 X 问题，改为 Y")
```

### change_type 取值

| 类型 | 含义 |
|------|------|
| config | 配置文件变更 |
| code | 核心代码变更 |
| agent | Agent 系统提示/角色文件变更 |
| experiment | 实验运行 / 数据变更 |
| doc | 文档 / skill 变更 |
| plan | 方案策划变更（新增/替换） |

## 规则

1. **提方案前** — 先 `scan()` 看日志，避免重复踩坑。
2. **用户确认修改后** — 立即 `add()` 记录。
3. **方案替换（含小范围）** — `rationale` 必须填原因，说明旧方案有什么问题、新方案为什么更好。
4. **首次添加** — `rationale` 可为空。
