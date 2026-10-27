from pathlib import Path
from datetime import datetime
import shutil,json,hashlib,re
P=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
b=P/'shumo_1/shumo_backup_20260913_003434';s=b/'图像压缩版'
a=P/'tmp'/('solution_labels_'+datetime.now().strftime('%Y%m%d_%H%M%S'));a.mkdir()
shutil.copytree(s,a/'before_source')
shutil.copy2(b/'main(图像压缩版）.pdf',a/'before.pdf')
protected={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest() for p in b.rglob('*') if p.is_file() and s not in p.parents and p.name!='main(图像压缩版）.pdf'}
(a/'protected_hashes.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2),'utf-8')
(P/'tmp/image_compact_audit_path.txt').write_text(str(a),'utf-8')
def edit(name,pairs):
 p=s/'sections'/name;t=p.read_text('utf-8')
 for x,y in pairs:
  assert t.count(x)==1,(name,x[:80],t.count(x))
  t=t.replace(x,y,1)
 p.write_text(t,'utf-8')

edit('sec_5_q1.tex',[
('光伏充电不能超过富余量，电池放电不能超过负载缺口；充放电还应满足设备功率限制：',r'\noindent\textbf{约束1：电量分配与供电限制。}光伏充电不超过富余量，电池放电不超过负载缺口：'),
(r'\begin{equation}'+'\n'+r'x_k+y_k\le P_{\max}\Delta t,',r'\noindent\textbf{约束2：充放电功率限制。}各时段充放电不超过设备允许功率：'+'\n'+r'\begin{equation}'+'\n'+r'x_k+y_k\le P_{\max}\Delta t,'),
('考虑充、放电各90\\%的效率，内部储电量满足',r'\noindent\textbf{约束3：储电量递推。}考虑充、放电各90\%的效率，内部储电量满足'),
(r'\begin{equation}'+'\n'+r'S_{\min}\le S_k\le S_{\max}',r'\noindent\textbf{约束4：储电量上下限。}内部储电量保持在允许范围内：'+'\n'+r'\begin{equation}'+'\n'+r'S_{\min}\le S_k\le S_{\max}'),
('日初与日末均取6000 kWh：',r'\noindent\textbf{约束5：日初与日末电量相等。}两者均取6000 kWh：'),
('求解时，先按时间标签整理数据并转换电量，再计算光伏直供后的缺口和富余量，代入目标函数及约束，得到各时段购电、充放电和储电安排。结果按原模板的时间标签对应填回。',r'''\noindent\textbf{步骤1：整理时段供需。}按时间标签转换电量，计算光伏直供后的负载缺口和富余量。

\noindent\textbf{步骤2：求解购电与储能安排。}将时段供需和电价代入模型，求得购电、充放电和储电量。

\noindent\textbf{步骤3：核对并汇总结果。}复核供需、储能约束和费用，按模板时间标签填回结果。''')])

edit('sec_6_q2.tex',[
('其中，$n_t$ 为计划缺口，$a_t$ 为扣除准备后的预计余量。普通订单满足',r'''其中，$n_t$ 为计划缺口，$a_t$ 为扣除准备后的预计余量。

\noindent\textbf{约束1：计划供需平衡。}普通订单满足'''),
('储电递推、容量和充放电功率约束沿用第5.1节，其中光伏充电上限改为预计余量 $a_t$，放电上限采用计划缺口 $n_t$。初始库存取当天零点实际储电量 $S_0=S_{d,0}$，日末余电连续传递至次日，不再要求每日首尾相等。',r'''\noindent\textbf{约束2：储能运行限制。}功率、储电递推与容量限制沿用式\eqref{eq:q1_power_constraint}—\eqref{eq:q1_soc_bound}，光伏充电上限改为预计余量 $a_t$，放电上限采用计划缺口 $n_t$。

\noindent\textbf{约束3：初始库存与跨日衔接。}取 $S_0=S_{d,0}$，日末实际余电传递至次日，不再要求每日首尾相等。'''),
('预测与准备量确定后，采用HiGHS求解当天订单。日内订单保持不变，储能根据实际供需充放电。',r'''\noindent\textbf{步骤1：形成供需预测与准备量。}每天零点，按第6.1节处理已有历史，形成未来48小时的供需判断。

\noindent\textbf{步骤2：求解跨日计划。}从当前实际库存开始，采用HiGHS求解，只固定当天订单。

\noindent\textbf{步骤3：按实际供需执行。}日内订单保持不变，储能根据实际供需充放电。'''),
('未能使用或储存的普通订单仍需付费，未利用光伏不计售电收益。因此，每日实际费用及跨日衔接为',r'\noindent\textbf{步骤4：结算并衔接次日。}未能使用或储存的普通订单仍需付费，未利用光伏不计售电收益。每日实际费用及跨日衔接为')])

edit('sec_7_q3.tex',[
('光伏优先直接满足负载后，其余供需满足',r'\noindent\textbf{约束1：计划供需平衡。}光伏优先直接满足负载后，其余供需满足'),
('储电递推、容量和充放电功率约束沿用第5.1节，并满足',r'\noindent\textbf{约束2：储能与供电范围限制。}功率、储电递推与容量限制沿用式\eqref{eq:q1_power_constraint}—\eqref{eq:q1_soc_bound}，另满足'),
('光伏充电不能超过预计富余，电池放电和紧急补购也不超过预计缺口。每次规划从当前实际库存开始，日末余电连续传递至次日，不要求每日首尾相等。',r'''光伏充电不超过预计富余，电池放电和紧急补购不超过预计缺口。

\noindent\textbf{约束3：库存衔接与订单锁定。}每次从实际库存开始规划，日末余电传递至次日；已经执行的订单不再修改，仅优化剩余时段。'''),
('其中，对 $t\\in\\mathcal A_{\\tau}$ 有',r'\noindent\textbf{辅助约束：调整量的线性化。}对 $t\in\mathcal A_{\tau}$，令'),
(r'\textbf{Step 1：',r'\noindent\textbf{步骤1：'),
(r'\textbf{Step 2：',r'\noindent\textbf{步骤2：'),
(r'\textbf{Step 3：',r'\noindent\textbf{步骤3：'),
(r'\textbf{Step 4：',r'\noindent\textbf{步骤4：'),
('随后继续执行Step 2，直至当天结束。','随后继续执行步骤2，直至当天结束。')])

edit('sec_8_q4.tex',[
('订单锁定、净调整计费和跨日库存衔接均沿用前文。区别在于规划使用预测电价，最终普通购电费、调整费和紧急购电费均按对应执行时段的实际电价结算。',r'''\noindent\textbf{约束沿用。}问题四-2沿用第6.2节的三项约束，问题四-3沿用第7.2节的三项约束及调整量线性化方法。规划使用预测电价，普通购电、调整和紧急购电均按执行时段的实际电价结算。'''),
('给定供需预测和价格预测后，两条分支均为线性规划，采用HiGHS求解。评价期与共同起始库存沿用第6.3节，按时间顺序连续运行334天。每次决策读取真实当前储电量，求得订单后执行至下一决策时点，再更新供需与储电状态。',r'''评价期与共同起始库存沿用第6.3节，两条分支按时间顺序连续运行334天。

\noindent\textbf{步骤1：更新电价预测。}按第8.1节更新价格模型及输入，得到决策时可用的未来价格判断。

\noindent\textbf{步骤2：分别求解两条分支。}从当前实际库存开始，调用HiGHS求解。问题四-2仅在零点订电；问题四-3在零点订电，并在6:00、12:00和18:00更新剩余订单。

\noindent\textbf{步骤3：实际执行与结算。}按对应分支的供电规则执行，以实际价格结算各项费用，并将日末实际余电传递至次日。''')])

# Formatting only: all mathematical expressions, result tables and figure assets remain exact.
checks={}
pat=r'\\begin\{(equation|align)\}.*?\\end\{\1\}|\\\[.*?\\\]'
for f in (s/'sections').glob('*.tex'):
 old=(a/'before_source/sections'/f.name).read_text('utf-8');new=f.read_text('utf-8')
 assert [m[0] for m in re.finditer(pat,old,re.S)]==[m[0] for m in re.finditer(pat,new,re.S)],f.name
 assert re.findall(r'\\begin\{tabular\}.*?\\end\{tabular\}',old,re.S)==re.findall(r'\\begin\{tabular\}.*?\\end\{tabular\}',new,re.S),f.name
 checks[f.name]={'steps':re.findall(r'\\textbf\{步骤(\d)：',new),'constraints':re.findall(r'\\textbf\{约束(\d)：',new)}
(a/'changes.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),'utf-8')
print(a)
