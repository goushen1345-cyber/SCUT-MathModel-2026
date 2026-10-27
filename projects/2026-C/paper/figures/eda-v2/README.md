# 数据探索论文候选图

最新图形版本为本目录eda-v2，统计来源为audit/eda-v1。eda-v1图目录是首次排版留痕，包含已修正的减号字体问题；请使用本目录。

`eda_figures.pdf`为七页图集，每页一组；01—07同名PDF是可插入LaTeX的单图素材，PNG用于预览。精确统计、来源和解释见项目report.md第11节及paper_evidence/figure_registry.md。本图集不是论文正文或购电研究结果。

## 复现

在仓库根目录运行，输出目录必须不存在：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'projects/2026-C/scripts/explore_data.py' --output 'tmp/eda-statistics-reproduction'
& 'E:/Anaconda/python.exe' -X utf8 'projects/2026-C/scripts/plot_eda.py' --input 'audit/eda-v1' --output 'tmp/eda-figures-new-reproduction'
```

独立统计核验脚本为scripts/verify_eda.py，核验当前audit/eda-v1。绘图实际使用现有Anaconda的Python、matplotlib和宋体；图集合并使用捆绑Python的pypdf，详细版本、字体路径与哈希见manifest.json。

捆绑Python没有matplotlib，所以绘图使用已安装的Anaconda，没有安装或修改软件。受限环境可能需要允许Anaconda加载现有DLL；其numexpr版本提示只表示未使用该可选加速，不改变本次已有统计。源码复现已在项目独立临时目录成功，所有图的PDF/PNG均一致。

图中文字、图例和单位已通过AI视觉检查及全页边界检查，见qa.json；尚未人工审阅，也尚未放入论文检查最终排版。所有均值是原标签采样均值，非kWh；全年统计是事后描述，不能作为零点提前可得的信息。
