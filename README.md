# Geo Benchmark

基于 Wolfram Engine 的几何场景自动生成与基准测试系统。

## 项目结构

```
geometricScene-builder/
├── .opencode/                    # Opencode Agent/Skill/Tool 定义
│   ├── agents/                   # 5 个 Agent
│   │   ├── geo-orchestrator.md          # Prime Agent (总协调)
│   │   ├── problem-constraint-designer.md # 问题与约束设计指南
│   │   ├── bench-runner.md              # 基准测试执行
│   │   ├── scorer-ui.md                 # 人工打分界面
│   │   └── analyst-reporter.md          # 分析与报告生成
│   ├── skills/                   # 6 个 Skill (知识库)
│   │   ├── agent-io-schema/             # ✨ Agent 数据流 Schema
│   │   ├── dimensionless-constraints-library/
│   │   ├── wl-benchmark-runbook/
│   │   ├── human-rating-loop/
│   │   ├── analysis-standard/
│   │   └── reporting-standard/
│   └── tools/
│       └── geo-tools.ts        # TypeScript 工具包装
├── core/                         # 底层库 (Agents 调用)
│   ├── __init__.py
│   ├── bench.py                  # 基准测试执行器
│   ├── constraints.py            # 约束构建 Pipeline
│   ├── report.py                 # 报告生成
│   └── analyze.py                # 分析工具
├── examples/                     # 示例代码
│   ├── README.md
│   ├── test_constraints.py       # 约束测试
│   └── verify_setup.py           # 环境验证
├── app/
│   └── rate_streamlit.py         # scorer-ui 的 Streamlit 实现
├── wl/
│   ├── scene_builders.wl         # Wolfram 约束构建器 (纯函数)
│   │   ├── BuildOrientation[]    # 朝向约束
│   │   ├── BuildAngleMin[]       # 角度下界
│   │   ├── BuildSideRatio[]      # 边长比 (Min/Max)
│   │   ├── BuildHeightBase[]     # 高度/底边比
│   │   └── BuildHeightPerimeter[]# 高度/周长比
│   └── bench_core.wl             # Wolfram 求解核心
├── configs/
│   └── sweep.yaml                # 约束配方配置
├── data/
│   └── problems.jsonl            # 几何问题定义
└── outputs/
    └── run_YYYYMMDD_HHMMSS/      # 运行输出
        ├── results.jsonl         # 结果数据
        ├── images/               # 渲染图像
        ├── report.md             # Markdown 报告
        ├── report.html           # HTML 报告
        ├── analysis.md           # 统计分析
        ├── figures/              # Plotly 交互图表
        └── ratings.csv           # 人工打分 (可选)
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

**要求**:
- Python 3.8+
- Wolfram Engine 14.0+ (已安装并配置)

### 2. 准备数据

编辑 `data/problems.jsonl`，每行一个几何问题：

```json
{
  "id": "p0001",
  "text": "在△ABC 中，AB=AC=5，BC=6",
  "points": ["A", "B", "C"],
  "base_edge": ["B", "C"],
  "base_hypotheses_wl": [
    "EuclideanDistance[A, B] == EuclideanDistance[A, C]",
    "EuclideanDistance[B, C] == 6"
  ],
  "meta": {"source": "manual", "difficulty": "easy"}
}
```

### 3. 配置约束配方

编辑 `configs/sweep.yaml`：

```yaml
timeout_s: 60
random_seeds: [1]
render_images: true

constraint_recipes:
  - name: baseline_only
    risk: low
    layout: null
    shape: []
    
  - name: angle_min_10
    risk: medium
    layout:
      triangle_base_horizontal: true
    shape:
      - type: angle_min
        min_deg: 10
        
  - name: side_ratio_0p3
    risk: medium
    layout:
      triangle_base_horizontal: true
    shape:
      - type: side_ratio
        min_ratio: 0.3
```

**风险等级**:
- **low**: 仅朝向约束
- **medium**: 单个角度或边长比约束
- **high**: 高度相关约束 (可能超时)

### 4. 运行基准测试

**方式 A: 使用 Opencode Agent** (推荐)

在 Opencode 中调用：

```
run_sweep(
  config_path="configs/sweep.yaml",
  problems_path="data/problems.jsonl"
)
```

**方式 B: 直接运行 Python**

```bash
python core/bench.py --config configs/sweep.yaml --problems data/problems.jsonl
```

### 5. 生成报告

**使用 Opencode Agent**:

```
build_report(run_dir="outputs/run_20260224_120000")
```

**直接运行**:

```bash
python core/report.py --run_dir outputs/run_20260224_120000
python core/analyze.py --run_dir outputs/run_20260224_120000
```

### 6. 人工打分 (可选)

启动 Streamlit GUI：

```bash
streamlit run app/rate_streamlit.py -- --run_dir outputs/run_20260224_120000
```

在浏览器打开 http://localhost:8501 进行 1-5 打分。

## 数据 Schema

### problems.jsonl

**Producer**: problem-collector / human  
**Consumer**: bench-runner

```json
{
  "id": "p0001",                    // required, unique
  "text": "题目描述",                // optional
  "points": ["A", "B", "C"],        // required
  "base_edge": ["B", "C"],          // optional, 建议底边
  "base_hypotheses_wl": [...],      // required, Wolfram 表达式
  "meta": {
    "source": "manual",
    "difficulty": "easy"
  }
}
```

### sweep.yaml

**Producer**: problem-constraint-designer / human  
**Consumer**: bench-runner

```yaml
constraint_recipes:
  - name: string                    # 唯一名称
    risk: "low" | "medium" | "high"
    layout:
      triangle_base_horizontal: boolean
    shape:
      - type: "angle_min" | "side_ratio" | "height_base" | "height_perimeter"
        min_deg: float              # angle_min 专用
        min_ratio: float            # ratio 类型专用
