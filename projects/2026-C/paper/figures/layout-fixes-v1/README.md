# 三张论文图的重叠修订

三张原图均使用Python/Matplotlib绘制，中文字体为SimSun。此次只使用保存的结果，不拟合、不求解、不改数据；旧代码、旧图及完整论文保留。

## 原图与源码对应

1. 指定日期供需、库存与缺口补充（用户第一张截图）：原代码`paper/q3_manuscript_v2/prepare.py`的specified_days绘图段，论文原图`paper/complete_manuscript_v1/q3_figures/specified_days.pdf`。截图是完整两列图的左列；新版保留原来的3月20日和9月23日两列。
2. 近期误差准备参数的费用依据（用户第二张截图）：原代码`questions/Q3/runs/20260911-parameter-interpretability-v1/plot.py`，原图`figures-v1/01_parameter_interpretability.pdf`，论文中使用parameter_interpretability.pdf。
3. 三种策略在相同代表日下的购电与储能安排（用户第三张整页截图及第四张局部截图）：原代码`questions/Q1/runs/20260911-compare-v1/present.py`，原图`figures-v4/01_daily_dispatch.pdf`，论文中使用q1_daily_dispatch.pdf。

以上路径均相对projects/2026-C。

## 修订与输出

- `01_Q3_specified_days.pdf/.png`：两组图例分别放入独立空白行，离开供需曲线及缺口图；增加行间距，保留两列三行数据。模型选择、日期选择、库存、缺口及紧急电量表达式沿用原代码。
- `02_Q3_parameter_interpretability.pdf/.png`：第一子图图例置于坐标框外，最低值标注移到柱顶上方；调整折线数字位置，增大边缘留白，避免数字压线或压标题。四组筛选口径、柱/点位置和数值不变。原图包含0.575和0.625两根未单列刻度的柱，新图同样保留。
- `03_Q1_daily_dispatch.pdf/.png`：电价图与储电图之间新增独立图例行，下方储电量和购电功率两图整体下移；图例与10800虚线分开。三条策略曲线及1200/10800边界保留。

PNG为300dpi，PDF为矢量格式。`*_preview.png`直接由PDF通过Poppler按140dpi渲染，作为矢量输出检查材料。

## 复现及数据核验

仓库根目录执行：`python projects/2026-C/paper/figures/layout-fixes-v1/build.py`。

`prepare_sources.py`从上述原代码抽取三张图的绘图段并明确应用布局修改，生成`draw_specified_days.py`、`draw_parameters.py`、`draw_dispatch.py`。`build.py`依次运行，仅写当前修订目录。依赖本机Python、Matplotlib、NumPy、Pandas与Poppler，不运行任何研究模型。

`manifest.json`记录原代码、输入数据、当前源码和输出的SHA256；已核对绘制前后原始输入及原代码哈希全部一致。目标只有修正显示，未增加验证结论。

## 实际画面检查

主AI已逐张查看最终矢量PDF的渲染预览：两套供需/缺口图例不与数据区重叠；参数图图例、最低值、折线数字与标题已分开；三策略图例位于独立留白，与10800虚线不重叠。中文、单位、坐标和日期完整。此次没有替换或重新编译完整论文，嵌入论文后的最终页待采用时核查，AI看图不代表人工审稿。

图题、图前说明及研究含义沿用原论文和图登记Q3-F06、Q3-F04及问题一三策略调度图；只改善可读性，不改变原图支持的论断或适用边界。
