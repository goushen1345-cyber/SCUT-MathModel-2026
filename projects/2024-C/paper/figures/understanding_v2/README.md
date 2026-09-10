# FIG-UNDERSTANDING-02 代码与复现

本目录依据主执行者提供的 `structure.json`（UNDERSTANDING-20260910-v2）制作题意层面的建模要素草图。没有读取旧模型来填充结构，没有数据处理、统计汇总、建模或实验，也未修改共享状态、证据账本和图登记表。题意结构核对由主执行者提供；本轮 G0 内容仍待用户确认。

## 可使用文件

- `render_v2/framework.pdf`：最终单页矢量图；建议以 16 cm 宽嵌入。
- `render_v2/framework.png`：220 dpi 清晰预览。
- `render_v2/framework.tex`：自包含 TikZ 源码。
- `build_figure.py`：读取结构定义、生成 TikZ、调用编译和渲染工具。
- `render_v2/commands.json`、`manifest.json`：实际命令、编译环境与输入/输出 SHA256。
- `reproduction_v2/`：第二目录从同一结构与生成代码重新生成的结果。
- `validation.json`：技术复现、实际看图和尺寸检查记录。

`render_attempt1/` 是因 MiKTeX 缓存权限失败的首次输出，`render_v1/` 是断行与边距修正前的预览，`render_final/` 和 `reproduction/` 是补入随图脚注前的上一版本；均不用于正文。`.miktex-data/`、`.miktex-config/` 是仅用于定位权限问题的本地缓存实验，最终成功命令未依赖这些目录。

## 复现命令与环境

从仓库根目录运行，输出必须位于本目录内，且使用不存在的新目录，脚本拒绝覆盖：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'projects/2024-C/paper/figures/understanding_v2/build_figure.py' --out-dir 'projects/2024-C/paper/figures/understanding_v2/reproduction_new'
```

脚本实际按以下顺序运行：

```powershell
xelatex --disable-installer -interaction=nonstopmode -halt-on-error -no-pdf framework.tex
xdvipdfmx -q -o framework.pdf framework.xdv
pdftoppm -png -r 220 -singlefile framework.pdf framework
```

环境：Python 3.12.14；MiKTeX-XeTeX 4.16（MiKTeX 25.12）；TikZ、xeCJK；SimSun 中文、SimHei 标题粗体、Times New Roman 西文；Poppler 26.07.0。节点文字为 10 pt，旁注 8.8 pt，黑字白底。工具路径可通过 `--xelatex`、`--pdftoppm` 覆盖。

本机 MiKTeX 会写入自身缓存和配置。普通沙箱编译报缓存目录权限错误，重定向缓存后仍有注册表写入限制；对限定新图目录的上述脚本申请工具执行权限后自动审核通过，编译成功。脚本使用 `--disable-installer`，未安装新组件。

两次独立编译的 `.tex`、`.png` 字节完全相同，渲染像素也相同。PDF 创建时间不同导致文件哈希不同，不影响可见内容。实际图尺寸及哈希见 `validation.json` 与两次 `manifest.json`。

## 表达映射和验收

十四个节点均直接来自结构定义。农业约束只调整换行，将“重茬·豆类覆盖”和“适度集中”分行，未改变含义。按主执行者复核意见，Q1 的“半价”显示为“基年半价”，并在图底注明基年为 2023 年。为减少交叉，Q2 到亩产、销售上限、价格与超额处置、亩成本的四条边合并为指向外参数组的虚线；Q3 到销售上限、价格、亩成本的三条边合并为指向内关系组的虚线。映射保存在生成清单。参数仍分别连到实际核算组件。

种植面积同时进入产量和种植成本。销售数量竖线与亩成本横线唯一交叉处采用白色桥接断口，表示没有连接。Q2 风险要求用另一条虚线连到七年收益评价，未把风险写成已选定的目标项。Q1 两种超额处置连到计价组件。图不表示前问面积锁定后问面积。

已查看最终 220 dpi 图和 605 px 宽预览（对应 16 cm、96 dpi），完成 AI 视觉检查。快速阅读能辨认共同决策、约束、核算主线和各问增量；没有进行真实读者计时试读。最终论文嵌入页的图题、脚注、字号与分页仍由主执行者随论文 PDF 检查。

星号含义已随图注明：销售上限来源、价格取值及 Q2/Q3 超额处置口径待定；另注明“题意要素草图，数学形式未定”。图题仍建议标明“建模要素草图”。图形技术通过不等于题意、建模口径或 G0 获得人工批准。
