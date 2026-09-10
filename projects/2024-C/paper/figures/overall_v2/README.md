# 总体建模框架图交付与复现

图题：**图1 农作物种植优化的统一模型、三问扩展与评价框架**。

本图依据已有题面、数据、研究协议、代码和结果整理；没有重新建模或新增实验。六项获准纠错和限制披露已并入新版论文。总体图替换原图1，实际位于新版论文第3页；图前引入在第2页末，图后完整解释从第4页开始，继而进入“数据整理、符号与基本假设”。

## 文件用途

| 文件 | 用途 |
|---|---|
| content_review.md | 内容审定表、全部节点/边及含义、共享与专属模块、图题、图前后段落、插入位置、来源与省略说明 |
| structure.json | 19个节点、共享分组与18条关系记录；保留追溯来源，内部ID不印入图 |
| prepare_definition.py | 从结构定义生成审定表和来源哈希，不进行数据处理 |
| build_tikz.py | 生成TikZ并调用排版器输出PDF、SVG、PNG |
| render/overall_framework.tex、pdf、svg、png | 总体框架图自包含源码及三种图形格式 |
| render/q3_relationship.tex、pdf、svg、png | 同步纠正的图8；区分相关机制与交叉价格需求响应，避免旧图与新文冲突 |
| render/render_manifest.json | 结构及图形文件哈希、生成环境 |
| source_manifest.json | 33项当前依据的哈希；原材料和冻结研究文件只读 |
| reproduction/ | 从相同源码独立再次渲染的结果，PDF元数据可不同，图形内容应相同 |
| ../../final_v2/validation.json | 原始成果完整性、已有数字、文档结构、图形复现及逐页核对记录 |

## 复现

本次环境：Python 3.12.14；MiKTeX-XeTeX 4.16（MiKTeX 25.12），TikZ、xeCJK；SimSun正文、SimHei粗体、Times New Roman西文；pdftocairo生成矢量SVG、Poppler生成PNG。PNG为180 dpi。SVG以矢量路径保存字形，无栅格底图；PDF为单页矢量图。若换字体，文字尺寸可能变化，应重新检查排版。

在本目录执行（Python和TeX可执行程序可按本机安装位置指定）：

```powershell
python prepare_definition.py
python build_tikz.py --out-dir reproduction
```

完整项目用于第一行的来源检查。独立交付包未包含原始附件和冻结研究数据；包内仍可直接运行第二行完成两张图的生成。程序提供`--xelatex`、`--pdftocairo`、`--pdftoppm`参数覆盖默认工具位置。若只需生成图源，可使用`--source-only`。环境不允许自动下载TeX组件，程序使用`--disable-installer`。

自包含`.tex`也可以分别按以下顺序生成PDF及预览：

```powershell
xelatex --disable-installer -interaction=nonstopmode -halt-on-error -no-pdf overall_framework.tex
xdvipdfmx -q -o overall_framework.pdf overall_framework.xdv
pdftocairo -svg overall_framework.pdf overall_framework.svg
pdftoppm -png -r 180 -singlefile overall_framework.pdf overall_framework
```

纸稿由`paper/build_paper_v2.py`生成DOCX，再由`paper/export_paper_v2.ps1`使用隐藏Word实例导出PDF。常规文档渲染器因本机未安装LibreOffice无法启动，故采用Word实际导出并逐页渲染检查。图1与图8在DOCX中同时保留原生SVG及PNG兼容预览；新版18页PDF已逐页检查。该视觉核对不是新增模型验证，也不等于人工最终确认。

## 阅读要点与边界

中间三个并列框组成同一个种植优化骨架，向三问共同提供变量、农业约束和销售收益结构。横向虚线表示新增现实因素；侧向实线表示实际参考方案传入比较。问题一与问题二的面积仍各自决策，问题三最终保留问题二方案。

销量来自历史产量代理，真实销量仍未知；概率、作物关系及关系系数为模拟设定。问题三同时改变成本和菜价的趋势档位，不能把跨问收益差归因于纯相关效应。已有相关核对仅在训练潜在变量层；累计豆类面积不保证地块内部空间全覆盖，限时求解不证明全局最优。图内保留这些关键边界，参数细节、样本规模、求解间隙与历史诊断留在正文。
