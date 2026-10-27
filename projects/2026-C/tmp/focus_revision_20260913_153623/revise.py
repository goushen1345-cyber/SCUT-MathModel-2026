from pathlib import Path
import re, json, hashlib, difflib

root = Path(r'E:/Projects/SCUT-MathModel-2026/projects/2026-C/shumo_1/shumo_backup_20260913_003434/图像压缩版')
audit = Path(__file__).parent
oldroot = audit / 'source_before'
sections = root / 'sections'
changes = {}

def read(name):
    p = sections / name
    assert p.read_bytes() == (oldroot / 'sections' / name).read_bytes(), f'Concurrent change: {name}'
    return p.read_text(encoding='utf-8-sig')

def replace(s, a, b):
    assert s.count(a) == 1, (a[:90], s.count(a))
    return s.replace(a, b, 1)

def keep(name, s):
    changes[name] = s

name = 'sec_0_abstract.tex'
s = read(name)
start = s.index(r'\textbf{针对问题一}')
end = s.index(r'\end{abstract}')
s = s[:start] + r'''\textbf{针对问题一}，采用电量流线性规划，在日初与日末储电量相等的条件下统筹全天购电与充放电，将有限储能留给更高价的时段。代表日最低购电费用为\textbf{35126.85元}，较峰谷策略降低8.23\%，表明全天统筹能够改善仅按价格门槛安排储能的效果。

\textbf{针对问题二}，将\textbf{近期加权准备与跨日线性规划}相结合。负载与光伏分别利用星期规律和近期历史预测，再根据近期缺口误差设置准备，平衡提前订电与五倍电价补购的损失。2025年2月至12月总费用为1358.38万元。与等权误差准备相比，普通电费增加约1.97万元，紧急电费减少约46.63万元，净节省\textbf{44.66万元}，说明适当增加普通购电准备能够减少更昂贵的临时补购。

\textbf{针对问题三}，采用\textbf{融合预测与日内校正滚动规划}，融合官方光伏预报与近期历史，依据当天已发生的负载偏差修正后续判断，并权衡调整费与补购费，更新尚未执行的订单。同一评价期总费用为1301.42万元。进一步设置相同模型下的信息对照：相较零点固定订单，日内反馈与改单节省\textbf{50.63万元}；在已有反馈与改单能力的基础上，后发官方光伏预报额外节省\textbf{6.95万元}，并使紧急购电量下降30.10\%。后两组期末库存相同，表明新增信息的收益并非来自多消耗剩余电量。

\textbf{针对问题四}，在未来真实电价未知的条件下，零点分支采用提升树预测与线性规划，日内分支采用岭回归预测与滚动线性规划；规划使用预测电价，结算采用实际电价。两套完整策略同期费用分别为1424.86万元和1369.59万元，后者降低3.88\%，反映供需判断、价格预测与订单调整共同作用下的节费效果。

逐时复核表明，方案满足供需平衡及储能容量、功率约束，费用可由实际订单和补购量重新计算。准备量检验与期末库存比较进一步说明了节费的条件与代价。本文将预测偏差、储能调节和信息更新与实际购电损失联系起来，形成了收益来源清晰、运行结果可核验的微网调控方案。
''' + s[end:]
keep(name, s)

name = 'sec_1_problem_review.tex'
s = read(name)
for word in ['光伏发电', '外部电网', '储能设备']:
    s = replace(s, '\\textbf{' + word + '}', word)
s = replace(s,
    r'为此，我们需要根据小区负载、光伏发电预测、储能状态和外网电价等信息，建立\textbf{微网购电—储能联合调度优化模型}，在保证小区正常供电和储能安全运行的前提下，\textbf{使总购电费用尽可能低}。',
    r'因此，需要结合供需预测、储能状态和电价，协调购电与充放电，在保证小区正常供电和储能安全运行的前提下，使总购电费用尽可能低。')
keep(name, s)

name = 'sec_2_problem_analysis.tex'
s = read(name)
s = replace(s,
    '四个问题围绕购电与储能的协调展开，区别在于决策时掌握的信息和允许调整的范围。问题一研究供需与电价已知时的安排；问题二加入供需预测误差；问题三利用日内信息调整订单；问题四进一步考虑未知的波动电价。各问共享电量平衡和储能约束，再针对新增条件扩展决策方法。',
    '四问始终以购电费用为主线：先在供需与电价已知时统筹电量的跨时段安排，再为预测偏差设置准备，随后评价日内反馈与新预报的收益，最后将未知电价纳入决策。各问共享电量平衡和储能约束，随可用信息和调整权限变化逐步扩展，重点考察每项改进如何改变实际购电支出。')
keep(name, s)

name = 'sec_4_data_preprocessing.tex'
s = read(name)
pos = s.index(r'\subsubsection*{（4）日内新预报')
lead, tail = s[:pos], s[pos:]
tail = replace(tail, r'\begin{figure}[htbp]', r'\begin{figure}[H]')
keep(name, lead + tail)

