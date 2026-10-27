from pathlib import Path
import shutil
from datetime import datetime

root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo_backup_20260913_003434'
backup=root/'tmp'/('analysis_assumptions_before_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir()
for name in ('sec_2_problem_analysis.tex','sec_3_model_assumption.tex'):
    shutil.copy2(src/'sections'/name,backup/name)
shutil.copy2(src/'main.pdf',backup/'main.pdf')
analysis=r'''% !TEX root = ../main.tex
% !TEX program = xelatex
\section{问题分析}

四个问题围绕购电与储能的协调展开，区别在于决策时能够掌握的信息及允许调整的范围。问题一先研究供需和电价已知时的调度；问题二加入供需预测误差；问题三进一步利用日内信息修正安排；问题四则分别在问题二、三的基础上考虑电价波动。因此，各问可以共享电量平衡和储能约束，再针对新增困难扩展决策方法。

\subsection{问题一的分析}

问题一的关键在于\textbf{供需与电价在时间上的错位}。光伏充足的时段未必用电最多，用电高峰也未必对应最低电价。储能可以转移电量，但容量、充放电功率和能量损耗限制了这种转移：低价时过多充电可能挤占后续光伏的储存空间，提前放电又可能使高价时段缺少可用电量。因此，不能仅凭当前电价决定充放电，而应统筹全天安排。

由于电量平衡、储能变化和购电费用均可用线性关系表示，可通过\textbf{电量流线性规划}协调各时段的购电与充放电。同时，日初与日末储电量相等，使安排能够每日重复，避免通过消耗初始库存压低当天费用。

\subsection{问题二的分析}

问题二中，零点制定计划时尚不知道当天的真实供需，问题一的调度结构因此需要接入预测信息。数据分析表明，负载具有较明显的星期规律，光伏的日间波动则更大，二者应当\textbf{分别预测}，再共同确定外网需要补足的电量。

然而，按预测值恰好订电并不一定最省钱。订电不足可能触发五倍电价的紧急补购，订电过多又可能形成无效支出；电池虽能缓冲偏差，却受剩余电量和充放电功率限制。因此，需要根据近期供需缺口的预测误差安排\textbf{适量准备}，平衡两类损失。此外，当天留下的电量会影响次日购电，不能只追求当天费用最低。由此，将准备量与跨日线性规划结合，并用实际供需检验计划执行后的费用和储能变化。

\subsection{问题三的分析}

问题三允许在日内获得新预报后修改安排，但\textbf{信息更新并不意味着修改订单一定划算}。一方面，新光伏预报和已经发生的负载可以纠正零点判断；另一方面，部分短时偏差能够由电池吸收，修改订单还需承担调整费用。因此，决策的重点是判断偏差是否可能持续，以及调整带来的预期节省能否覆盖费用。

据此，将光伏预报与历史信息融合，利用已发生的负载偏差修正后续需求，再依据当前储电量，对尚未执行的安排进行\textbf{滚动优化}。这样既保留问题二的提前准备，也能随日内信息及时纠偏。评价新预报的价值时，还需保持调度方法和调整权限一致，比较使用与不使用后续光伏预报的费用，区分新预报的收益与反馈改单本身的收益。

\subsection{问题四的分析}

问题四中，未来电价同样未知。价格判断不仅影响费用估计，还会改变提前购电和储能转移是否值得。因此，不能只将前三问的结果换一个电价结算，而应将\textbf{价格预测纳入购电决策}。

两种情形分别承接问题二和问题三。零点安排情形需要一次判断全天价格，可利用提升树刻画历史价格、时间及供需特征之间的非线性关系。日内调整情形还可以利用当天已发生的价格修正后续判断，但新增特征可能彼此相关，使预测不够稳定，因此通过岭回归抑制系数波动。两条分支分别保留原有调整权限，将价格预测与供需预测共同用于调度，并按实际电价评价费用。由此判断，价格预测能否真正改善购电和储能安排，而非仅提高预测精度。
'''
(src/'sections/sec_2_problem_analysis.tex').write_text(analysis,encoding='utf-8')
p=src/'sections/sec_3_model_assumption.tex'
old=p.read_text(encoding='utf-8')
symbols=old[old.index(r'\subsection{符号说明}'):]
assumptions=r'''% !TEX root = ../main.tex
% !TEX program = xelatex
\section{模型假设与符号说明}

\subsection{模型假设}

为便于分析与建模，作如下假设：

\noindent\textbf{假设1：}光伏优先满足负载，外网购电可直接供负载或用于充电；富余电量在容量和充电功率允许时存入储能。

\noindent\textbf{假设2：}每个10分钟时段内，负载功率、光伏功率和电价保持不变。

\noindent\textbf{假设3：}问题二至四的储电量跨日连续衔接，日初电量取前一日实际日末电量。

\noindent\textbf{假设4：}决策仅使用当时已发生的观测和已发布的预报，不提前使用未来真实供需及电价。

\noindent\textbf{假设5：}同一时段的调整费用，仅按最终订单相对零点原计划的净变化结算一次。

\noindent\textbf{假设6：}不考虑电池自放电与寿命折旧，未利用的富余光伏不计售电收益。

'''
p.write_text(assumptions+symbols,encoding='utf-8')
assert p.read_text(encoding='utf-8').split(r'\subsection{符号说明}',1)[1]==old.split(r'\subsection{符号说明}',1)[1]
print('Updated analysis and assumptions; symbols unchanged. Backup:',backup)
