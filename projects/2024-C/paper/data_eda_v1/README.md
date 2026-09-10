# 数据预处理与探索性分析章节草稿

- chapter.md：可编辑论文文字。
- chapter.tex / chapter.pdf：LaTeX与6页阅读稿，4页正文+2页明细附录。
- data_figures.zip：6张最终图的PDF、PNG、SVG；图源、实际输入与复现命令见../../data/eda/DATA-EDA-PAPER-v1/README.md。

正文包括来源关联、预处理复用/核查、土地与历史结构、适种观测覆盖、亩产成本价格差异和时间口径。局部图表编号1—4、A1—A2，整合全文时应统一编号；本轮不修改前置草稿或既有全文。全部新数字来自本次EDA及已有审计，不使用旧优化结果。稿件由AI起草并核对，待用户审阅；没有真人逐格复算或完整比赛提交合规验收。

从仓库根生成（需要本机MiKTeX、SimSun/SimHei/Times New Roman、ctex和Poppler）：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 projects/2024-C/paper/data_eda_v1/build.py
```

脚本只排版本Markdown及最终六图，禁用自动安装，不执行数据研究。build.py重新生成本候选章节的tex/PDF与预览，勿用于覆盖已冻结版本。本机MiKTeX需读写自身字体/缓存，获限定审批后编译。发行版提示较新release及字体family重定义，最终无Overfull、缺字或未定义引用，6页全部实际查看、图表未裁切。底层图6张在独立目录复现PNG/PDF一致；PDF提取全部文字黑色。技术/视觉核对与科学证据边界见项目report和EDA目录核验记录。

销量、销售池和跨年收益、轮作空间与未来概率等仍为未决语义。本文仅提出其必要表达要求，不假装完成这些研究，也不声明历史面积证明多年覆盖。
