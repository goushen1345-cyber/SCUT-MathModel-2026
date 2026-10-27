# 数据预处理与探索性分析：第三版

当前试读稿为`data_chapter.pdf`，可编辑源文件为`data_chapter.tex`。4页、5小节、4张既有代码图，无表格。旧稿data_chapter_v1/v2保留。

本次根据用户反馈，将章名改为“数据预处理与探索性分析”，7.1仅简要说明来源和实际预处理。其余小节从主要发现展开：日内供需错配、季节中负载与光伏的不同步、星期差异和跨日电价波动、预报更新的改善与局限。用约数保留主要证据，减少连续极值、相关系数和重复指标的罗列，扩充对现象及购电含义的解释。

输入仍为既有prepared-v1、EDA-v1与eda-v2图形，没有新增统计、预测或策略计算。精确数字与被精简的统计仍保留在audit/eda-v1和report.md，改写对应关系见paper_evidence/data.md。4张源图不改，前两图显示宽度82%，后两图78%，均保持原比例，最终分别位于第1—4页。

复现排版：在仓库根目录运行：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'projects/2026-C/paper/data_chapter_v3/build.py'
```

沿用现有字体、字号、行距和页边距；使用XeLaTeX、xdvipdfmx、Poppler，禁用自动安装。实际命令与输入/PDF哈希见build/build_record.json，来源保持、约数及实际4页检查见build/qa.json。4页实际渲染均已查看，文字黑色、图与单位清楚、末段不再孤立成页。当前为AI修订与检查的试读稿，不代表人工审定或完成最终提交格式核验。
