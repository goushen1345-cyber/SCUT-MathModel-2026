# AUDIT-REVISIT-v1只读诊断证据

授权U029：只读审计，预算30分钟，完成处理建议和影响清单后停G1；不处理数据、不做EDA、不建模。主报告位于`../../report.md`对应版本区，本目录不再维护独立研究报告。

| 文件 | 用途 |
|---|---|
| audit_readonly.py | openpyxl读取原附件，做键、原面积、类型/价格区间、模板与历史源字段诊断 |
| verify_diagnostics.py | 不使用openpyxl，独立ZIP/XML复核关键面积、端点、模板、原文件版本和销量未知字段 |
| inventory.json | 原文件/工作表/有效范围/表头/合并区域与读取告警 |
| diagnostic_details.json | 每个空白/边界空白的坐标、历史参数匹配、原面积核对、价格区间与模板结构 |
| diagnostics.json | 本次实际检查汇总，包含12个无历史种植的合法组合 |
| independent_checks.json | 独立路径检查及销售文字定位结果 |
| protected_before.json | 原始/冻结/既有文稿和图形文件的起始哈希 |
| execution.json、delivery_check.json | 代码版本、范围、时间、最终保护/状态核对 |
| problem_source.txt | 本轮只读提取的原题全文，来源原PDF，不是研究结果 |

仅审计诊断，不是清洗后模型输入；输出中的源坐标/原值/键用于追溯，不授权其作为正式处理结果。未计算任何产量、收益、正常销量代理或价格中点；旧表的相应列未参与数值对照。

本次实际命令（仓库根目录，使用bundled Python 3.12.14）：

```powershell
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' projects/2024-C/audit/AUDIT-REVISIT-v1/audit_readonly.py
& 'C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' projects/2024-C/audit/AUDIT-REVISIT-v1/verify_diagnostics.py
```

audit_readonly.py会拒绝覆盖既有诊断，也检查DATA_PLAN/U029及批准时间窗口。现在已经完成并停G1，不应直接重新执行；以后如获准复核，先为新的授权/输入创建独立版本并保留本次证据。脚本没有任何原工作簿保存或模型调用。

匹配中的strip和合并锚点读取仅在内存解释标签；没有写回数据。适种键依据附件1 E2的类型/例外作诊断，不输出展开的参数数据集。独立XML核对采用不同解析路径，但仍由同一AI实施，不是用户人工复算。

读取工具产生的页眉页脚解析警告已记录；本次检查针对单元格、原XML与表结构，没有宣称完成全部工作簿排版检查。类型/端点正确及无面积超限不证明真实市场、空间轮作或旧模型整体正确。
