# 问题四局部论文与通俗讲解

## 直接阅读和修改

- `问题四的模型建立与求解.pdf`：问题四独立章节，8页，3幅代码生成图，含建立、求解、比较、结果与验证。
- `问题四的模型建立与求解.tex`：**所有论文正文都在这个文件中**，不是只有引用命令的入口。只有指定日期结果表单独引用 `tables/selected_days.tex`。
- 通俗报告：项目的 `paper_evidence/问题四模型与论文详细讲解报告.md`。按实际研究顺序解释电价规律、候选、岭回归动机、树模型、调度、计费、深化和可信程度。
- `figures/`：三图均有PNG和矢量PDF。图1价格轮廓，图2逐月正负节费，图3树复杂度与日内价格更新。
- `tables/指定日期汇总.csv`：只汇总保存结果，不是正式result4工作簿。

## 本稿依据与状态

用户本轮明确要求详细讲解并写论文，按cumcm-paper-builder局部起草执行。采用Q4-2当前31叶提升树与Q4-3完整岭回归；后者继承最新Q3的0.60分位、3小时分组，不使用早期0.65版。正式期为2025-02-01至12-31，共334天，统一初始库存8592.693560925925 kWh。

初次比较来源：`questions/Q4/runs/20260912-three-candidates-v1/outputs/common_start/`。深化、反例和独立核算来源：`questions/Q4/runs/20260912-selected-deepening-v1/`。来源文件、图形指纹见 `source_manifest.json`，排版输入及最终PDF指纹见 `build/record.json`。

本轮没有新训练、购电求解、参数搜索、正式结果表填写、模型冻结或研究状态转换。正文仍为团队待审稿。论文仅展示四个指定日期的摘要，完整144段计划、充放电起止明细与紧急时段清单留在原始研究输出；正式result4及全篇提交材料需另行整理，不能将本稿摘要视为完整提交。

价格完全预知参照仅固定当前供需与控制结构作比较，并非理论下界。超出2025年数据范围的年末辅助价格保留原预测。残差式正则检验不能被写成完整岭回归的选参依据；日内更新对照差额不能相加；当前数据不构成独立跨年泛化。

## 复现

在项目仓库根目录运行以下命令，输出仅写入本稿目录，不改研究结果：

```powershell
& 'E:/Anaconda/python.exe' 'projects/2026-C/paper/q4_manuscript_v1/prepare.py'
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'projects/2026-C/paper/q4_manuscript_v1/build.py'
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'projects/2026-C/paper/q4_manuscript_v1/check_artifacts.py'
```

图形使用已安装Matplotlib、SimSun；排版使用XeLaTeX与xdvipdfmx，Poppler逐页渲染。普通沙箱阻止了已有运行环境的启动，本轮通过工具权限运行同一套已安装环境，未安装软件或改安全设置。pandas提示可选numexpr版本偏旧，未影响此次保存结果的读取与绘图。

人工复核重点：两条分支选择的经济折中、已确认计费假设与正文一致性、全篇符号和图表编号衔接。AI核算和逐页查看不代表人工核验。经典方法文献用于方法归属，不引用当届外部解法；最终整合时再按全篇统一编号并核验参考文献与赛事AI声明。