name = 'sec_5_q1.tex'
s = read(name)
# Retain the selected cost; remove indiscriminate bold type in the two detailed tables.
for label in ['tab:q1_purchase_result', 'tab:q1_storage_result']:
    labelpos = s.index('\\label{' + label + '}')
    start = s.rfind(r'\begin{table}', 0, labelpos)
    end = s.index(r'\end{table}', labelpos) + len(r'\end{table}')
    block = re.sub(r'\\textbf\{([^{}]*)\}', r'\1', s[start:end])
    if label == 'tab:q1_purchase_result':
        block = block.replace('35126.85', r'\textbf{35126.85}')
    s = s[:start] + block + s[end:]
s = replace(s, r'该目标关注\textbf{购电费用}。', '该目标关注购电费用。')
s = replace(s, r'全天购电量\textbf{59482.70 kWh}', '全天购电量59482.70 kWh')
keep(name, s)

name = 'sec_6_q2.tex'
s = read(name)
start = s.index('问题二需要在当天供需尚未确定时提前订电。')
end = s.index(r'\subsubsection*{（1）负载与光伏分别预测}')
s = s[:start] + r'''问题二需要在当天供需尚未确定时提前订电。候选包括历史分项预测、岭回归和提升树。历史分项预测能够直接利用负载的星期规律和光伏的近期变化，便于解释供需判断的来源；后两者则可利用更多特征描述线性或非线性关系。

预测之后，还需要决定如何承担偏差带来的购电损失。因此，本文采用\textbf{历史分项预测、近期加权准备与跨日线性规划}，根据近期缺口误差设置准备，再结合储能余量确定订单，以减少预测不足时的高价补购。

''' + s[end:]
s = replace(s,
    '取 $\\beta=0.7$ 时，历史权重约每两天减半，既突出近期变化，也保留此前记录。1月8—31日的参数比较和评价期检验支持这一选择。分位参数取0.7，则用于兼顾准备不足与过量订电，具体费用比较见第6.5节。',
    '取 $\\beta=0.7$ 时，历史权重约每两天减半，既突出近期变化，也保留此前记录。继续减小会使权重更集中于少数日期，更容易受异常日牵动；低于0.7的设置未作全年比较，因此不将其解释为全局最优。1月8—31日的参数比较及评价期费用检验提供了选择依据，分位与衰减的费用权衡见第6.5节。')
s = replace(s, r'\subsubsection*{（1）候选方案比较}', r'\subsubsection*{（1）误差准备的节费作用与方案比较}')
s = replace(s, r'& \textbf{1297.96} & \textbf{60.43} & \textbf{1358.38}', r'& 1297.96 & 60.43 & \textbf{1358.38}')
start = s.index('增加准备后，普通电费有所上升')
end = s.index(r'\subsubsection*{（2）评价期与指定日期结果}')
s = s[:start] + r'''表中首先比较不设置准备的三种预测策略，再考察历史分项预测加入准备后的效果。最终方案较无准备的历史预测方案降低总费用约14.74\%。这些结果评价的是完整购电策略，不能单独据此判断历史预测器优于岭回归或提升树。

与等权准备相比，\textbf{近期加权以约1.97万元的新增普通电费，减少约46.63万元的紧急电费，净节省44.66万元}，降幅3.18\%。统一分位数计算方式后，仍节省约44.54万元，说明节费主要来自历史误差权重的调整。

因此，本文选择历史分项预测、近期加权准备与跨日规划的组合。它利用数据中的历史规律形成判断，再让准备量跟随近期缺口变化，以适量普通购电减少更昂贵的临时补购，并在表中完整方案中取得最低实际费用。

''' + s[end:]
s = replace(s,
    '1月份用于积累历史、比较前期参数并衔接库存。2月1日得到8592.69 kWh，作为各候选及问题三、四的共同评价起点。此后各策略分别继承自身前一天的实际余电。',
    '1月份用于积累历史、比较前期参数并衔接库存。2月1日得到8592.69 kWh，作为各候选及问题三、四的共同评价起点。此后各策略分别继承自身前一天的实际余电。近期加权方法的选择还参考了2—12月误差诊断，故这一评价期并非完全独立的留出检验；逐日运行仍只使用当时已获得的信息。')
keep(name, s)

