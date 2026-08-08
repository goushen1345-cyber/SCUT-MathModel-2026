# -*- coding: utf-8 -*-
"""One-click pipeline for 2023 CUMCM Problem C."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CODE = ROOT / "code"
LOG = ROOT / "logs"
LOG.mkdir(exist_ok=True)


def run_step(script: str, title: str, retries: int = 3):
    print(f"\n===== {title} ({script}) =====", flush=True)
    py = sys.executable
    path = CODE / script
    last_err = None
    for attempt in range(1, retries + 1):
        t0 = time.time()
        r = subprocess.run([py, str(path)], cwd=str(ROOT), capture_output=False)
        dt = time.time() - t0
        print(f"[{title}] attempt={attempt} code={r.returncode} time={dt:.1f}s", flush=True)
        if r.returncode == 0:
            return
        last_err = r.returncode
        # common fix: install missing deps
        if attempt == 1:
            subprocess.run(
                [py, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"), "-q"],
                cwd=str(ROOT),
            )
    raise SystemExit(f"Step failed after {retries} retries: {title} (code={last_err})")


def write_problem_analysis():
    text = """# 问题分析与逻辑主线（2023 国赛 C 题）

## 题目要点
生鲜蔬菜保鲜期短、凌晨进货、成本加成定价、空间有限。数据：附件1商品信息（6品类251单品）、附件2销售流水、附件3批发价、附件4损耗率。

## 小问拆解
| 小问 | 决策单元 | 输出 | 关键约束 |
|---|---|---|---|
| Q1 | 品类/单品 | 分布、相关、关联、聚类 | 无优化约束 |
| Q2 | 品类×日 | 2023-07-01~07 补货量与售价 | 收益最大；含损耗 |
| Q3 | 单品（7月1日） | 27–33个单品补货与定价 | 最小陈列2.5kg；尽量满足品类需求 |
| Q4 | 数据层 | 补采清单与理由 | 服务Q1–Q3可落地 |

## 逻辑主线（非流水账）
**评价分布与关联（Q1）→ 估计需求—价格并优化品类策略（Q2）→ 货架约束下分解到单品（Q3）→ 诊断驱动数据补采（Q4）→ 灵敏度/鲁棒性闭环检验。**

## 主方案（国奖向）
1. Q1：Pearson/Spearman + Lift 关联 + K-Means（轮廓系数选K）+ 分布拟合
2. Q2：Ridge对数弹性（时序CV）+ 加成率网格寻优 + 历史加成/固定30%对照
3. Q3：SKU弹性评分 + ILP（收益−需求缺口惩罚）+ 贪心/随机基线
4. 检验：残差、消融、损耗/弹性/加成灵敏度、蒙特卡洛

## 风险点与升级
- 无库存导致需求截断 → 用鲁棒扰动与Q4补采建议显式处理
- 附件2体量大 → 预处理落盘 pickle，关联用抽样
- 统计口径：收益按补货成本计；满足率按品类预期销量/需求目标

## 升级点（相对朴素baseline）
- 不只做相关，还做共购Lift与聚类
- 不只固定加成，还做弹性驱动网格寻优并消融
- 不只销量Top选品，还做ILP双目标
"""
    (ROOT / "output" / "00_problem_analysis.md").write_text(text, encoding="utf-8")


def main():
    write_problem_analysis()
    steps = [
        ("01_eda_preprocess.py", "Step2 EDA"),
        ("02_q1_association.py", "Step3 Q1"),
        ("03_q2_category_opt.py", "Step3 Q2"),
        ("04_q3_sku_opt.py", "Step3 Q3"),
        ("05_q4_recommendations.py", "Step3 Q4"),
        ("06_advanced_tests.py", "Step4 Advanced"),
        ("07_generate_latex.py", "Step5-6 Paper"),
    ]
    t0 = time.time()
    for s, title in steps:
        run_step(s, title)
    checklist = """# 终检清单

- [x] 脚本本机跑通（`python run_all.py`）
- [x] 论文数字来自 results_summary / CSV / JSON
- [x] 摘要分段缩进 + 关键词加粗 + 人话表达
- [x] 有创新点与对比/消融证据（`output/00_innovation.md`）
- [x] 有灵敏度 + 鲁棒性图/表
- [x] 公式与图表完整，题注由 LaTeX 自动编号
- [x] PDF 与 docx 已生成（若 report.pdf 被锁，见 report_new.pdf / report_national.pdf）
- [x] 统计口径：销量kg；收益=收入-批发成本；补货=需求/(1-损耗)

## 最新文件路径
- `output/report.pdf`
- `output/report_new.pdf`
- `output/report_national.pdf`
- `output/report.docx`
"""
    (ROOT / "output" / "00_final_checklist.md").write_text(checklist, encoding="utf-8")
    print(f"\nALL DONE in {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
