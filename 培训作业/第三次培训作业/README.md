# 2022 国赛 C 题：古代玻璃制品的成分分析与鉴别

## 一键复现

```bash
cd 培训作业/第三次培训作业
python -m pip install -r requirements.txt
python run_all.py
```

## 产出

- `output/report.pdf` / `output/report.docx`
- `output/figures/`、`output/tables/`
- `output/results_summary.md`、`output/00_*.md`
- `code/` 分小问脚本（通过 `sys.path` 导入，无 `code/__init__.py`）

## 口径

- 有效样本：成分比例累加和 ∈ [85%, 105%]
- 空白成分按 0 处理（未检出）
- 风化前预测：类型条件风化因子反演后归一化到 100%
