# 数据章节第二版

本版按用户要求精简7.1：来源简要带过，整理过程只写一段，以“经过整理与分析，我们有以下发现”引出7.2及后续分析。原7.2—7.5文字、数字、四张源图保持不变；图1、图2仅调整显示尺寸，末段完整换页。

`data_chapter.tex`为源文件，`data_chapter.pdf`为修订稿，仍为5页、4图、无表格。图1—4位于第1—4页，第5页为预报更新的配对比较与费用含义两段。已实际查看页面；完整保留内容，末页自然收尾，不补写凑页内容。前版保留在paper/data_chapter_v1。

在仓库根目录运行以下命令重新编译并渲染预览：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'projects/2026-C/paper/data_chapter_v2/build.py'
```

依赖现有XeLaTeX、xdvipdfmx和Poppler，禁用自动安装；源码、输入图和PDF哈希见build/build_record.json，实际检查见build/qa.json。详细统计来源继续沿用paper_evidence/data.md。

7.1删去的行数、时间边界例子及逐日信息说明仍保留在研究记录与原前置稿；删简不改变这些约定。原始数据、研究状态、旧稿未改，没有新增分析或建模。
