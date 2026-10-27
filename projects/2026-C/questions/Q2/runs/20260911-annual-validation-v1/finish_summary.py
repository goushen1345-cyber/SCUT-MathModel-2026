"""Describe completed results without changing selected research outputs."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;D=R/'delivery_data'
summary=json.loads((D/'summary.json').read_text(encoding='utf-8'));sup=pd.read_csv(R/'supplement/comparison.csv').set_index('variant');base=pd.read_csv(R/'annual/comparison.csv').set_index('variant')
main=summary['total_official_cost'];equal=float(sup.loc['equal-step-cdf','total_cost']);old=float(base.loc['T4','total_cost'])
summary.update(actual_research_lp=8156,attribution={'equal_step_cdf_cost':equal,'quantile_convention_saving':old-equal,'recency_weights_saving_after_same_quantile_convention':equal-main,'fraction_of_total_saving_due_convention':(old-equal)/(old-main)},final_model_sensitivity={k:float(v) for k,v in sup.total_cost.items()})
paired=pd.read_csv(D/'paired_days.csv');summary['largest_improvement_day']=paired.loc[paired.saving.idxmax()].to_dict();summary['largest_deterioration_day']=paired.loc[paired.saving.idxmin()].to_dict()
diagnostics={}
for name,file in [('selected48',R/'refinement/schedules/sensitivity-error-decay70.npz'),('selected24',R/'supplement/schedules/selected-horizon24.npz')]:
 z=np.load(file);ix={k:i for i,k in enumerate(z['actual_columns'])};a=z['actual'];soc=a[:,:,ix['storage_end_kwh']];em=a[:,:,ix['emergency_kwh']];dis=a[:,:,ix['discharge_kwh']]
 diagnostics[name]={'mean_end_of_day_kwh':float(soc[:,-1].mean()),'last_end_kwh':float(soc[-1,-1]),'near_minimum_slots':int((soc<1200+1e-6).sum()),'emergency_at_discharge_power_limit_slots':int(((em>1e-6)&(dis>5000/6-1e-6)).sum()),'emergency_at_minimum_inventory_slots':int(((em>1e-6)&(soc<1200+1e-6)).sum()),'emergency_slots':int((em>1e-6).sum())}
summary['horizon_diagnostics']=diagnostics
summary['validation_scope_note']='Original4 yearly comparison;15 fixed sensitivities;Jan selection of decay and2 full-year refinements;5 final-model controls. Family choice used annual diagnosis, no untouched-test claim;48h is retained with cost and risk tradeoffs disclosed.'
(D/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'deliverables/result2_填写说明.md').write_text('''# result2 填写说明

本文件与 result2.xlsx 配套；原始模板未改。本次结果为“分别历史预测＋近期加权误差余量＋线性规划”，尚未由用户冻结。

- 全部输出覆盖2025年2月1日至12月31日334天；1月连续初始化另有运行明细。2月1日初始储电量8592.69356093 kWh，来自1月连续运行，不是重新设置6000。
- 计划购电量：每行是一个自然日。B至EN为00:10至23:50起始的143个10分钟区间，EO是该行日期00:00—00:10。输出EO表头改为0:00-0:10，以落实已确认的循环列顺序；原模板带+1的标签保留在原始文件中。EN仍表示本日23:50至次日00:00。
- 计划购电量表的全天购电量与全天购电费分别是零点普通订单总量和普通订单费用。未实际利用的普通订单也计费。紧急电量列在紧急购电量表中；普通费＋五倍电价紧急费才是当天实际总费，不能只读取计划表费用列作为问题二总费用。
- 充放电量按一天六个4小时区间汇总实际执行量，充电包括光伏充电和外网充电，充放电量均在电池外部计量；0:00/24:00储电量在电池内部计量。某4小时段同时有充电量和放电量，是不同10分钟区间发生，所有10分钟段均未同时充放。
- 紧急购电量按同一天连续10分钟缺口合并；跨日切开，便于与自然日对应。无紧急购电的日期写明“无紧急购电”、电量0；共439行，其中261个正购电事件、178个无事件日。
- 数值保留完整精度，Excel仅显示两位小数。不可把显示数值重新累加或再次当作求解输入造成舍入差异。
- 指定日期3月20日、6月21日、9月23日、12月21日的论文表1、表2、表3数据分别在 ../delivery_data/specified_table1.csv、specified_table2.csv、specified_table3.csv。表1支撑数据同时给出普通/紧急/合计量及费用，便于按正文口径展示；它们是结果数据，尚未排成论文。

官方要求区间普通费用12979560.57元、紧急费用604250.27元，合计13583810.84元。公共1月费用2125934.78元，含该初始化过程的365天总费用15709745.62元。两个范围不可混写。
''',encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['attribution','horizon_diagnostics','largest_improvement_day','largest_deterioration_day']},ensure_ascii=False),flush=True)
