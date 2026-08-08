# 2023高教社杯全国大学生数学建模竞赛 C题
# 蔬菜类商品的自动定价与补货决策

## 一键复现

```bash
pip install -r requirements.txt
python run_all.py
```

运行后将自动完成：数据预处理 → Q1–Q4 建模 → 灵敏度/鲁棒/消融 → 出图出表 → XeLaTeX 编译 PDF → pdf2docx 转 Word。

## 目录结构

- `data/` 原始附件（含 `attach1..4.xlsx` ASCII 副本）
- `data/processed/` 清洗后面板
- `code/` 分步脚本（勿将目录当作包名遮蔽标准库）
- `output/figures/` 论文图（PNG，300dpi）
- `output/tables/` 论文表（CSV/JSON）
- `output/report.pdf` / `report.docx` 最终论文
- `latex/main.tex` 论文源码
- `logs/` 运行与编译日志

## 口径说明

- 销量/补货单位：千克
- 收益 = 销售收入 − 批发成本（按补货量）
- 补货量 = 预测需求 / (1 − 损耗率)
- 论文数字均来自脚本真实输出，禁止手写估计冒充结果
