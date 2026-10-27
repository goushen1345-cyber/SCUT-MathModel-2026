from pathlib import Path
import re, shutil, hashlib, json
from datetime import datetime

P=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
base=P/'shumo_1/shumo_backup_20260913_003434'
src=base/'压缩版'; dst=base/'图像压缩版'
assert not dst.exists(), 'Do not overwrite an existing image edition'
audit=P/'tmp'/('image_compact_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
audit.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected={str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file() and ('图像压缩版' not in p.parts)}
(audit/'protected_hashes.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2),'utf-8')
shutil.copytree(src,dst)
(P/'tmp/image_compact_audit_path.txt').write_text(str(audit),'utf-8')
changes=[]
def read(n):return (dst/'sections'/n).read_text('utf-8')
def write(n,s): (dst/'sections'/n).write_text(s,'utf-8')
def removefig(s,label):
    pat=r'\\begin\{figure\}.*?\\end\{figure\}'
    found=[]
    def edit(m):
        if '\\label{'+label+'}' in m[0]:found.append(label);return ''
        return m[0]
    s=re.sub(pat,edit,s,flags=re.S)
    assert len(found)==1,label
    changes.append('Removed figure '+label)
    return s
def replace(s,a,b):
    assert a in s, a[:100]
    return s.replace(a,b,1)

n='sec_1_problem_review.tex';s=read(n)
s=replace(s,'width=0.9\\textwidth','width=0.78\\textwidth')
write(n,s)

n='sec_4_data_preprocessing.tex';s=read(n)
for lab in ['fig:tsxfx_1','fig:tsxfx_2','fig:tsxfx_3','fig:tsxfx_4']:s=removefig(s,lab)
s=replace(s,r'图~\ref{fig:tsxfx_1}显示，代表日午间光伏能够覆盖负载并产生富余，', '代表日午间光伏能够覆盖负载并产生富余，')
s=replace(s,r'图~\ref{fig:tsxfx_2}显示，夏季负载较高，',r'图~\ref{fig:data_compact}(a)显示，夏季负载较高，')
s=replace(s,r'图~\ref{fig:tsxfx_3}显示，相同时刻在不同日期的电价也存在较大差异。', '相同时刻在不同日期的电价也存在较大差异。')
s=replace(s,'按实际星期分组后，周五、周六的平均负载',r'图~\ref{fig:data_compact}(b)显示，按实际星期分组后，周五、周六的平均负载')
s=replace(s,'下降约69\\%，如图~\\ref{fig:tsxfx_4}所示。','下降约69\\%。')
s=replace(s,'预报提前时间越长，平均绝对误差总体越大。',r'预报提前时间越长，平均绝对误差总体越大，如图~\ref{fig:forecast_compact}所示。')
s=replace(s,r'\subsubsection*{（2）负载与光伏的年内变化不同步}',r'''\subsubsection*{（2）负载与光伏的年内变化不同步}
\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{fig/data_compact.pdf}
\caption{负载与光伏的季节差异及负载的星期规律}
\label{fig:data_compact}
\end{figure}''')
s=replace(s,r'\subsubsection*{（4）日内新预报提高预测精度，为滚动调整提供依据}',r'''\subsubsection*{（4）日内新预报提高预测精度，为滚动调整提供依据}
\begin{figure}[htbp]
\centering
\includegraphics[width=0.78\textwidth]{fig/forecast_compact.pdf}
\caption{光伏预报提前时间与平均绝对误差}
\label{fig:forecast_compact}
\end{figure}''')
write(n,s)

n='sec_5_q1.tex';s=read(n)
# Keep all model equations, optimality reasoning, and prescribed outputs.
s=replace(s,r'\includegraphics[width=0.88\textwidth]{fig/q1_daily_dispatch.pdf}',r'\includegraphics[width=0.73\textwidth]{fig/q1_daily_dispatch.pdf}')
pat=r'\\begin\{table\}.*?\\end\{table\}'
s=re.sub(pat,lambda m:'' if r'\label{tab:q1_sensitivity}' in m[0] else m[0],s,flags=re.S)
s=replace(s,r'进一步取1200、6000和10800 kWh三种初始电量，并分别要求日末恢复至对应初值，重新优化，结果见表~\ref{tab:q1_sensitivity}。',r'进一步取1200、6000和10800 kWh三种初始电量，并分别要求日末恢复至对应初值。重新优化后的费用依次为35199.30、35126.85和35409.75元，前后两种状态较主方案分别增加0.21\%和0.81\%。')
write(n,s)

n='sec_6_q2.tex';s=read(n)
s=removefig(s,'fig:q2_monthly_cost');s=removefig(s,'fig:q2_specified_days')
s=replace(s,r'图~\ref{fig:q2_monthly_cost}显示，11个月的费用均低于等权准备方案，', '按月比较，11个月的费用均低于等权准备方案，')
s=replace(s,r'图~\ref{fig:q2_specified_days}中，3月20日储能补足了大部分订单与实际需求之间的缺口。', '以3月20日为例，储能补足了大部分订单与实际需求之间的缺口。')
s=replace(s,r'\includegraphics[width=0.95\textwidth]{fig/sensitivity.png}',r'\includegraphics[width=0.82\textwidth]{fig/sensitivity.png}')
write(n,s)

n='sec_7_q3.tex';s=read(n)
s=replace(s,r'\includegraphics[width=0.98\textwidth]{fig/q3_final_days.pdf}',r'\includegraphics[width=0.88\textwidth]{fig/q3_final_days.pdf}')
s=replace(s,r'\includegraphics[width=0.72\textwidth]{fig/q3_final_quantile.pdf}',r'\includegraphics[width=0.64\textwidth]{fig/q3_final_quantile.pdf}')
# Only condense explanations already established in Q2; retain newly introduced mechanisms.
s=replace(s,'''平均预测较准，仍可能在关键时段低估缺口。
少准备的电量可能需要按5倍电价补购，准备过多又可能付费后用不完。
为平衡两者，沿用第6.1节的净需求误差定义，考察实际缺口超过预测的程度。历史误差按原发布时间的预测计算，反映当时能够形成的供需判断。''','''沿用第6.1节的净需求误差与加权分位方法，为可能低估的用电缺口设置准备。历史误差按原发布时间的预测计算，保证它反映当时能够形成的供需判断。''')
s=replace(s,'''历史误差采用 $\\omega_j\\propto0.7^{a_j}$ 的权重，$a_j$ 表示相隔天数。
每早一天权重乘以0.7，约两天降至一半，因而准备量主要跟随近期供需变化。
28天窗口保留四周信息，3小时分组则将每个6小时更新区间分成前后两段。''',r'''历史误差仍按 $\omega_j\propto0.7^{a_j}$ 加权，$a_j$ 为相隔天数。28天窗口保留四周信息，3小时分组将每个6小时更新区间分成前后两段，使准备量兼顾近期变化和日内差异。''')
s=replace(s,'''准备量只改变规划中的供需判断；实际运行仍按真实负载与光伏计算。

沿用前文普通订单 $q_t$、外网充电 $x_t$、光伏充电 $y_t$、
电池对外放电 $z_t$ 和内部储电量 $S_t$。
另设 $e_t$ 为预计紧急购电量，用于比较改单与补购的代价；$u_t$ 为已订购但预计无法接收的电量。
除 $S_t$ 为电池内部电量外，其余电量均在电池外侧计量。''',r'''准备量只改变规划中的供需判断。沿用前文的订单、充放电与库存变量，另设预计紧急购电量 $e_t$ 和已订购但预计无法接收的电量 $u_t$，用于权衡改单、补购与订单过量的代价。''')
write(n,s)

n='sec_8_q4.tex';s=read(n);s=removefig(s,'fig:q4_model_test')
s=replace(s,'前者影响价格预测的细致程度，后者决定多订普通电与承担紧急补购之间的取舍，结果见图~\\ref{fig:q4_model_test}。','前者影响价格预测的细致程度，后者决定多订普通电与承担紧急补购之间的取舍。')
s=replace(s,r'图\ref{fig:q4_model_test}(a)以15叶模型为参照。','以15叶模型为参照，比较7叶、15叶和31叶三档设置。')
s=replace(s,r'图\ref{fig:q4_model_test}(b)比较0.40至0.80五档准备分位。','比较0.40至0.80五档准备分位。')
s=replace(s,'''已经执行的订单不再修改。同一时段经过多次调整时，只按最终订单与零点原计划之间的净变化结算一次。规划使用预测电价；最终普通购电费、调整费和紧急购电费均按对应执行时段的实际电价结算。

两条分支的供需平衡、储电递推、容量与功率约束及实际供电规则均沿用前文。实际日末储电量继续传递至次日，不再要求每日首尾相等。''','''订单锁定、净调整计费和跨日库存衔接均沿用前文。区别在于规划使用预测电价，最终普通购电费、调整费和紧急购电费均按对应执行时段的实际电价结算。''')
write(n,s)

# Let main-text figures move within the current section to avoid large unused page bottoms.
# Appendices are copied verbatim and keep their fixed placement.
for f in (dst/'sections').glob('sec_*.tex'):
    s=f.read_text('utf-8').replace(r'\begin{figure}[H]',r'\begin{figure}[!htbp]')
    f.write_text(s,'utf-8')
main=(dst/'main.tex').read_text('utf-8')
main=main.replace(r'\usepackage{float}',r'\usepackage{float}'+'\n'+r'\usepackage[section]{placeins}')
main=main.replace(r'\setlength{\parskip}{0pt}',r'''\setlength{\parskip}{0pt}
% Keep the original body type, line spacing and page margins; trim only float gaps.
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\intextsep}{8pt plus 2pt minus 2pt}
\setlength{\floatsep}{8pt plus 2pt minus 2pt}''')
(dst/'main.tex').write_text(main,'utf-8')
(audit/'changes.json').write_text(json.dumps({'scope':'image-led compression; original and compressed editions unchanged; appendix excluded per user and preserved','removed_figures':changes,'source':str(dst)},ensure_ascii=False,indent=2),'utf-8')
print(dst);print(audit)
