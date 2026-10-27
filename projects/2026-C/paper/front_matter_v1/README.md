# 2026-C 前置章节 v1

本目录是经用户明确授权的局部论文草稿，含背景、重述、分析、初步总体思路、基本假设与运行约定、基础符号。正文共4页；供用户阅读修订，尚不是整篇论文或最终提交稿。

## 文件

- `front_matter.tex`：可编辑的LaTeX正文源文件，是本稿内容源。
- `front_matter.pdf`：编译后的4页稿件。
- `build.py`：仅执行本地排版与页面渲染，不读取数据工作簿、不进行研究计算。
- `preview/page-1.png`至`page-4.png`：120 dpi页面预览，供版面复核。
- `build/build_record.json`、`build/qa.json`：实际构建命令、源与PDF哈希、字体/页面/文本核对记录。

## 编译

需要已安装的XeLaTeX、xdvipdfmx、Poppler及宋体、黑体、Times New Roman。脚本优先查找PATH，附有本机现有工具路径；已关闭MiKTeX自动安装。

在仓库根目录用PowerShell执行：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'projects/2026-C/paper/front_matter_v1/build.py'
```

MiKTeX编译需要写入其用户缓存。当前执行环境首次限制了缓存访问，随后本地排版命令获得工具权限并成功执行；没有安装软件或下载宏包。重新编译后应查看新页面，不沿用旧版本的检查结论。

## 来源与后续内容

正文依据题面和截至`G0-CONFIRM-009`的已确认口径。2024-C仅提供通用排版参考，不提供本题内容。主张映射、段落职责和未定事项见项目`paper_evidence/data.md`。

数据处理完整章节、各问具体模型与求解、实验及可信度验证、结果图表、摘要和结论留待对应研究材料形成后补充。目前未绘制总体模型图，也未提前定义完整决策变量与时段转换。

写作未改变研究进度：`state/state.json`保持原revision13且字节一致。文稿生成与AI自检不等于人工审阅或数据确认。
