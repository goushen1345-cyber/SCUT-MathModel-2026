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

ROOT=PROJECT/'questions/Q1/runs/20260911-compare-v1'
def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
summary=json.loads((ROOT/'outputs/summary.json').read_text('utf-8'))
selected={row['candidate']:row for row in summary['comparison']}
schedules={c:rows(ROOT/'outputs/schedules'/f"{row['key']}.csv") for c,row in selected.items()}
p=np.array([float(r['price']) for r in schedules['04']]); t=np.arange(144)/6
peak=int(p.argmax())
names_cn={'03':'峰谷策略','04':'线性规划','10':'光伏预留策略'}
colors={'03':'#b65a32','04':'#1f66a5','10':'#32805a'}
styles={'03':'--','04':'-','10':':'}
fig=plt.figure(figsize=(8.2,9.1))
gs=fig.add_gridspec(4,1,height_ratios=[1,.21,1,1],left=.115,right=.975,bottom=.10,top=.94,hspace=.18)
axs=[fig.add_subplot(gs[r]) for r in (0,2,3)]
legend_ax=fig.add_subplot(gs[1]); legend_ax.axis('off')
axs[0].step(np.r_[t,24],np.r_[p,p[-1]],where='post',color='#444444',lw=1.5)
axs[0].set_ylabel('电价（元/kWh）'); axs[0].set_title('同一天，不同策略怎样安排电池和购电')
axs[0].axvline(t[peak],color='#999999',lw=.8,ls=':')
axs[0].annotate('当天最高价',xy=(t[peak],p[peak]),xytext=(16,p[peak]+.12),
    arrowprops={'arrowstyle':'->','color':'black'},fontsize=10)
axs[0].set_ylim(0,max(p)+.3)
for c in ['03','10','04']:
    rr=schedules[c]; ss=[float(rr[0]['state_start'])]+[float(r['state_end']) for r in rr]
    axs[1].plot(np.arange(145)/6,ss,label=names_cn[c],color=colors[c],ls=styles[c],lw=1.6)
    qq=np.array([float(r['purchase_kwh']) for r in rr])*6
    axs[2].step(np.r_[t,24],np.r_[qq,qq[-1]],where='post',label=names_cn[c],color=colors[c],ls=styles[c],lw=1.25)
for bound in [1200,10800]: axs[1].axhline(bound,color='#888888',ls=':',lw=.8)
axs[1].set_ylim(0,12000); axs[1].set_yticks([1200,6000,10800]); axs[1].set_ylabel('内部储电量（kWh）')
handles,labels=axs[1].get_legend_handles_labels()
legend_ax.legend(handles,labels,ncol=3,loc='center',fontsize=11); axs[2].set_ylabel('外网购电功率（kW）'); axs[2].set_xlabel('时刻（时）')
for ax in axs:
    ax.set_xlim(0,24); ax.set_xticks(range(0,25,2)); ax.grid(axis='y',alpha=.18)
fig.text(.06,.022,'同一代表日；两种规则各选27组参数中费用最低者。首尾均为6000 kWh，充放效率各90%。',fontsize=9)
for axis in axs[:2]: axis.tick_params(labelbottom=False)
save(fig,'03_Q1_daily_dispatch')
