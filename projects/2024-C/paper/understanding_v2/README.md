# 第一阶段论文草稿v2

本目录为2026-09-10明确授权的第一阶段重做交付，版本UNDERSTANDING-20260910-v2。仅包含前置章节和题意模型要素图，不使用旧研究的销量代理、候选算法、情景或结果。

- 可编辑正文：`../front_matter_understanding_v2.md`。
- LaTeX源与4页阅读稿：`front_matter_understanding_v2.tex`、`front_matter_understanding_v2.pdf`。
- 框架图结构/源码/独立复现：`../figures/understanding_v2/`；最终使用`render_v2/framework.pdf`。
- 研究与完整歧义：`../../report.md`的UNDERSTANDING-20260910-v2区。
- 来源/保护清单：`source_manifest.json`；交付核对：`validation.json`。

从仓库根目录运行以下命令即可从Markdown及代码图PDF重建本文：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' projects/2024-C/paper/understanding_v2/build_paper.py
```

脚本只读取本轮文字和框架图并排版，不读取工作簿或导入研究脚本。先运行图目录README中的命令可重建图形。`--source-only`只生成LaTeX。

环境为Python 3.12.14、MiKTeX-XeTeX 4.16（MiKTeX 25.12）、ctex/xeCJK、SimSun/SimHei/Times New Roman、Poppler。编译禁用自动安装；本机MiKTeX需要字体/缓存访问，本轮经工具自动审批获得必要执行权限。编译日志含安装包要求较新LaTeX发行版的提示，实际编译与四页渲染成功，无Overfull、缺字或未定义引用告警。

已检查4页实际渲染：主执行者第1/4页，独立AI第2/3页；修正了表格缩进、表题分页及符号表孤立分页，最终图以约15.36cm宽嵌入第4页。全黑文字、白底表、图题及正文衔接完整。第3页引图段后留白用于将完整图置于第4页，没有缩字塞满页面。

这些是AI文字、来源、技术与版式核对，不是用户人工核验；未进行真实读者10—20秒计时试读。本轮交付待用户确认，停止于第一阶段，不自动启动数据审计、处理、EDA或Q1。本稿是训练前置草稿，未进行整篇提交材料或当届提交格式的最终验收。
