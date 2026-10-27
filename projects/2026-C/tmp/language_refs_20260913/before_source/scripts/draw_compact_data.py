"""Re-layout saved EDA only; no fitting or model changes."""
from pathlib import Path
import os,hashlib,json
P=Path(__file__).resolve().parents[4]
paper=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(P/'tmp/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
source=P/'audit/eda-v1'
monthly=pd.read_csv(source/'monthly_summary.csv')
weekday=pd.read_csv(source/'weekday_summary.csv')
errors=pd.read_csv(source/'forecast_error_by_lead.csv')
plt.rcParams.update({'font.family':'SimSun','font.size':11,'axes.unicode_minus':False,'pdf.fonttype':42,
 'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False,'savefig.facecolor':'white'})
out=paper/'fig'
fig,ax=plt.subplots(1,2,figsize=(7.2,2.6),layout='constrained')
ax[0].plot(monthly.month,monthly.load_kw,'o-',color='#b85518',label='负载',lw=1.4,ms=3)
ax[0].plot(monthly.month,monthly.pv_actual_kw,'s--',color='#2166ac',label='光伏',lw=1.4,ms=3)
ax[0].set(title='（a）负载与光伏的月平均水平',xlabel='月份',ylabel='平均功率 / kW',xticks=[1,3,5,7,9,12],ylim=(0,6500))
ax[0].legend(ncol=2,fontsize=10)
ax[1].bar(weekday.weekday,weekday.load_kw,color=['#b85518']*4+['#2166ac']*2+['#b85518'],width=.6)
ax[1].set(title='（b）不同星期位置的平均负载',xlabel='星期',ylabel='平均功率 / kW',xticks=list(range(7)),xticklabels=list('一二三四五六日'),ylim=(0,6500))
for a in ax:a.grid(axis='y',alpha=.18);a.set_axisbelow(True)
fig.savefig(out/'data_compact.pdf',bbox_inches='tight');fig.savefig(out/'data_compact.png',dpi=220,bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(6.4,2.25),layout='constrained')
for scope,label,color,style in [('all','全部匹配样本','#2166ac','--'),('actual_positive','实际光伏大于零','#b85518','-')]:
    g=errors[errors.scope==scope]
    ax.plot(g.lead_hours,g.mae_kw,label=label,color=color,ls=style,lw=1.5,marker='o',ms=2.5)
ax.set(xlabel='预报提前时间 / h',ylabel='平均绝对误差 / kW',xticks=[1,6,12,18,24],ylim=(0,None))
ax.legend(fontsize=10);ax.grid(axis='y',alpha=.18)
fig.savefig(out/'forecast_compact.pdf',bbox_inches='tight');fig.savefig(out/'forecast_compact.png',dpi=220,bbox_inches='tight');plt.close(fig)
files=[source/n for n in ['monthly_summary.csv','weekday_summary.csv','forecast_error_by_lead.csv']]
manifest={'sources':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
 'scope':'Saved descriptive statistics re-plotted without altering data or model; monthly and weekday means follow original source-date grouping.',
 'outputs':['fig/data_compact.pdf','fig/data_compact.png','fig/forecast_compact.pdf','fig/forecast_compact.png']}
(paper/'scripts/compact_figures_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
print('Saved compact figures')
