from pathlib import Path
import re, json, shutil, hashlib, datetime

project=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=project/'shumo_1/shumo_backup_20260913_003434'
backup=project/'tmp'/('q3_approved_before_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True)
tracked=[src/'main.tex',*sorted((src/'sections').glob('*.tex')),*sorted((src/'tables').glob('*.tex')),*sorted((src/'fig').glob('*'))]
hashes={str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked if p.is_file()}
for rel in ['sections/sec_2_problem_analysis.tex','sections/sec_7_q3.tex','main.pdf']:
    dest=backup/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src/rel,dest)
(backup/'source_hashes.json').write_text(json.dumps(hashes,indent=2),'utf-8')
(project/'tmp/q3_approved_backup_path.txt').write_text(str(backup),'utf-8')
p=src/'sections/sec_7_q3.tex'; s=p.read_text('utf-8')
def replace(old,new):
    global s
    assert old in s,old[:100]
    s=s.replace(old,new,1)
def between(start,end,new):
    global s
    a=s.index(start); b=s.index(end,a)
    s=s[:a]+new.strip()+'\n\n'+s[b:]

between(r'\subsection{日内新信息下的求解思路}',r'\subsection{供需预测与动态安全准备}',r'''
\subsection{日内新信息下的求解思路}

问题三允许在获得新预报后修改尚未执行的订单，但修改本身需要付费。因此，既要判断未来还缺多少电，也要判断是否值得修改订单。当天已发生的负载偏差能够帮助修正后续判断，但短暂波动未必持续，不能将眼前偏差直接用于全天。

针对这些特点，本文比较直接使用官方预报、历史融合和提升树修正三种光伏预测方法，并考察误差准备的作用。官方预报使用简便；历史融合能够结合当天预报与近期发电水平；提升树可以表达更复杂的关系。误差准备则用于缓冲低估缺口后按5倍电价补购的风险。

本文采用\textbf{融合预测与日内校正滚动规划}。负载以同星期近期加权预测为基础，再用当天已发生的偏差修正；光伏由官方预报与历史参考融合得到。更新误差准备后，由线性规划权衡普通购电、改单和紧急购电费用。这样既能利用新信息，也能说明每次调整的依据。
''')
replace(r'=\sum_{j=1}^{4}b_jL_{d-7j,k},\qquad'+ '\n'+r'b_j=',r'=\sum_{j=1}^{4}\gamma_jL_{d-7j,k},\qquad'+'\n'+r'\gamma_j=')
replace('四种历史参照的费用比较见后文。','0.5作为预设周衰减系数参与比较，四种历史参照的费用比较见后文。')
replace('次日的辅助负载曲线仍由零点已知的同星期历史构造，不直接延续当天偏差。','零点不作日内偏差修正。次日的辅助负载预测仍由零点已知的同星期历史构造，不直接延续当天偏差。')
replace('利用过去28天已经兑现的同组预报，求使平方误差最小的融合权重：','记 $\\mathcal I_{d,\\tau,h}$ 为过去28天中相同发布钟点、同一提前量组内已经兑现的样本集合，融合权重取为')
replace(r'\left(\frac{\sum(F-H)(P^{PV}-H)}{\sum(F-H)^2}\right).',r'\left(\frac{\sum_{i\in\mathcal I_{d,\tau,h}}(F_i-H_i)(P^{PV}_i-H_i)}'+ '\n'+r'{\sum_{i\in\mathcal I_{d,\tau,h}}(F_i-H_i)^2}\right).')
replace('官方预报近期较准时，其权重增加；历史参考较可靠时，历史信息的比例提高。\n因此，融合权重随发布时间和预测提前量变化，而不是全年固定不变。','该式选择使历史融合平方误差最小的比例，让两类信息相互补充。融合权重随发布时间和预测提前量变化，而不是全年固定不变。')
between('为平衡两者，本文考察历史上实际净需求超过预测的程度：','每次决策使用此前28天',r'''为平衡两者，沿用第6.3节的净需求误差定义，考察实际缺口超过预测的程度。历史误差按原发布时间的预测计算，反映当时能够形成的供需判断。''')
replace(r'\rho_t=(\widehat L_t-\widehat P^{PV}_t)\Delta t+M_t,\qquad'+'\n'+r'N_t=\max(\rho_t,0),\quad A_t=\max(-\rho_t,0).',r'N_t=(\widehat L_t-\widehat P^{PV}_t)\Delta t+M_t,\qquad'+'\n'+r'n_t=\max(N_t,0),\quad a_t=\max(-N_t,0).')
replace('$N_t$ 为预计需要外网或电池补充的电量，$A_t$ 为预计可用于储能的光伏富余。','$N_t$ 为带符号的净需求，$n_t$ 为预计需要外网或电池补充的电量，$a_t$ 为预计可用于储能的光伏富余。')
replace(r'q_t-x_t+z_t+e_t-u_t=N_t.',r'q_t-x_t+z_t+e_t-u_t=n_t.')
replace('另设 $e_t$ 为预计紧急购电量，$u_t$ 为已订购但预计无法接收的电量。','另设 $e_t$ 为预计紧急购电量，用于比较改单与补购的代价；$u_t$ 为已订购但预计无法接收的电量。')
replace(r'S_t=S_{t-1}+0.9(x_t+y_t)-\frac{z_t}{0.9}.',r'S_t=S_{t-1}+\eta_c(x_t+y_t)-\frac{z_t}{\eta_d},\qquad \eta_c=\eta_d=0.9.')
replace(r'1200&\leq S_t\leq10800,',r'S_{\min}&\leq S_t\leq S_{\max},')
replace(r'0\leq y_t&\leq A_t,\qquad z_t+e_t\leq N_t,',r'0\leq y_t&\leq a_t,\qquad z_t+e_t\leq n_t,')
replace('其中 $P_{\\max}\\Delta t=5000/6\\ \\mathrm{kWh}$，计算时保留精确值。','其中 $S_{\\min}=1200$ kWh、$S_{\\max}=10800$ kWh，$P_{\\max}\\Delta t=5000/6\\ \\mathrm{kWh}$，计算时保留精确值。')
between(r'\subsection{日内滚动求解过程}',r'\subsection{候选方案比较与最终模型选择}',r'''
\subsection{日内滚动求解过程}

\textbf{Step 1：制定零点原计划。}每天零点，读取已有历史、当前库存和官方预报，形成供需预测与准备量，求得并保存当天原始订单。次日的辅助安排仅用于判断当前应保留多少电。

\textbf{Step 2：执行购电与储能安排。}按问题二的实际供电规则运行至下一决策时点。光伏和普通电不足时由电池补充，剩余缺口紧急购买；余电在容量和充电功率允许时储存，并逐时更新实际库存。

\textbf{Step 3：利用新信息调整订单。}在6:00、12:00和18:00，更新负载偏差、光伏融合预测和准备量，从当前实际储电量重新求解。已经执行的订单锁定，未执行部分是否调整由费用权衡决定。随后继续执行Step 2，直至当天结束。

\textbf{Step 4：结算费用并衔接次日。}保留各时段执行前最后确定的订单，按照其相对零点订单的净变化计算调整费用，再加上实际紧急购电费。日末实际余电传递至下一天。

费用评价期为2025年2月1日至12月31日，共334天，起始库存沿用第6.5节的8592.69 kWh。各日连续运行，完整方案每天求解4次，共完成1336次滚动线性规划。
''')
replace('历史融合的总费用最低，说明官方预报与近期历史能够相互补充。','历史融合的普通结算费用下降，虽紧急购电费略有上升，总费用仍最低，说明官方预报与近期历史能够相互补充。')
replace(r'\subsection{全年结果与指定日期分析}',r'\subsection{评价期结果与指定日期分析}')
replace(r'\subsubsection*{（1）全年费用结果}',r'\subsubsection*{（1）费用构成}')
replace('总购电费用为\n\\begin{equation}\n\\boxed{C=13014172.33\\ \\text{元}}.\n\\end{equation}','总购电费用为\\textbf{13014172.33元}。')
replace('安全准备也有代价。全年仍有32.66万kWh普通订单未能接收，\n这部分电虽未使用，却已经付费。因此，不能只以紧急购电少作为方案优劣的标准，\n还要看为此多付出的普通订电费用。','评价期内仍有32.66万kWh普通订单未能接收，这是供需预测误差、已订电量与设备接收能力共同作用的结果。这部分电虽未使用，却已经付费。因此，评价方案时还需兼顾紧急补购与未利用订单的代价。')
replace(r'\subsubsection*{（2）指定日期零点原计划}',r'\subsubsection*{（2）零点原计划与日内调整}')
replace(r'\subsubsection*{（3）日内调整后的购电结果}'+'\n\n','')
replace(r'\subsubsection*{（4）指定日期储能运行}',r'\subsubsection*{（3）储能运行与紧急购电}')
replace(r'\subsubsection*{（5）紧急购电与典型日期分析}'+'\n\n','')
replace('这说明电池里有电，并不等于任何时段都能及时供够。','这说明\\textbf{库存下限和放电功率限制都可能触发紧急补购}，电池里有电并不等于任何时段都能及时供够。')
info_table=re.search(r'\\begin\{table\}\[H\].*?\\label\{tab:q3_info\}.*?\\end\{table\}',s,re.S).group(0)
# Match only the table containing this label, not preceding tables.
info_table=next(t for t in re.findall(r'\\begin\{table\}\[H\].*?\\end\{table\}',s,re.S) if r'\label{tab:q3_info}' in t)
between(r'\subsection{日内新预报的实际费用价值}',r'\subsection{参数灵敏度与模型可信度}',r'''
\subsection{日内新预报的实际价值}

为区分新预报与反馈改单各自的作用，本文在同一套负载预测、准备规则和调度结构下设置三组信息条件，共同从同一实际库存开始连续运行。第一组只在零点订电，全天不改单；第二组允许根据已发生的供需和库存调整，但不读取后发官方预报；第三组在第二组基础上加入后发官方预报。各组的预测误差与准备量均由自身可用信息构造，结果见表~\ref{tab:q3_info}。

'''+info_table+r'''

日内反馈与改单使费用减少50.63万元；在此基础上，新光伏预报又节省\textbf{6.95万元}，降幅约0.53\%。后两组期末库存相同，因此这部分节省不是靠多消耗剩余电量换来的。新预报的价值还体现在以下方面。

\textbf{（1）减少对紧急购电的依赖。}引入后发预报后，紧急购电量由40956.71 kWh降至28627.32 kWh，\textbf{下降30.10\%}；紧急购电费下降27.22\%，发生紧急购电的日期由191天减少至185天。新预报帮助模型提前识别缺口，减少了临时高价补购。

\textbf{（2）减少电量浪费，促进光伏就地利用。}未接收的普通订单由38.83万kWh降至32.66万kWh，\textbf{减少15.88\%}；未利用光伏电量减少3.07\%。这说明新预报能够帮助协调购电与储能，既减少订多却用不上的电量，也让更多光伏用于小区供电，有利于提高可再生能源利用水平，符合绿色低碳发展的方向。

\textbf{（3）以适量调整支出换取更大的购电节省。}虽然引入新预报后调整费增加约6.86万元，但普通订单费和紧急电费分别减少约7.78万元、6.03万元，节省金额超过新增调整支出，最终实现\textbf{6.95万元的净节省}。同时，紧急购电量下降30.10\%，表明这部分调整支出不仅带来了经济回报，也减少了对临时高价补购的依赖。因此，利用新预报及时调整订单，在费用与补购风险之间取得了更有利的平衡。

综上，针对题目“是否需要引入其他时刻的预报制定调整购电策略”的问题，本文的结论是：在题目给定条件下，\textbf{有必要引入6:00、12:00和18:00发布的光伏预报}，作为日内调整购电策略的依据。三组信息对照表明，在已有日内反馈与改单能力的基础上，后发官方预报进一步降低了总费用，减少了紧急购电和未利用电量，具有明确的经济价值与运行价值。具体是否改单、调整多少，则由优化模型结合最新供需判断、储能余量和调整费用确定。
''')
replace('fig/q3_final_validation.pdf','fig/q3_final_quantile.pdf')
replace(r'\includegraphics[width=0.96\textwidth]',r'\includegraphics[width=0.72\textwidth]')
replace(r'\caption{负载参照与误差准备程度的费用比较}',r'\caption{误差准备程度与购电费用的关系}')
start=s.index('因此，0.60体现的是本题成本条件下的取舍')
s=s[:start]+r'''因此，\textbf{适量准备的作用是平衡两类支出，而非一味压低紧急购电}。虽然上述比较不代表0.60是所有连续取值中的全局最优，但它已是本年度已测试取值中的较优选择，能够较好地兼顾准备不足与订电过量的代价。

计算后，逐10分钟核对供需平衡、库存衔接、充放电功率和已执行订单锁定，并由实际订单与紧急购电量重新计算账单。各项约束得到满足，费用复算差异小于0.01元。上述检验表明，方案在本文设定的信息与结算条件下能够连续执行，储能运行符合设备限制，购电费用可由实际订单逐项核算。
'''
assert '曲线' not in s
original=p.read_text('utf-8')
for table in re.findall(r'\\begin\{table\}\[H\].*?\\end\{table\}',original,re.S): assert table in s,'Table altered'
p.write_text(s,'utf-8')
analysis=src/'sections/sec_2_problem_analysis.tex'
a=analysis.read_text('utf-8')
assert 'fig/model.pdf' not in a
a+=r'''

四问的模型组成及递进关系如图~\ref{fig:overall_model_framework}所示。
\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{fig/model.pdf}
\caption{四问整体模型框架}
\label{fig:overall_model_framework}
\end{figure}
'''
analysis.write_text(a,'utf-8')
assert (src/'fig/model.pdf').read_bytes()==(project/'paper/figures/model-framework-v4/四问整体模型框架图.pdf').read_bytes()
print('Approved Q3 and framework inserted. Backup: '+str(backup))