```

### results.jsonl

**Producer**: bench-runner  
**Consumer**: analyst-reporter, scorer-ui

```json
{
  "problem_id": "p0001",
  "recipe_name": "angle_min_10",
  "seed": 1,
  "success": true,
  "solve_time_s": 1.23,
  "fail_type": "",                  // timeout|invalid_head|runtime_error|...
  "scene_build_time_s": 0.003,
  "solver_wall_time_s": 12.5,
  "algebraic_complexity": 3809,
  "image_path": "images/p0001_angle_min_10_1.png"
}
```

### ratings.csv

**Producer**: scorer-ui (human)  
**Consumer**: analyst-reporter

```csv
problem_id,recipe_name,seed,rating,comment,rated_at
p0001,angle_min_10,1,4,"好图",2026-02-24T10:00:00Z
```

## 约束类型

系统支持 5 种约束构建器 (扁平化，无层级概念)：

| 约束类型 | Wolfram 函数 | 计算复杂度 | 风险等级 |
|---------|-------------|-----------|---------|
| **朝向** | `BuildOrientation[points, baseEdge]` | O(1) | low |
| **角度下界** | `BuildAngleMin[points, minDeg]` | O(n²) | medium |
| **边长比** | `BuildSideRatio[points, minRatio]` | O(1) | medium |
| **高度/底边** | `BuildHeightBase[points, baseEdge, minRatio]` | O(1) | high |
| **高度/周长** | `BuildHeightPerimeter[points, minRatio]` | O(1) | high |

**推荐实验策略**:
1. 从 baseline (无约束) 开始
2. 逐个添加约束类型
3. 每个约束测试 2-3 个阈值
4. 避免同时叠加多个 high 风险约束

## Opencode Agents

### geo-orchestrator (Prime Agent)

**职责**: 总协调，接收用户指令并调度子 Agent

**工作流**:
1. 调用 `problem-constraint-designer` 验证配置
2. 调用 `bench-runner` 执行测试
3. 可选：调用 `scorer-ui` 进行人工打分
4. 调用 `analyst-reporter` 生成分析报告

### bench-runner

**职责**: 执行 Wolfram 基准测试

**输入**: `problems.jsonl`, `sweep.yaml`  
**输出**: `results.jsonl`, `images/`

### analyst-reporter

**职责**: 合并结果与评分，生成决策就绪的分析

**输入**: `results.jsonl`, `ratings.csv` (可选)  
**输出**: `analysis.md`, `figures/*.html`

### scorer-ui

**职责**: 提供人工打分界面

**输入**: `results.jsonl` (筛选成功案例)  
**输出**: `ratings.csv`

### problem-constraint-designer

**职责**: 提供配置模板与验证 (人工操作指南)

**定位**: 不自动生成配置，而是提供 schema 验证与设计模式指导

## 开发说明

### 添加新约束类型

1. 在 `wl/scene_builders.wl` 添加 Wolfram 函数
2. 在 `core/constraints.py` 添加 Python 包装器
3. 更新 `configs/sweep.yaml` 添加测试配置
4. 更新 `dimensionless-constraints-library/SKILL.md`

### Schema 验证

所有数据 schema 定义在 `.opencode/skills/agent-io-schema/SKILL.md`，Agents 会据此验证输入输出。

## 故障排查

### Wolfram 连接失败

```bash
wolframscript -code '1+1'
```

### Python 包缺失

```bash
pip install -r requirements.txt
```

### 路径错误

使用项目根目录下的相对路径，所有 Agents 会自动解析。

## 项目状态

✅ 完整实现的核心链路:
- bench-runner (core/bench.py)
- analyst-reporter (core/report.py + analyze.py)
- scorer-ui (app/rate_streamlit.py)
- Wolfram 约束构建器 (wl/scene_builders.wl)

✅ 文档与代码对齐:
- Agent/Skill 定义与实现一致
- Schema 统一 (agent-io-schema)
- 术语扁平化 (移除 L0/L1/L2/L3)

## 许可证

MIT
