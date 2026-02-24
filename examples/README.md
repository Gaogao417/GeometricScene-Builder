# Geo Benchmark Examples

示例代码展示如何调用 `core/` 中的底层接口。

## 示例列表

### 1. test_constraints.py

测试所有约束构建器的基本功能。

**运行方式**:

```bash
python test_constraints.py
```

**功能**:
- 初始化 Wolfram 会话
- 测试 5 种约束构建器
- 验证约束组装
- 输出测试结果

### 2. verify_setup.py

验证 Wolfram Engine 连接是否正常。

**运行方式**:

```bash
python verify_setup.py
```

**功能**:
- 测试 Wolfram 内核启动
- 执行简单计算 (1+1)
- 验证 wolframclient 连接

## 如何调用 core 接口

### 示例代码

```python
from core import (
    BuildOrientation,
    BuildAngleMin,
    BuildSideRatio,
    BuildHeightBase,
    BuildHeightPerimeter,
    AssembleConstraints,
)
from wolframclient.language import wl, wlexpr, Global
from wolframclient.evaluation import WolframLanguageSession

# 初始化会话
session = WolframLanguageSession("D:/Program Files/Wolfram Research/Wolfram/14.3/wolfram.exe")

# 加载 Wolfram 构建器
session.evaluate(wlexpr('Get["wl/scene_builders.wl"]'))

# 定义点
points = wl.List(WLSymbol("A"), WLSymbol("B"), WLSymbol("C"))
base_edge = wl.List(WLSymbol("B"), WLSymbol("C"))

# 构建约束
constraints = []
constraints.append(BuildOrientation(points, base_edge))
constraints.append(BuildAngleMin(points, 10))
constraints.append(BuildSideRatio(points, 0.3))

# 组装场景
base_hyp = wl.List(wlexpr("EuclideanDistance[A, B] == EuclideanDistance[A, C]"))
all_constraints = AssembleConstraints(points, base_edge, [
    {"type": "angle_min", "min_deg": 10},
    {"type": "side_ratio", "min_ratio": 0.3}
])

scene = session.evaluate(
    Global.AssembleScene(points, base_hyp, wl.List(*all_constraints))
)

# 求解
result = session.evaluate(wlexpr(f"RandomInstance[{scene}]"))
```

##  Agents 调用示例

bench-runner agent 通过 geo-tools.ts 调用 `core/bench.py`：

```typescript
// geo-tools.ts
const reportOut = runPython(worktree, "core/bench.py", [
  "--config", configPath,
  "--problems", problemsPath,
  "--out", outDir
]);
```

analyst-reporter agent 调用 `core/report.py` 和 `core/analyze.py`：

```typescript
const reportOut = runPython(worktree, "core/report.py", ["--run_dir", runDir]);
const analysisOut = runPython(worktree, "core/analyze.py", ["--run_dir", runDir]);
```
