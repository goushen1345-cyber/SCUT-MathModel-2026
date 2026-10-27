"""Two explanatory figures from verified saved comparisons only."""
from pathlib import Path
import argparse,json,hashlib,os
R=Path(__file__).resolve().parent;P=R.parents[3]
os.environ.setdefault('MPLCONFIGDIR',str(P/'tmp/matplotlib-q2-trial'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import numpy as np
a=argparse.ArgumentParser();a.add_argument('--output',default='figures-v1');args=a.parse_args()
F=(R/args.output).resolve();assert F.is_relative_to(P) and not F.exists();F.mkdir()
assert json.loads((R/'verification.json').read_text(encoding='utf-8'))['status']=='passed'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
font=font_manager.findfont(font_manager.FontProperties(family='SimSun'),fallback_to_default=False)
plt.rcParams.update({'font.family':'SimSun','font.size':11,'axes.titlesize':12,'text.color':'black','axes.labelcolor':'black',
 'xtick.color':'black','ytick.color':'black','axes.unicode_minus':False,'pdf.fonttype':42,
 'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False,'figure.facecolor':'white'})
B='#2166ac';RUST='#bd5414';G='#23806c';names=['T1','T2','T3','T4'];labels=['同星期规律','岭回归','提升树','规律＋误差余量']
c=pd.read_csv(R/'outputs/comparison.csv').set_index('variant').loc[names]
m=pd.read_csv(R/'interpretation/month_metrics.csv').pivot(index='month',columns='variant',values='total_cost')
entries=[]
def save(fig,name,note):
    fig.get_layout_engine().set(rect=(0,.075,1,.91));fig.text(.025,.012,note,fontsize=9,va='bottom',color='black')
    fig.canvas.draw();renderer=fig.canvas.get_renderer();W,H=fig.canvas.get_width_height();excluded=set()
    for ax in fig.axes:
        for axis in [ax.xaxis,ax.yaxis]:
            lo,hi=sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                if not lo<=tick.get_loc()<=hi:excluded.update([id(tick.label1),id(tick.label2)])
    bad=[]
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_visible() or not t.get_text() or id(t) in excluded:continue
        box=t.get_window_extent(renderer)
        if box.x0< -2 or box.y0< -2 or box.x1>W+2 or box.y1>H+2:bad.append(t.get_text())
    assert not bad,bad
    fig.savefig(F/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None});fig.savefig(F/(name+'.png'),dpi=300)
    plt.close(fig);entries.append(name)
fig,axs=plt.subplots(2,1,figsize=(8,7.4),layout='constrained')
x=np.arange(4);axs[0].bar(x,c.ordinary_cost/1e4,color=B,label='普通购电费')
axs[0].bar(x,c.emergency_cost/1e4,bottom=c.ordinary_cost/1e4,color=RUST,label='紧急购电费')
for i,y in enumerate(c.total_cost/1e4):axs[0].text(i,y+8,f'{y:.2f}',ha='center',fontsize=11)
axs[0].set(xticks=x,xticklabels=labels,ylabel='2—6月费用（万元）',ylim=(0,800),title='（a）少花紧急购电费，抵消了多订普通电的支出')
axs[0].legend(ncol=2,loc='upper center')
saving=(m.T1-m.T4)/1e4;axs[1].bar(m.index,saving,color=[G if y>=0 else RUST for y in saving])
axs[1].axhline(0,color='black',lw=.8)
for month,y in saving.items():axs[1].text(month,y+(1 if y>=0 else -1),f'{y:.2f}',ha='center',va='bottom' if y>=0 else 'top')
axs[1].set(xticks=range(2,7),xlabel='月份',ylabel='加余量相对不加余量的节费（万元）',ylim=(-6,48),title='（b）收益主要集中在5—6月，2月反而略贵')
for ax in axs:ax.grid(axis='y',alpha=.15)
save(fig,'01_cost_and_months','相同起始库存、固定电价、48小时规划和实际执行规则；设置仅由1月历史选出。\n正节费表示加余量更省；2—6月用于候选比较，尚非全年验证。')
info=json.loads((R/'interpretation/summary.json').read_text(encoding='utf-8'))
e=pd.read_csv(R/'interpretation/paired_extreme_day_trajectories.csv')
fig,axs=plt.subplots(3,2,figsize=(10,8.6),layout='constrained',sharex=True,sharey='row')
for col,(date,label) in enumerate([(info['best_day'],'节费最多日'),(info['worst_day'],'增加费用最多日')]):
    for kind,color,ls,name in [('T1',B,'-','不加余量'),('T4',RUST,'--','增加误差余量')]:
        d=e[(e.decision_date==date)&(e.variant==kind)].sort_values('slot');hour=d.slot.to_numpy()/6
        axs[0,col].step(np.r_[hour,24],np.r_[d.order_kwh.to_numpy()*6,d.order_kwh.iloc[-1]*6],where='post',color=color,ls=ls,label=name)
        axs[1,col].plot(np.arange(145)/6,np.r_[d.storage_start_kwh.iloc[0],d.storage_end_kwh],color=color,ls=ls,label=name)
        axs[2,col].step(np.r_[hour,24],np.r_[d.emergency_kwh.to_numpy()*6,d.emergency_kwh.iloc[-1]*6],where='post',color=color,ls=ls,label=name)
    axs[0,col].set_title(date[5:]+'：'+label)
    axs[0,col].set_ylim(0,11500)
    axs[1,col].axhline(1200,color='gray',ls=':',lw=1);axs[1,col].axhline(10800,color='gray',ls=':',lw=1)
    axs[2,col].set(xlim=(0,24),xticks=range(0,25,6),xlabel='区间起点（时）')
axs[0,0].set_ylabel('普通订电功率（kW）');axs[1,0].set_ylabel('实际储电量（kWh）');axs[2,0].set_ylabel('紧急购电功率（kW）')
axs[0,0].legend(fontsize=10,ncol=2,loc='upper right')
for ax in axs.ravel():ax.grid(axis='y',alpha=.15)
save(fig,'02_paired_extreme_days','展示150天中同星期方案加余量后节费最多与增费最多的两天；不是随机代表日。\n两策略沿各自跨日库存运行；日内普通订单不调整，允许电池按实际供需执行。')
manifest={'figures':entries,'matplotlib':matplotlib.__version__,'font':font,'dpi':300,'script_sha256':sha(Path(__file__)),
 'sources':{str(p.relative_to(R)):sha(p) for p in [R/'outputs/comparison.csv',R/'interpretation/month_metrics.csv',
 R/'interpretation/summary.json',R/'interpretation/paired_extreme_day_trajectories.csv']},
 'outputs':{p.name:sha(p) for p in F.iterdir() if p.is_file()},'visible_text_within_canvas':True,'visual_qa':'pending'}
(F/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(str(F))
