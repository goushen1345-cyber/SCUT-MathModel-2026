# 整理后的来源数据（prepared-v1）

按已批准的最小格式整理方案生成，当前是待用户确认的候选版本。
保留全部原始数值、来源位置和发布版本，没有训练、插值、能量换算或填写购电结果。

| 文件 | 每行表示什么 | 行数 | 数值单位 |
|---|---|---:|---|
| day_reference.csv | 附件1代表日的一个原始时间标签 | 144 | 功率kW；电价元/kWh |
| actual_power.csv | 一个来源日期和原时间标签的实际负载及光伏 | 52560 | kW |
| actual_price.csv | 一个来源日期和原时间标签的实际价格 | 52560 | 元/kWh |
| pv_forecasts.csv | 一次发布针对一个未来整点的光伏预报 | 35040 | kW |

## 时间字段

source_date保留原表归属日；代表日没有日历日期，不假造日期。
source_minute为距离归属日零点的分钟数：0:10对应10，0:00+1对应1440。
source_time_label保留原单元格值的文字表示：Excel时间转ISO文字，原文本不改；source_time_type保留原类型。
这只是来源标签，不说明功率代表前一段、后一段或平均值，不能直接把它当作已确认的购电区间。
CSV保留日期和时间为明确文字、分钟数为整数。不要覆盖CSV后再声称原值未变。

## 预报字段

release_datetime是发布时刻；lead_hours为1—24；target_datetime等于发布时刻加提前小时数。
同一目标时刻的不同发布版本全部保留，不能按目标时刻去重或用较晚发布值覆盖较早发布。
date_inherited=1表示原行日期空白，来自同组首行；原行日期及组首单元格都保留。
has_actual_target_label只表示目标标签是否在附件2中存在，不代表当时可提前获知其实际值。
全年最后实际标签是2025-12-31的0:00+1，即2026-01-01 00:00；36条预报晚于此时刻，仅标注而未删除。

## 信息身份与单位

actual_power是实际观测；actual_price是实际价格，在Q4中不可提前知道未来部分。
day_reference来自附件1，其负载/预测用于Q1和已确认的Q2首日启动参考；其电价用于固定日曲线场景。
pv_forecasts来自附件3，仅在相应发布时刻起可用，不能用于未经授权的Q2/Q4-2预报输入。
CSV本身不强制这些权限，后续研究代码还需落实时间切片。
功率仍为kW，价格仍为元/kWh；没有得到区间能量kWh，未填补数值、裁剪、平滑、标准化或插值。

## 数值及来源

数值列直接保存XLSX内部的数值文本，没有按显示小数位四舍五入；重读时按数值解析。
source_id在manifest.json的sources中映射到原文件与工作表。
所有*_cell列均为原工作表单元格地址；实际功率的load_/pv_前缀分别指两张原表。
source_date_label/type保留原日期值表示及类型；source_row_date_label/type保留预报当前行的原日期空白。
source_release_label/type保留预报发布时间的原值表示及类型。
slot_index仅是附件1原行顺序索引，不是新定义的物理区间。

manifest.json记录文件哈希、来源身份、行数、字段、生成脚本和授权。
逐值核对结果另存项目audit/prepared_v1_verification.json，不是人工核验或数据冻结。

## 复现

在仓库根目录使用Python运行：
python -X utf8 projects/2026-C/scripts/prepare_source_tables.py --output tmp/prepared-v1-reproduction
只允许新目录；脚本拒绝覆盖已有输出或写入原始材料目录。
核验命令：python -X utf8 projects/2026-C/scripts/verify_prepared_tables.py
