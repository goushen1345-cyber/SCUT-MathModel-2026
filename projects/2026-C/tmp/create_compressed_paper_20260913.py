from pathlib import Path
import json,hashlib,shutil,re,datetime
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
src=root/'shumo_1/shumo_backup_20260913_003434'
dest=src/'压缩版'
assert not dest.exists(), 'Separate compressed source already exists; inspect before overwriting.'
audit=root/'tmp'/('compressed_paper_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
audit.mkdir(parents=True)
tracked=[src/'main.pdf',src/'main.tex',*sorted((src/'sections').glob('*.tex')),*sorted((src/'tables').glob('*.tex')),*sorted((src/'fig').glob('*'))]
hashes={str(p.relative_to(src)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked if p.is_file()}
(audit/'original_hashes.json').write_text(json.dumps(hashes,indent=2),'utf-8')
(root/'tmp/compressed_paper_audit_path.txt').write_text(str(audit),'utf-8')
dest.mkdir()
for folder in ['sections','tables','fig']:
    shutil.copytree(src/folder,dest/folder)
shutil.copy2(src/'main.tex',dest/'main.tex')
originals={p.name:p.read_text('utf-8') for p in (src/'sections').glob('*.tex')}
blocks={}
for s in originals.values():
    for block in re.findall(r'\\begin\{(table|figure)\}.*?\\end\{\1\}',s,re.S):pass
    for match in re.finditer(r'\\begin\{(?P<kind>table|figure)\}.*?\\end\{(?P=kind)\}',s,re.S):
        block=match.group();lab=re.search(r'\\label\{([^}]+)\}',block)
        if lab: blocks[lab.group(1)]=block

def save(name,text):
    text=re.sub(r'@@\{([^}]+)\}',lambda m:blocks[m.group(1)],text)
    assert '@@' not in text
    (dest/'sections'/name).write_text('% !TEX root = ../main.tex\n% !TEX program = xelatex\n'+text.strip()+'\n','utf-8')

save('sec_2_problem_analysis.tex',r'''
\section{问题分析}

四个问题围绕购电与储能的协调展开，区别在于决策时掌握的信息和允许调整的范围。问题一研究供需与电价已知时的安排；问题二加入供需预测误差；问题三利用日内信息调整订单；问题四进一步考虑未知的波动电价。各问共享电量平衡和储能约束，再针对新增条件扩展决策方法。

\subsection{问题一的分析}
问题一的关键是\textbf{供需与电价在时间上的错位}。光伏充足时未必用电最多，用电高峰也未必对应最低电价。储能可以转移电量，但容量、充放电功率和能量损耗限制了这种转移：提前充满可能挤占后续光伏的储存空间，过早放电又可能使高价时段缺少可用电量。因此，需要统筹全天的购电与充放电。

购电费用、电量平衡和储能变化均可用线性关系表示，适合用\textbf{电量流线性规划}求解。日初与日末储电量相等，则使每日安排能够重复执行，避免通过消耗初始库存压低当天费用。

\subsection{问题二的分析}
问题二在零点订电时尚不知道当天真实供需，需要先利用历史数据形成判断。负载具有星期规律，光伏的日际变化更强，因此二者应当\textbf{分别预测}。

预测偏差会造成两类损失：订电不足可能触发五倍电价的紧急补购，订电过多又可能付费后用不完。电池能够缓冲部分偏差，但受库存和功率限制。因此，需要根据近期误差设置适量准备，并考虑当天余电对次日购电的影响，将预测、误差准备和跨日调度结合起来。

\subsection{问题三的分析}
问题三允许获得新预报后修改尚未执行的订单。新光伏预报和已发生的负载可以修正零点判断，但短时偏差未必持续，部分缺口也可以由电池补足。因此，调整的关键是判断\textbf{未来供需变化是否值得支付改单费用}。

据此，将官方光伏预报与历史信息融合，利用当天负载偏差修正后续需求，再根据实际储电量滚动优化剩余订单。评价日内预报的价值时，应在相同调整权限下比较有、无后发预报的结果，区分新预报的收益与反馈改单本身的收益。

\subsection{问题四的分析}
问题四中，未来电价也需要预测。价格判断会改变提前购电和储能转移是否合算，因此应将\textbf{价格预测纳入调度}，而不只是更换最终结算单价。

两条分支分别承接问题二和问题三。零点分支主要依靠历史价格与供需特征判断全天价格；日内分支还可利用当天已发生的价格修正后续判断。针对两种信息条件分别选择预测方法，再将预测价格用于决策、实际价格用于结算，以评价价格预测对购电安排的实际作用。

四问的模型组成及递进关系如图~\ref{fig:overall_model_framework}所示。
@@{fig:overall_model_framework}
''')

save('sec_4_data_preprocessing.tex',r'''
\section{数据预处理与探索性分析}
\subsection{数据预处理}
本文数据来自赛题附件，涵盖负载、光伏、电价及不同时间发布的光伏预报。各附件的时间写法和排列方式有所不同，功率数据也需要转换为调度使用的电量。为使各项数据准确对应，进行以下处理。

\noindent\textbf{1．检查缺失与异常记录。}原表已有记录未发现空单元格，但按实际时间排列后，全年实测数据缺少1月1日00:00—00:10这一段，启动处理见第6.3节。夜间光伏为零属于正常情况，予以保留；极端取值经原表核对后，也不因数值较大或较小而直接删除。

\noindent\textbf{2．统一时间与区间对应关系。}各行数据用于标注时刻开始的10分钟区间。例如，首行“00:10”对应00:10—00:20，末行“00:00+1”对应次日00:00—00:10。问题一中，每天各时段的负载、光伏出力和电价均相同，因此将末行零点数据放到当天开头；全年连续数据则按实际日期衔接，不将次日零点移回当天。描述性统计仍按原表日期分组。

\noindent\textbf{3．区分预报批次。}统一日期与时间格式，并为光伏预报同时保留“发布时间”和“目标时刻”，避免新预报覆盖旧预报。超出实测覆盖范围的预报予以保留，但不参与误差比较。

\noindent\textbf{4．转换电量并核对。}每个时段为10分钟，即 $\Delta t=1/6\ \mathrm h$，将功率按 $E=P\Delta t$ 转换为电量，并核对整理前后的数值及时间对应关系。全年统计用于识别数据特征，逐日决策仅使用当时已获得的信息。

\subsection{探索性分析}
经过整理与分析，得到以下四点发现。

\subsubsection*{（1）光伏富余与用电缺口存在时间错位}
@@{fig:tsxfx_1}
图~\ref{fig:tsxfx_1}显示，代表日午间光伏能够覆盖负载并产生富余，傍晚光伏回落后，外网需要补足的电量明显增加，且与较高电价有所重合。全年有330天出现过光伏功率高于负载的情况，说明光伏富余具有普遍性。

因此，储能需要将富余光伏或低价购电留到后续使用。能够转移多少电量，又受到容量、充放电功率和效率限制。这说明购电与储能应当按时段联合安排，全天电量总和不能代替逐时供需判断。

\subsubsection*{（2）负载与光伏的年内变化不同步}
@@{fig:tsxfx_2}
图~\ref{fig:tsxfx_2}显示，夏季负载较高，光伏也能提供较多电量；冬季负载虽有所回落，光伏下降却更加明显。以月平均功率差衡量，12月负载减去光伏约为3177 kW，接近5月的两倍。

这表明，\textbf{外网补电压力取决于负载与光伏的共同变化}。不同月份的电价也存在差异，因此需要随近期数据更新判断，不能将代表日的购电安排直接复制到全年。

\subsubsection*{（3）负载具有星期规律，光伏与电价的日际变化更强}
@@{fig:tsxfx_3}
按实际星期分组后，周五、周六的平均负载比其余五天低约36.8\%；负载与一周前数据的相关性也高于与前一天数据的相关性。因此，同一星期位置的历史负载更有参考价值。

光伏在不同日期呈现相似的昼夜变化，但扣除各月相同时刻的平均水平后，其一周相关性接近于零。这说明，光伏的相似性主要来自白天发电、夜间为零的共同特征，负载的星期规律不宜直接用于光伏预测。

图~\ref{fig:tsxfx_3}显示，相同时刻在不同日期的电价也存在较大差异。由此，负载、光伏和电价应分别利用适合自身特点的历史信息，再共同参与购电决策。

\subsubsection*{（4）日内新预报提高预测精度，为滚动调整提供依据}
@@{fig:tsxfx_4}
将不同发布时间的预报与相同目标时刻的实测值匹配后发现，预报提前时间越长，平均绝对误差总体越大。在实际光伏大于零的4177组配对样本中，使用目标时刻前最新日内预报后，平均绝对误差由约378.8 kW降至116.3 kW，下降约69\%，如图~\ref{fig:tsxfx_4}所示。

新预报为修正购电提供了更准确的信息。考虑到约17.4\%的样本更新后误差增大，且修改订单需要付费，后续由优化模型综合预报、储能余量和调整成本决定改单幅度，将预测精度的改善转化为实际购电收益。
''')

save('sec_5_q1.tex',r'''
\section{问题一的模型建立与求解}
\subsection{电量流线性规划的建立}
问题一已知各时段的供需和电价，适合统筹全天安排。本文考虑峰谷电价策略、光伏空间预留策略和线性规划三种方案。前两种策略直观易用，但需要事先设置价格门槛或目标储电量；线性规划则能同时考虑当前充放电对后续用电的影响。由于费用和设备约束均为线性关系，本文采用\textbf{电量流线性规划}，并通过相同条件下的策略比较检验其效果。

\subsubsection*{（1）电量划分与决策变量}
沿用前文的144个10分钟时段。第 $k$ 段的负载电量和光伏电量为
\begin{equation}
E_k^L=L_k\Delta t,\qquad E_k^{PV}=P_k^{PV}\Delta t.
\label{eq:q1_energy}
\end{equation}
按照光伏优先满足负载的运行假设，定义
\begin{equation}
m_k=\min(E_k^L,E_k^{PV}),\qquad n_k=E_k^L-m_k,\qquad r_k=E_k^{PV}-m_k.
\label{eq:q1_gap_surplus}
\end{equation}
其中，$m_k$ 为光伏直接供电量，$n_k$ 为剩余负载缺口，$r_k$ 为富余光伏。

以外网充电量 $x_k$、光伏充电量 $y_k$、电池向负载输出的电量 $z_k$ 和时段末内部储电量 $S_k$ 为决策变量。电量分配关系如图~\ref{fig:q1_1}所示。
@@{fig:q1_1}
外网直接补足电池放电后的负载缺口，还可以额外给电池充电，因此
\begin{equation}
q_k=n_k-z_k+x_k,\qquad w_k=r_k-y_k,
\label{eq:q1_purchase}
\end{equation}
其中，$q_k$ 为外网购电量，$w_k$ 为未利用光伏电量。

\subsubsection*{（2）目标函数}
以全天购电费用最低为目标：
\begin{equation}
\min C=\sum_{k=1}^{144}p_k(n_k-z_k+x_k).
\label{eq:q1_objective}
\end{equation}
该目标关注\textbf{购电费用}。即使储能损耗使总购电量有所增加，只要低价购电能够替代更昂贵的后续购电，仍可能降低总费用。

\subsubsection*{（3）约束条件}
光伏充电不能超过富余量，电池放电不能超过负载缺口；充放电还应满足设备功率限制：
\begin{equation}
x_k\ge0,\qquad 0\le y_k\le r_k,\qquad 0\le z_k\le n_k,
\label{eq:q1_supply_constraint}
\end{equation}
\begin{equation}
x_k+y_k\le P_{\max}\Delta t,\qquad z_k\le P_{\max}\Delta t.
\label{eq:q1_power_constraint}
\end{equation}
其中，$P_{\max}\Delta t=5000/6\ \mathrm{kWh}$，计算时保留精确值。该限制作用于储能充放电，不限制外网直接向负载供电。

考虑充、放电各90\%的效率，内部储电量满足
\begin{equation}
S_k=S_{k-1}+\eta_c(x_k+y_k)-\frac{z_k}{\eta_d},\qquad \eta_c=\eta_d=0.9,
\label{eq:q1_soc_transition}
\end{equation}
\begin{equation}
S_{\min}\le S_k\le S_{\max},\qquad S_{\min}=1200,\quad S_{\max}=10800.
\label{eq:q1_soc_bound}
\end{equation}
日初与日末均取6000 kWh：
\begin{equation}
S_0=S_{144}=6000.
\label{eq:q1_terminal_constraint}
\end{equation}
这样既保证储能在允许范围内运行，也避免通过消耗初始电量降低当天表面费用，使各策略能够在相同起点和终点下比较。

\subsection{模型求解}
模型包含576个连续变量，各时段通过储电量递推相互连接，采用SciPy的\texttt{linprog}接口调用HiGHS求解。

本题无需额外设置0—1变量区分充放电。若某时段同时充放电，则该段存在负载缺口，没有富余光伏，充电只能来自外网。取 $\delta=\min(x_k,z_k/0.81)>0$，将充电减少 $\delta$、放电减少 $0.81\delta$，不足的负载由外网直接补充。由于 $0.9\delta-0.81\delta/0.9=0$，储电变化不变，功率约束仍满足，而购电量减少 $0.19\delta$。电价为正时费用随之下降，因此最优解不会保留这种同时充放电。

求解时，先按时间标签整理数据并转换电量，再计算光伏直供后的缺口和富余量，代入目标函数及约束，得到各时段购电、充放电和储电安排。结果按原模板的时间标签对应填回。

\subsection{调度结果与策略比较}
\subsubsection*{（1）购电与储能结果}
线性规划得到全天购电量\textbf{59482.70 kWh}，购电费用\textbf{35126.85元}；储能累计充电20740.67 kWh、向负载输出16799.94 kWh。指定结果见表~\ref{tab:q1_purchase_result}和表~\ref{tab:q1_storage_result}。
@@{tab:q1_purchase_result}
@@{tab:q1_storage_result}
表中充放电量按电池外侧计量，库存按内部电量计量。一个4小时区间同时出现充电和放电，表示不同10分钟时段采取了不同动作。

\subsubsection*{（2）策略比较}
峰谷策略按价格门槛安排充放电，光伏空间预留策略进一步为午间富余光伏保留储能空间。两种规则均比较27组参数：低价门槛取电价的15\%、25\%、35\%分位，高价门槛取65\%、75\%、85\%分位，目标储电量取6000、8400、10800 kWh。

分别选取已比较组合中费用最低的规则方案，与线性规划对照。各方案均在日末恢复6000 kWh，恢复库存所需的购电全部计入费用，结果见表~\ref{tab:q1_strategy_compare}。
@@{tab:q1_strategy_compare}
线性规划较峰谷策略节省3149.79元，降幅\textbf{8.23\%}；较光伏空间预留策略节省2817.50元，降幅\textbf{7.43\%}。三种策略的购电与储能安排如图~\ref{fig:q1_2}所示。
@@{fig:q1_2}
20:00时，两种规则策略均已降至1200 kWh的储电下限，线性规划仍保留5168.13 kWh。到20:40—20:50，电价达到全天最高的1.3952元/kWh，线性规划利用储能满足负载，外网购电量为零；另外两种策略则需购买715.65 kWh的高价电。

因此，节费的关键是\textbf{根据全天供需和价格变化，将有限储能留给更有价值的时段}。虽然线性规划因储能损耗多购电1740.28 kWh，但增加的低价购电替代了更昂贵的后续购电，最终费用更低。

\subsection{模型检验与初始电量分析}
逐时核对供需平衡、储电递推、容量与功率约束，并重新计算全天费用。三个初始电量案例的最大储电递推残差约为 $1.34\times10^{-12}\ \mathrm{kWh}$。利用对偶乘子独立重算费用下界后，求解费用与下界的最大差值约为 $1.22\times10^{-12}$ 元。两者均处于数值误差范围，支持所得解的可行性与数值最优性。

进一步取1200、6000和10800 kWh三种初始电量，并分别要求日末恢复至对应初值，重新优化，结果见表~\ref{tab:q1_sensitivity}。
@@{tab:q1_sensitivity}
三种状态的费用相对主方案变化均不足1\%，且都为晚间最高价时段保留电量。这表明，主要调度规律对所比较初始储电量的变化较为稳定。
''')

save('sec_6_q2.tex',r'''
\section{问题二的模型建立与求解}
\subsection{供需预测与近期误差准备}
问题二需要在当天供需尚未确定时提前订电。本文考虑历史分项预测、岭回归和提升树等方案。历史分项预测能够直接利用负载的星期规律和光伏的近期变化，解释清楚、计算简洁；岭回归和提升树则可利用更多特征描述线性与非线性关系。

本题的费用还取决于预测偏差如何处理。因此，本文将\textbf{近期加权准备与跨日线性规划}相结合，在形成供需预测后，根据近期误差安排适量准备，平衡订电不足与订电过量的损失。

\subsubsection*{（1）负载与光伏分别预测}
负载取过去四个相同星期位置的同刻平均，光伏取最近七天的同刻平均：
\begin{equation}
\widehat L_{d,k}=\frac14\sum_{j=1}^{4}L_{d-7j,k},\qquad
\widehat P^{PV}_{d,k}=\frac17\sum_{j=1}^{7}P^{PV}_{d-j,k}.
\label{eq:q2_forecast}
\end{equation}
四周同星期数据保留负载的星期规律，并平滑单日波动；七天光伏数据反映近期发电水平。上述窗口结合1月份的方案比较确定，历史不足时对当时已有的对应记录取平均。

跨日规划所需的次日负载，按次日星期位置选取历史；次日光伏仍参考当前零点以前最近七天的数据。两天预测均以\textbf{当前零点}为信息截止点，不使用未来真实值，也不引入附件3的光伏预报。

\subsubsection*{（2）根据近期误差设置准备}
连续低估负载或高估光伏，会使电池不断补充缺口，最终可能触及库存下限。为此，定义历史净需求预测误差：
\begin{equation}
\varepsilon_{i,k}=\left[(L_{i,k}-P^{PV}_{i,k})-(\widehat L_{i,k}-\widehat P^{PV}_{i,k})\right]\Delta t.
\label{eq:q2_error}
\end{equation}
正值表示实际缺口大于预测。历史预测按当时能够获得的信息形成。

将一天分为六个4小时区间，收集最近28天同一区间的误差。设 $\mathcal H_{d,g}$ 为第 $d$ 天零点可用的第 $g$ 组记录，对历史误差赋予权重：
\begin{equation}
\omega_{d,i,k}=\frac{\beta^{d-1-i}}{\displaystyle\sum_{(j,u)\in\mathcal H_{d,g}}\beta^{d-1-j}},\qquad (i,k)\in\mathcal H_{d,g}.
\label{eq:q2_weight}
\end{equation}
较新的记录权重更高，使准备量能够跟随近期变化。将误差排序后，计算加权累计比例，并取相应分位：
\begin{align}
F_{d,g}(u)&=\sum_{(i,k)\in\mathcal H_{d,g}}\omega_{d,i,k}\mathbf1(\varepsilon_{i,k}\le u),\label{eq:q2_cdf}\\
b_{d,k}&=\max\left\{0,\inf\{u:F_{d,g(k)}(u)\ge\alpha\}\right\}.\label{eq:q2_reserve}
\end{align}
其中，\textbf{$\alpha$控制准备程度，$\beta$控制旧误差的衰减速度}。本文均取0.7，但二者作用不同：70\%分位是误差分布中的位置，不是直接增加70\%的购电量，也不是供电可靠率。

取 $\beta=0.7$ 时，历史权重约每两天减半，既突出近期变化，也保留此前记录。1月8—31日的参数比较和评价期检验支持这一选择。分位参数取0.7，则用于兼顾准备不足与过量订电，具体费用比较见第6.5节。

准备量进入规划净需求后，既可能增加预计缺口，也可能减少计划中的光伏富余，最终购电量仍由储能调度共同决定。

\subsection{跨日购电与储能模型}
只考虑当天，可能使模型在午夜前过早用尽储能。因此，每天零点规划未来48小时，共288个时段，\textbf{只固定当天前144个时段的订单}；次日安排用于辅助当前决策，到次日零点再重新制定。

用 $t$ 连续编号规划时段，含准备量的净需求为
\begin{equation}
N_t=(\widehat L_t-\widehat P^{PV}_t)\Delta t+b_t,\qquad
n_t=\max(N_t,0),\quad a_t=\max(-N_t,0).
\label{eq:q2_net_demand}
\end{equation}
其中，$n_t$ 为计划缺口，$a_t$ 为扣除准备后的预计余量。普通订单满足
\begin{equation}
q_t=n_t-z_t+x_t.
\label{eq:q2_purchase}
\end{equation}
以计划购电费用减去期末储电参考价值为目标：
\begin{equation}
\min J=\sum_{t=1}^{288}p_tq_t-\nu S_{288},\qquad \nu=\eta_dp_{00:00}.
\label{eq:q2_objective}
\end{equation}
内部1 kWh电量能够向负载输出约 $\eta_d$ kWh，因此按零点电价赋予参考价值。该项用于减轻规划末端的影响，不作为售电收入，也不从实际账单中扣除。

储电递推、容量和充放电功率约束沿用第5.1节，其中光伏充电上限改为预计余量 $a_t$，放电上限采用计划缺口 $n_t$。初始库存取当天零点实际储电量 $S_0=S_{d,0}$，日末余电连续传递至次日，不再要求每日首尾相等。

上述模型直接优化计划费用，紧急购电风险通过准备量体现。方案优劣最终按实际运行中的普通购电费与紧急购电费之和评价。

\subsection{模型求解与实际运行}
预测与准备量确定后，采用HiGHS求解当天订单。日内订单保持不变，储能根据实际供需充放电。

设某时段实际负载电量为 $l$，光伏电量为 $v$，普通订单为 $q$，时段开始时内部储电量为 $S$。供电不足时，先由电池补充，再紧急购买剩余缺口：
\begin{align}
D&=\max(l-v-q,0),\label{eq:q2_actual_deficit}\\
z^{\mathrm{act}}&=\min\{D,P_{\max}\Delta t,\eta_d(S-S_{\min})\},\qquad e=D-z^{\mathrm{act}}.\label{eq:q2_emergency}
\end{align}
存在余电时，在容量与充电功率允许范围内储存：
\begin{equation}
c^{\mathrm{act}}=\min\left\{\max(v+q-l,0),P_{\max}\Delta t,\frac{S_{\max}-S}{\eta_c}\right\}.
\label{eq:q2_actual_charge}
\end{equation}
充电优先使用富余光伏，再使用普通订单余量，内部储电量更新为
\begin{equation}
S^{\mathrm{next}}=S+\eta_cc^{\mathrm{act}}-\frac{z^{\mathrm{act}}}{\eta_d}.
\label{eq:q2_actual_soc}
\end{equation}
未能使用或储存的普通订单仍需付费，未利用光伏不计售电收益。因此，每日实际费用及跨日衔接为
\begin{equation}
C_d=\sum_{k=1}^{144}\left(p_kq_{d,k}+5p_ke_{d,k}\right),\qquad S_{d+1,0}=S_{d,144}.
\label{eq:q2_daily_cost}
\end{equation}
运行从1月1日零点的6000 kWh开始，首日采用问题一的购电安排。实测序列缺少首个00:00—00:10区间，仅该段借用附件1零点供需作启动参考，不作为实测值或预测训练标签；此后使用附件2的连续实测数据。

1月份用于积累历史、比较前期参数并衔接库存。2月1日得到8592.69 kWh，作为各候选及问题三、四的共同评价起点。此后各策略分别继承自身前一天的实际余电。

\subsection{方案比较与运行结果}
\subsubsection*{（1）候选方案比较}
统一电价、设备参数、初始库存、规划长度与实际供电规则，比较2025年2月1日至12月31日共334天的实际费用，结果见表~\ref{tab:q2_model_compare}。
@@{tab:q2_model_compare}
增加准备后，普通电费有所上升，但五倍电价的紧急补购显著减少。最终方案较不设置准备的历史预测方案降低总费用约14.74\%。

与等权准备相比，近期加权增加普通电费约1.97万元，减少紧急电费约46.63万元，净节省\textbf{44.66万元，降幅3.18\%}。统一分位数计算方式后，仍节省约44.54万元，说明节费主要来自历史误差权重的调整。

因此，本文选择历史分项预测、近期加权准备与跨日规划的组合。其优势在于利用数据中清楚的历史规律，并将近期缺口误差转化为准备量，在表中完整方案中取得最低实际费用。

\subsubsection*{（2）评价期与指定日期结果}
最终总购电费用为\textbf{13583810.84元}，其中普通电费12979560.57元、紧急电费604250.27元。完整10分钟结果保存于\texttt{result2.xlsx}。
@@{fig:q2_monthly_cost}
图~\ref{fig:q2_monthly_cost}显示，11个月的费用均低于等权准备方案，6月和12月的节省较为明显，说明费用优势覆盖了不同季节。指定日期的结果见表~\ref{tab:q2_specified_purchase}、表~\ref{tab:q2_storage}及紧急购电表。
@@{tab:q2_specified_purchase}
@@{tab:q2_storage}
\input{tables/q2_emergency.tex}
指定时段订单与充放电量的单位均为kWh；全天合计由完整144个时段汇总。充放电按设备外侧计量，库存按内部电量计量。

\subsubsection*{（3）储能对预测偏差的缓冲}
@@{fig:q2_specified_days}
图~\ref{fig:q2_specified_days}中，3月20日储能补足了大部分订单与实际需求之间的缺口。但20:40开始时内部电量仅剩1622.06 kWh，继续放电触及1200 kWh下限后，仍有329.52 kWh需要紧急购买。

6月21日白天光伏充足，电池能够储存余电并在后续释放，全天未发生紧急购电。两个日期说明，\textbf{缓冲能力取决于缺口出现时的库存与放电能力}，不能仅由全天供需总量判断。

\subsection{参数检验与风险分析}
@@{fig:q2_sensitivity}
如图~\ref{fig:q2_sensitivity}所示，固定 $\beta=0.7$，将分位 $\alpha$ 提高至0.8后，紧急购电天数由156天降至102天，但新增普通电费超过紧急电费的节省，总费用上升约3.06万元；降至0.6时，准备不足使总费用上升约16.36万元。

固定 $\alpha=0.7$，将 $\beta$ 提高至0.8和0.9，总费用分别增加约6.12万元和20.49万元。上述比较表明，两个参数取0.7能够较好地兼顾近期响应和购电准备，平衡两类费用。

规划长度方面，48小时较24小时增加费用3215.61元，但将最长连续紧急补购时间由340分钟缩短至200分钟，并保留更多期末储电。因此，保留48小时规划，以较小费用代价改善跨日衔接。去除期末储电参考价值后，总费用保持不变，说明主要节费结果不依赖该辅助项。

进一步从历史误差中选取连续三天的不利片段，构造持续低估负载、高估光伏及两者叠加的情景，并保持实际供需不变。近期加权方案仍比等权准备节省3.09\%—3.52\%，费用优势在所测试情景下得到保持。其中，光伏高估带来的新增费用较为明显，且略高于等权方案，后续改进可重点关注光伏偏差的持续性。
''')

# Q3 and Q4 content is written by the second part before compilation.
(audit/'scaffold.json').write_text(json.dumps({'source':str(src),'compressed_source':str(dest),'status':'scaffold_with_sections_2_4_5_6'},ensure_ascii=False,indent=2),'utf-8')
print('Separate source prepared:',dest)
print('Audit:',audit)
