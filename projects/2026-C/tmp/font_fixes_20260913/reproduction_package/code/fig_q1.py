from pathlib import Path
import json, csv, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox
PROJECT=Path(__file__).resolve().parents[1]
HERE=PROJECT/'reproduced/plots/fig'
HERE.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':['Times New Roman','SimSun'],'font.size':15,
 'axes.labelsize':15,'axes.titlesize':15,'xtick.labelsize':14.5,'ytick.labelsize':14.5,'axes.unicode_minus':False,
 'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
 'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
 'axes.axisbelow':True,'savefig.facecolor':'white','legend.frameon':False})
def save(fig, name):
    fig.canvas.draw()
    # Preserve the original paper figure size; enlarge labels within that area.
    box = Bbox.from_bounds(0, 0, 573.144/72, 633.451725/72)
    for ext in ('pdf','png'):
        kw = {'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}
        fig.savefig(HERE/f'{name}.{ext}',dpi=300,bbox_inches=box,**kw)
    fig.savefig(HERE/f'{name}_preview.png',dpi=120,bbox_inches=box)
    plt.close(fig)

ROOT=PROJECT/'figure_inputs/q1'
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
fig=plt.figure(figsize=(573.144/72,633.451725/72))
gs=fig.add_gridspec(4,1,height_ratios=[1,.23,1,1],left=.16,right=.985,bottom=.16,top=.94,hspace=.20)
axs=[fig.add_subplot(gs[r]) for r in (0,2,3)]
legend_ax=fig.add_subplot(gs[1]); legend_ax.axis('off')
axs[0].step(np.r_[t,24],np.r_[p,p[-1]],where='post',color='#444444',lw=1.5)
axs[0].set_ylabel('电价（元/kWh）'); axs[0].set_title('同一天，不同策略怎样安排电池和购电')
axs[0].axvline(t[peak],color='#999999',lw=.8,ls=':')
axs[0].annotate('当天最高价',xy=(t[peak],p[peak]),xytext=(16,p[peak]+.12),
    arrowprops={'arrowstyle':'->','color':'black'},fontsize=14.5)
axs[0].set_ylim(0,max(p)+.3)
for c in ['03','10','04']:
    rr=schedules[c]; ss=[float(rr[0]['state_start'])]+[float(r['state_end']) for r in rr]
    axs[1].plot(np.arange(145)/6,ss,label=names_cn[c],color=colors[c],ls=styles[c],lw=1.6)
    qq=np.array([float(r['purchase_kwh']) for r in rr])*6
    axs[2].step(np.r_[t,24],np.r_[qq,qq[-1]],where='post',label=names_cn[c],color=colors[c],ls=styles[c],lw=1.25)
for bound in [1200,10800]: axs[1].axhline(bound,color='#888888',ls=':',lw=.8)
axs[1].set_ylim(0,12000); axs[1].set_yticks([1200,6000,10800]); axs[1].set_ylabel('内部储电量（kWh）')
handles,labels=axs[1].get_legend_handles_labels()
legend_ax.legend(handles,labels,ncol=3,loc='center',fontsize=15,handlelength=2,columnspacing=1.2)
axs[2].set_ylabel('外网购电功率（kW）'); axs[2].set_xlabel('时刻（时）')
for ax in axs:
    ax.set_xlim(0,24); ax.set_xticks(range(0,25,2)); ax.grid(axis='y',alpha=.18)
fig.text(.06,.049,'同一代表日；两种规则各选27组参数中费用最低者。',fontsize=14.5)
fig.text(.06,.019,'首尾均为6000 kWh，充放效率各90%。',fontsize=14.5)
for axis in axs[:2]: axis.tick_params(labelbottom=False)
save(fig,'03_Q1_daily_dispatch')
