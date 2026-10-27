# 数据章节第一版

`data_chapter.pdf`是供用户试读的独立数据章，共5页、5小节、4张已有数据图，无表格；`data_chapter.tex`是可编辑的LaTeX源文件。沿用现有前置稿的字体、字号、页边距和行距，暂编号为第7章，图号为本章局部编号1—4，页码从1开始。

本版依照用户2026-09-11的要求，将大纲改写成自然书面语。内容包括来源与实际整理、代表日供需错配、年内变化、星期差异与电价波动、光伏预报误差及更新。没有写入模型、调控方案、求解或节费结果。

依据为data/prepared-v1、audit/eda-v1及report.md已有记录；图片引用paper/figures/eda-v2中的01、02、06、07，不重新生成统计或图片。对应关系及待补事项见paper_evidence/data.md，本轮写作授权见state/decisions.md的PAPER-DATA-017。

## 编译与页面检查

在仓库根目录运行：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'projects/2026-C/paper/data_chapter_v1/build.py'
```

使用已安装XeLaTeX编译两次，再由xdvipdfmx生成PDF、Poppler生成实际页面预览；禁用自动安装。编译需要本地MiKTeX缓存的正常写权限。`build/build_record.json`记录源文和四张图的哈希及实际命令，`build/qa.json`记录最终PDF、逐页检查、字体与输入保持情况。

最终5页均已实际渲染并由AI查看。已修正初版的零散尾页、图文错位和跨图续句；四图完整，文字全黑、字体嵌入、无缺字或页面越界。第1页在完整插图前自然换页，图1及相应解释位于第2页。预览目录只保留最终5页。

原始材料、整理后数据、前置稿和研究state.json/state.md保持不变。本稿尚待用户试读，AI自检不代表人工审定，也未核验最终全文提交格式。

后续补充依赖真实研究：物理时段及能量换算、小时预报到10分钟的处理、各问模型及策略评价。当前描述性误差比较不等于预测训练、储能运行或购电经济收益。
