# 数据预处理复用、描述性EDA与代码图

本轮DATA-EDA-PAPER-v1由用户明确请求执行，研究许可U032/U033。基础G1-v1-base保持，旧清洗和明文引用已核对，新增数值/数据行改动为0。这里的JSON/CSV是分析结果，不是新冻结模型输入。预期销量、轮作空间、销售归属等未决问题不在本目录选择。

## 复现

从仓库根执行，输出目录必须尚不存在：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 projects/2024-C/data/eda/DATA-EDA-PAPER-v1/analyze.py --output <新的分析输出目录>
& 'E:/Anaconda/python.exe' -X utf8 projects/2024-C/data/eda/DATA-EDA-PAPER-v1/plot.py --input <分析输出目录>/eda.json --output <新的图输出目录>
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 projects/2024-C/data/eda/DATA-EDA-PAPER-v1/verify.py
```

正式分析输出results，最终图figures_final；results_reproduction/reproduction_final为实际独立复现。figures、figures_v2、reproduction为排版迭代记录，不作为交付图。verify.py只读原附件ZIP/XML/Decimal独立核对并写verification.json，不运行模型。描述计算用bundled Python3.12.14/NumPy，bundled无matplotlib；图用现有Anaconda Python3.13/matplotlib3.11.1和C:/Windows/Fonts/simsun.ttc。本机DLL读取在沙箱内受限，限定本脚本的审批执行后成功。

先从源字段形成土地统计、适种/观察矩阵、历史播种结构、107原参数分布和区间，再绘图。源码中全部过滤/去重/求和/排序/对数坐标有明确含义；无标准化、收益排序、销量代理、拟合、优化或模拟。图6仅为减少重复显示合并同作物相同区间，107个源行仍保留。

输出：6张PDF/PNG/SVG。4张正文图（01、03、02、04），2张附图（05、06）。共同主张及图卡以项目report、paper_evidence/data.md和figure_registry.md为准。本目录不另立研究报告。

verification.json记录原附件独立核对及423项保护文件；technical_checks.json记录分析重建、6图PDF/PNG一致及PDF文字颜色/页边界；delivery.json记录最终源码、输入、图、章节哈希及AI视觉验收。此类检查不等于人工复算或模型科学认证。
