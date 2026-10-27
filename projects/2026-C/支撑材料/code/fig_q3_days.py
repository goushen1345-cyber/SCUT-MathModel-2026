from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'reproduced/plots/fig';FIG.mkdir(parents=True,exist_ok=True)
z=dict(np.load(ROOT/'results/Q3.npz'))
df=pd.read_csv(ROOT/'figure_inputs/q3_daily.csv')
truth=np.load(ROOT/'data/inputs.npz')['actual']
font_manager.findfont('SimSun', fallback_to_default=False)
plt.rcParams.update({'font.family': ['Times New Roman','SimSun'], 'font.size':11,
 'axes.titlesize':12, 'axes.labelsize':11, 'legend.fontsize':10,
 'axes.unicode_minus':False, 'pdf.fonttype':42, 'ps.fonttype':42,
 'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.8,
 'savefig.facecolor':'white','figure.facecolor':'white','axes.axisbelow':True})
BLUE='#396e96'; GOLD='#bf913c'; GREEN='#62896c'; GRAY='#888888'
outputs=[]
def save(fig, name, fixed_canvas=False):
    for ext in ('pdf','png'):
        p=FIG/f'{name}.{ext}'
        kw={'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {'dpi':300}
        layout_kw={} if fixed_canvas else {'bbox_inches':'tight','pad_inches':.07}
        fig.savefig(p, **layout_kw, **kw); outputs.append(p)
    plt.close(fig)
def grid(ax): ax.grid(axis='y',color='#dddddd',lw=.5)

# Q3 monthly charges: sum raw daily bills, without selecting favorable months.
monthly=df.assign(month=pd.to_datetime(df.date).dt.month).groupby('month').sum(numeric_only=True)
fig,ax=plt.subplots(figsize=(9.1,3.3), layout='constrained')
x=monthly.index.to_numpy()
ax.bar(x,monthly.ordinary_cost/1e4,.63,color=BLUE,label='普通结算')
ax.bar(x,monthly.emergency_cost/1e4,.63,bottom=monthly.ordinary_cost/1e4,color=GOLD,label='紧急购电')
ax.set(xlabel='月份',ylabel='月度费用 / 万元',xticks=x,ylim=(0,180))
ax.legend(loc='upper left',frameon=False,ncol=2);grid(ax)
save(fig,'q3_final_monthly')

# Q3 10-minute physical curves. Arrays are chronological: slot k starts k/6 h.
# Storage arrays refer to edges; energy orders are multiplied by six for kW.
# Font sizes account for insertion at 0.88 textwidth (~399 pt).
# Keep exactly the prior paper PDF MediaBox; do not crop away fixed margins.
plt.rcParams.update({'font.size':16,'axes.titlesize':17,'axes.labelsize':16,
                     'xtick.labelsize':16,'ytick.labelsize':16,'legend.fontsize':15.5})
fig,axes=plt.subplots(3,2,figsize=(717.0852734375/72,512.54/72),sharex=True,sharey='row')
fig.subplots_adjust(left=.145,right=.985,bottom=.15,top=.86,hspace=.55,wspace=.22)
hours=np.arange(144)/6; edges=np.arange(145)/6
handles0=None;handles2=None
for col,date in enumerate(('2025-03-20','2025-09-23')):
    i=int(df.index[df.date==date][0]); day=int(z['days'][i]); ex=z['execution'][i]
    actual=truth[day*144:(day+1)*144]
    q0=z['q0'][i]; final=z['versions'][i,-1]
    ax=axes[0,col]
    l1,=ax.plot(hours,actual[:,0],color='black',lw=1.05,label='实际负载')
    l2,=ax.plot(hours,actual[:,1],color=GREEN,lw=1.05,label='实际光伏')
    l3,=ax.step(hours,q0*6,where='post',color=GRAY,lw=.9,ls='--',label='零点订单')
    l4,=ax.step(hours,final*6,where='post',color=BLUE,lw=1.05,label='最终订单')
    handles0=[l1,l2,l3,l4]
    ax.set_title('3月20日' if col==0 else '9月23日',pad=9)
    ax.set(ylim=(0,14500),yticks=[0,5000,10000]);grid(ax)
    ax=axes[1,col]
    ax.plot(edges,np.r_[ex[0,0],ex[:,1]],color=BLUE,lw=1.2)
    for limit in (1200,10800): ax.axhline(limit,color=GRAY,ls='--',lw=.7)
    ax.set(ylim=(0,11600),yticks=[1200,6000,10800]);grid(ax)
    ax=axes[2,col]
    deficit=np.maximum((actual[:,0]-actual[:,1])/6-final,0)
    f=ax.fill_between(hours,deficit,step='post',color='#d9d9d9',label='订单外缺口')
    d,=ax.step(hours,ex[:,7],where='post',color=BLUE,lw=1.1,label='电池补充')
    e=ax.bar(hours,ex[:,8],width=1/6,align='edge',color=GOLD,label='紧急购电')
    handles2=[f,d,e];ax.set(xlabel='时刻 / h',xlim=(0,24),xticks=[0,6,12,18,24],ylim=(0,1000),yticks=[0,250,500,750,1000]);grid(ax)
axes[0,0].set_ylabel('功率 / kW');axes[1,0].set_ylabel('储电量 / kWh');axes[2,0].set_ylabel('每时段补缺电量 / kWh')
fig.legend(handles0,[h.get_label() for h in handles0],loc='upper center',bbox_to_anchor=(.54,.994),ncol=4,frameon=False,columnspacing=1.15,handlelength=1.8)
fig.legend(handles2,['订单外缺口','电池补充','紧急购电'],loc='lower center',bbox_to_anchor=(.55,.005),ncol=3,frameon=False,columnspacing=1.4,handlelength=1.8)
save(fig,'q3_final_days',fixed_canvas=True)
