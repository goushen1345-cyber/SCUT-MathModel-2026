# 问题一验证和结果整理

授权Q1-CLOSE-030，计划Q1-close-plan-v1。主方案是原compare-v1的6000首尾LP，不修改旧实验。仅新增1200、10800两起点求解，分别要求首尾相等。

最终表格：deliverables/result1.xlsx。保持原模板两表/标签，填144段购电、6组4小时充放和2个首尾电量。原始模板只读。显示两位小数，底层保留全精度；没有上传、冻结或跨问。

原始结果：outputs/schedules、两份certificate、sensitivity.csv、summary.json。题给展示数据：table1_selected_purchase.csv、table2_four_hour.csv。verification.json是独立来源、能量和最优性核验；workbook_verification.json是保存后XLSX回读、时间映射和样式核对。previews含实际查看过的原模板及最终两表/零点尾部。

人话发现及论文思路已并入../../report.md第13—14节，论文证据见项目paper_evidence/Q1.md。当前只交论文思路，没有起草正文。

## 复现

在仓库根目录运行下列命令，先选择本运行目录的独立副本以保留既有结果。close.py拒绝覆盖已存在outputs，不能为重复核验重新求解。

1. `E:/Anaconda/python.exe projects/2026-C/questions/Q1/runs/20260911-close-v1/close.py`：仅2次新LP，引用compare-v1的模型实现；numpy2.5.1、scipy1.18.0。首次受限DLL加载失败未求解，自动工具审核允许后完成。
2. 捆绑Python执行`verify_close.py`：标准库Decimal独立核验，无调度代码导入、无新求解。
3. 捆绑Node执行`workbook.mjs inspect`查看原模板；执行`workbook.mjs export`生成正式结果。依赖@oai/artifact-tool，由node_modules目录连接已配置捆绑依赖；不安装包。导出前按电子表格工具要求运行一次操作标记。
4. 捆绑Python执行`verify_workbook.py`：独立XML取值及openpyxl只读核对结构/有效样式，不用openpyxl写表。必须再查看previews中的最终PNG。未经桌面Excel交互核验，不作该声明。

两个起点都只变初始/终止库存，其他条件相同；三起点结果不能冒充连续区间扫描、固定策略鲁棒性或全年预测风险实验。所有核验由AI执行，未代替人类核验。源文件/产物哈希见delivery_manifest.json，清单仅用于追溯，不是模型冻结。
