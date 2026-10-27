# 当前论文稿：写至问题一

本稿依据PAPER-Q1-034起草，衔接已有前置与数据章，更新模型假设、符号及问题一正文。它是研究期间的当前稿，不是整题定稿；问题二至问题四未建模，也未编造其结果或全文摘要。原有稿件和研究产物均保留。

## 阅读与修改

- `问题一论文草稿.pdf`：当前14页PDF，问题一从第9页开始（原构建名paper.pdf）。
- `问题一论文草稿.tex`：当前主入口与统一排版（原名paper.tex）；`sections/question1.tex`、`assumptions.tex`、`symbols.tex`可直接编辑。
- `sections/front.tex`和`sections/data.tex`：由既有前置稿、数据v3稿最小转换得到，保留分析展开，提交文件映射表改为文字。
- `result_values.tex`：从已保存结果生成的数值；不要手工改数。来源与全精度值见`source_manifest.json`。
- `figures/energy_paths.tex`：问题一电量关系图源码；其余5幅PDF是既有代码图的逐字节副本。
- `figures/png/`：当前初稿实际使用的6张300 dpi PNG，按图1—图6中文命名；其中图5和图6是问题一正文两图，可直接插入Word。图题注由正文另排。`manifest.json`保存来源，`qa.json`保存实际查看及复现检查。
- `../../paper_evidence/问题一模型详细讲解报告.md`：给队员读的详细讲解，与论文正文分开。

## 复现排版

在本目录运行 `python build.py`，使用已安装XeLaTeX和xdvipdfmx编译两轮，再用Poppler渲染页面。`python check.py`检查来源、论文数值、引用、黑字和报告链接；不进行模型计算。

实际使用的Python为`C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`；LaTeX位于`C:/Program Files/Latex/miktex/bin/x64`。无需安装新包，LaTeX已关闭自动安装。其本地缓存访问需要运行环境允许。

`build.py`会先执行`prepare.py`，重新生成前置章、数据章、结果宏与既有图片副本。若继续修改这两章，需同步修改`prepare.py`中的文字转换或相应既有输入；避免只改生成文件后被下一次构建覆盖。新写的问题一、假设、符号及能量图不会被该步骤覆盖。

## 来源与检查范围

前置文字来自`front_matter_v1`，数据文字来自`data_chapter_v3`及已确认时间口径；Q1公式、比较、验证来自`20260911-compare-v1`与`20260911-close-v1`、Q1研究报告及证据映射。研究state.json保持revision26及原哈希，局部写作不代替小问冻结或跨问授权。

`build/build_record.json`保存真实构建命令与源文件哈希；`build/qa.json`保存本次一致性检查；`preview/`保存120dpi实际页面。已逐页查看并修正图中标注和结果页留白，未发现公式、表格、图注裁切或失效引用。旧版LaTeX发行日期及字体重定义提示保留在日志，不影响本次输出；未安装或更新软件。

上述均为AI检查，作者尚需阅读、修改和核验。最终摘要、其他三问、全篇评价与比赛提交文件规范，留待相应研究及整合阶段完成。

## 单独导出PNG

`export_png.py`只读当前矢量PDF和图源，不运行模型或重编论文。默认写入figures/png；为保留既有文件，目标目录已存在时拒绝覆盖。复现时使用`--output`指定项目内新目录，例如projects/2026-C/tmp/q1-png-reproduction-v1（从仓库根运行）。图5由当前第9页经过核对的矢量图区域直接渲染，未从低分辨率页面截图放大。

当前PDF/TeX已经使用中文文件名，旧build.py/check.py仍保留历史英文入口及当时状态断言；此次仅补PNG，未调用这两个脚本。以后重新编论文时需核对当前文件名与人工修改再更新构建入口，不能直接运行prepare覆盖改稿。
