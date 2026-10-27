from pathlib import Path
import json, csv, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
plt.rcParams.update({'font.family':'SimSun','font.size':10,'axes.unicode_minus':False,
 'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
 'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
 'axes.axisbelow':True,'savefig.facecolor':'white','legend.frameon':False})
def save(fig, name):
    fig.canvas.draw()
    for ext in ('pdf','png'):
        kw = {'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}
        fig.savefig(HERE/f'{name}.{ext}',dpi=300,bbox_inches='tight',**kw)
    fig.savefig(HERE/f'{name}_preview.png',dpi=120,bbox_inches='tight')
    plt.close(fig)

BASE = PROJECT/'questions/Q3/runs/20260911-four-candidates-v1'
PARAM = PROJECT/'questions/Q3/runs/20260911-parameter-interpretability-v1'
SELECTED = 'M_q60_b070_w28_h03'
trace = dict(np.load(PARAM/f'outputs/strategies/{SELECTED}.npz'))
sources = dict(np.load(BASE/'outputs/sources.npz'))
actual = sources['actual']
days = trace['days'].astype(int)
q0, execution = trace['q0'], trace['execution']
qf = trace['versions'][:,3]
dates = pd.to_datetime('2025-01-01') + pd.to_timedelta(days, unit='D')
slot_map = {str(date.date()): i for i,date in enumerate(dates)}
chosen_dates = ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
BLUE, GREEN, RED, GREY = '#386a94','#5f8768','#b34e4a','#777777'
# Two specified dates: the largest emergency amount and the smallest among the four.
specified_amounts = {date: float(execution[slot_map[date],:,8].sum()) for date in chosen_dates}
high = max(chosen_dates, key=lambda date: specified_amounts[date])
low = min(chosen_dates, key=lambda date: specified_amounts[date])
plot_dates = [high, low] if high != low else chosen_dates[:2]
fig = plt.figure(figsize=(8.8, 8.1))
gs = fig.add_gridspec(5, 2, height_ratios=[.16, 1, 1, .16, 1],
                     left=.09, right=.98, bottom=.075, top=.98, hspace=.40, wspace=.28)
axes = np.array([[fig.add_subplot(gs[r, c]) for c in range(2)] for r in (1,2,4)])
legend_top = fig.add_subplot(gs[0,:]); legend_top.axis('off')
legend_bottom = fig.add_subplot(gs[3,:]); legend_bottom.axis('off')
for column, date in enumerate(plot_dates):
    i, day = slot_map[date], int(days[slot_map[date]])
    truth = actual[day*144:day*144+144]
    x = np.arange(144)/6
    axes[0,column].step(x, truth[:,0], where="post", color="black", linewidth=1, label="实际负载")
    axes[0,column].step(x, truth[:,1], where="post", color=GREEN, linewidth=1.1, label="实际光伏")
    axes[0,column].step(x, q0[i]*6, where="post", color=GREY, linewidth=.8, linestyle="--", label="零点订单")
    axes[0,column].step(x, qf[i]*6, where="post", color=BLUE, linewidth=1, label="最终订单")
    axes[0,column].set_title(date[5:].replace("-", "月") + "日", fontsize=11)
    state = np.r_[execution[i,0,0], execution[i,:,1]]
    axes[1,column].plot(np.arange(145)/6, state, color=BLUE, linewidth=1.2)
    for bound in (1200, 10800):
        axes[1,column].axhline(bound, color=GREY, linestyle="--", linewidth=.7)
    axes[1,column].set(ylim=(0,12000), yticks=[1200,6000,10800])
    gap = np.maximum((truth[:,0]-truth[:,1])/6-qf[i], 0)
    axes[2,column].fill_between(x, gap, step="post", color="#dddddd", label="普通电后的缺口")
    axes[2,column].step(x, execution[i,:,7], where="post", color=BLUE, linewidth=1, label="电池补充")
    axes[2,column].bar(x, execution[i,:,8], width=1/6, align="edge", color=RED, label="紧急购电")
    axes[2,column].set(xlim=(0,24), xticks=np.arange(0,25,4), xlabel="时刻 / h")
    for axis in axes[:,column]:
        axis.grid(axis="y", alpha=.15)
axes[0,0].set_ylabel("功率 / kW")
axes[1,0].set_ylabel("内部储电量 / kWh")
axes[2,0].set_ylabel("每10分钟电量 / kWh")
handles, labels = axes[0,0].get_legend_handles_labels()
legend_top.legend(handles, labels, loc='center', ncol=4, fontsize=10, columnspacing=2)
handles, labels = axes[2,0].get_legend_handles_labels()
legend_bottom.legend(handles, labels, loc='center', ncol=3, fontsize=10, columnspacing=2)
for axis in axes[:2,:].ravel():
    axis.set(xlim=(0,24), xticks=np.arange(0,25,4))
    axis.tick_params(labelbottom=False)
save(fig, '01_Q3_specified_days')
