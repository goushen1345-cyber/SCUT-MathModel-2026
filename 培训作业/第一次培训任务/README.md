# CUMCM 2021-C 全自动解题项目

## 题目
生产企业原材料的订购与运输

## 一键复现

```bash
pip install -r requirements.txt
python run_all.py
```

## 目录结构

- `code/` — 分模块代码（EDA、Q1–Q4、LaTeX、PDF）
- `data/` — 原始附件与处理后数据
- `output/figures/` — 论文图表
- `output/tables/` — 结果表
- `output/report.pdf` — 最终论文 PDF
- `logs/` — 运行日志

## 主要输出

| 文件 | 说明 |
|------|------|
| `output/tables/q1_top50_suppliers.csv` | Q1 Top50 供应商 |
| `data/processed/附件A_*.xlsx` | 订购方案（Q2/Q3/Q4） |
| `data/processed/附件B_*.xlsx` | 转运方案（Q2/Q3/Q4） |
| `output/results_summary.md` | 关键数值摘要 |

## 环境
- Python 3.10+
- 依赖见 `requirements.txt`
- PDF：优先 xelatex；无 LaTeX 时自动使用 reportlab