name = 'sec_7_q3.tex'
s = read(name)
s = replace(s, r'\textbf{最近四周近期加权} &\textbf{1301.42}&\textbf{16.13}', r'\textbf{最近四周近期加权} &\textbf{1301.42}&16.13')
resultpos = s.index(r'\subsection{调度结果与分析}')
infopos = s.index(r'\subsection{日内新预报的价值}')
testpos = s.index(r'\subsection{参数检验}')
prefix, results, info, tests = s[:resultpos], s[resultpos:infopos], s[infopos:testpos], s[testpos:]
info = replace(info, r'\subsection{日内新预报的价值}', r'\subsection{日内反馈与新预报的价值}\label{sec:q3_information}')
info = replace(info, r'\begin{table}[!htbp]', r'\begin{table}[H]')
start = info.index(r'\begin{tabular}')
end = info.index(r'\end{tabular}') + len(r'\end{tabular}')
info = info[:start] + r'''\begin{tabular}{p{0.50\textwidth}rr}
\toprule
信息与决策条件 & 总费用/万元 & \shortstack{较上一条件\\节省/万元}\\
\midrule
零点订电，全天不修改订单 &1359.00&---\\
日内反馈与改单，不使用后发官方预报 &1308.37&\textbf{50.63}\\
日内反馈与改单，使用后发官方预报 &1301.42&\textbf{6.95}\\
\bottomrule
\end{tabular}''' + info[end:]
info = replace(info, '日内反馈与改单使费用减少50.63万元。', r'\textbf{日内反馈与改单使费用减少50.63万元，后发光伏预报进一步节省6.95万元。}')
info = replace(info, r'实现\textbf{6.95万元的净节省，降幅约0.53\%}', r'实现上述净节省，降幅约0.53\%')
info = replace(info, r'\textbf{减少15.88\%}', r'减少15.88\%')
results = replace(results, r'\subsection{调度结果与分析}', r'\subsection{调度结果与分析}\label{sec:q3_dispatch_results}')
s = prefix + '\\FloatBarrier\n' + info + '\\FloatBarrier\n' + results + tests
keep(name, s)

name = 'sec_8_q4.tex'
s = read(name)
labelpos = s.index(r'\label{tab:q4_price_comparison}')
start = s.rfind(r'\begin{table}', 0, labelpos)
end = s.index(r'\end{table}', labelpos) + len(r'\end{table}')
block = re.sub(r'\\textbf\{([^{}]*)\}', r'\1', s[start:end])
block = replace(block, '问题四-2 & 提升树 &', r'问题四-2 & \textbf{提升树} &')
block = replace(block, '问题四-3 & 岭回归 &', r'问题四-3 & \textbf{岭回归} &')
block = replace(block, '注：价格模型比较', '注：加粗方法为所选路线。价格模型比较')
s = s[:start] + block + s[end:]
s = replace(s,
    '问题四-3中，提升树的预测误差更小，但在上述相同供需条件下，其费用仅比岭回归低约0.016\\%，紧急购电量却更多。可见，价格预测误差更小并不一定带来更合适的储能安排。综合费用、紧急补购和解释难度，本文采用岭回归，将其与问题三的负载校正及滚动调整结构结合。',
    r'\textbf{价格预测的误差大小需要结合实际费用与紧急补购共同评价。}问题四-3中，提升树的预测误差更小，但在表中相同供需条件下，费用仅比岭回归低约0.016\%，紧急购电量却更多。因此，日内分支采用岭回归，是费用接近、补购较少与关系清楚之间的综合取舍，再将其与问题三的负载校正和滚动调整结合。')
keep(name, s)

# Confirm protected content before writing any chapter.
oldabs = (oldroot/'sections/sec_0_abstract.tex').read_text(encoding='utf-8-sig')
def first_para(s):
    return s.split(r'\begin{abstract}', 1)[1].split(r'\textbf{针对问题一}', 1)[0]
assert first_para(oldabs) == first_para(changes['sec_0_abstract.tex'])
assert re.search(r'\\title\{[^\n]*', oldabs).group() == re.search(r'\\title\{[^\n]*', changes['sec_0_abstract.tex']).group()
def figure_block(s, label):
    i=s.index('\\label{'+label+'}')
    return s[s.rfind(r'\begin{figure}',0,i):s.index(r'\end{figure}',i)+len(r'\end{figure}')]
for name,label in [('sec_1_problem_review.tex','fig:weiwang'),('sec_2_problem_analysis.tex','fig:overall_model_framework')]:
    assert figure_block((oldroot/'sections'/name).read_text(encoding='utf-8-sig'),label) == figure_block(changes[name],label)
for name,s in changes.items():
    assert (sections/name).read_bytes() == (oldroot/'sections'/name).read_bytes(), f'Concurrent change: {name}'
for name,s in changes.items():
    (sections/name).write_text(s, encoding='utf-8')

diff = ''.join(''.join(difflib.unified_diff((oldroot/'sections'/name).read_text(encoding='utf-8-sig').splitlines(True),s.splitlines(True),fromfile=name+' before',tofile=name+' after')) for name,s in changes.items())
(audit/'changes.diff').write_text(diff, encoding='utf-8')
print(json.dumps({'changed_chapters':list(changes),'protected_title':True,'protected_abstract_first_paragraph':True,'protected_two_figure_blocks':True},ensure_ascii=False,indent=2))
