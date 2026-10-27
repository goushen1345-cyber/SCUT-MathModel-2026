"""Render paper figures/tables only from saved, verified Q3/Q4 research results.

Run from any directory with E:/Anaconda/python.exe -X utf8 this_script.py.
An alternate --output-root recreates the same artifacts without overwriting the paper.
No forecasting, fitting, dispatch optimization, or research-state mutation is performed.
"""
from pathlib import Path
import argparse, hashlib, json, platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt, font_manager

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output-root', type=Path, default=HERE.parent)
args = parser.parse_args()
OUT = args.output_root.resolve()
FIG = OUT / 'fig'; TAB = OUT / 'tables'; META = OUT / 'scripts'
for p in (FIG, TAB, META): p.mkdir(parents=True, exist_ok=True)
Q3 = PROJECT / 'questions/Q3/runs/20260912-forecast-risk-v1/outputs'
Q4 = PROJECT / 'questions/Q4/runs/20260913-q3-transfer-v1/outputs'
OLD4 = PROJECT / 'questions/Q4/runs/20260912-selected-deepening-v1/outputs/comparison.csv'
SRC = PROJECT / 'questions/Q3/runs/20260911-four-candidates-v1/outputs/sources.npz'
PREV3 = PROJECT / 'questions/Q3/runs/20260912-load-feedback-v1/outputs/strategies/LEARN_PREFIX.summary.json'
sources = []
def readj(p):
    sources.append(p)
    return json.loads(p.read_text(encoding='utf-8-sig'))
def readcsv(p):
    sources.append(p)
    return pd.read_csv(p)
def readnpz(p):
    sources.append(p)
    return dict(np.load(p))

s3, s4 = readj(Q3/'summary.json'), readj(Q4/'summary.json')
v3, v4 = readj(Q3/'verification.json'), readj(Q4/'verification.json')
z = readnpz(Q3/'strategies/EW4_Q60_full.npz')
df = readcsv(Q3/'strategies/EW4_Q60_full.daily.csv')
truth = readnpz(SRC)['actual']
prev3 = readj(PREV3)
old4 = readcsv(OLD4)
assert len(df) == 334 and np.array_equal(z['days'], np.arange(31,365))
assert abs(df.total_cost.sum()-s3['winner']['total_cost']) < 1e-6
assert abs(z['execution'][:,:,8].sum()-s3['winner']['emergency_kwh']) < 1e-6
assert np.allclose(z['execution'][1:,0,0], z['execution'][:-1,-1,1], atol=1e-8)

font_manager.findfont('SimSun', fallback_to_default=False)
plt.rcParams.update({'font.family': ['Times New Roman','SimSun'], 'font.size':11,
 'axes.titlesize':12, 'axes.labelsize':11, 'legend.fontsize':10,
 'axes.unicode_minus':False, 'pdf.fonttype':42, 'ps.fonttype':42,
 'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.8,
 'savefig.facecolor':'white','figure.facecolor':'white','axes.axisbelow':True})
BLUE='#396e96'; GOLD='#bf913c'; GREEN='#62896c'; GRAY='#888888'
outputs=[]
def save(fig, name):
    for ext in ('pdf','png'):
        p=FIG/f'{name}.{ext}'
        kw={'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {'dpi':300}
        fig.savefig(p, bbox_inches='tight', pad_inches=.07, **kw); outputs.append(p)
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
fig,axes=plt.subplots(3,2,figsize=(10,7.3),sharex=True,sharey='row')
fig.subplots_adjust(left=.08,right=.985,bottom=.13,top=.9,hspace=.48,wspace=.17)
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
    ax.set_ylim(0,14500);grid(ax)
    ax=axes[1,col]
    ax.plot(edges,np.r_[ex[0,0],ex[:,1]],color=BLUE,lw=1.2)
    for limit in (1200,10800): ax.axhline(limit,color=GRAY,ls='--',lw=.7)
    ax.set(ylim=(0,11600),yticks=[1200,6000,10800]);grid(ax)
    ax=axes[2,col]
    deficit=np.maximum((actual[:,0]-actual[:,1])/6-final,0)
    f=ax.fill_between(hours,deficit,step='post',color='#d9d9d9',label='订单外缺口')
    d,=ax.step(hours,ex[:,7],where='post',color=BLUE,lw=1.1,label='电池补充')
    e=ax.bar(hours,ex[:,8],width=1/6,align='edge',color=GOLD,label='紧急购电')
    handles2=[f,d,e];ax.set(xlabel='时刻 / h',xlim=(0,24),xticks=[0,6,12,18,24],ylim=(0,1000));grid(ax)
axes[0,0].set_ylabel('功率 / kW');axes[1,0].set_ylabel('储电量 / kWh');axes[2,0].set_ylabel('每时段补缺电量 / kWh')
fig.legend(handles0,[h.get_label() for h in handles0],loc='upper center',bbox_to_anchor=(.53,.99),ncol=4,frameon=False)
fig.legend(handles2,['订单外缺口','电池补充','紧急购电'],loc='lower center',bbox_to_anchor=(.53,.015),ncol=3,frameon=False)
save(fig,'q3_final_days')

# Information comparison: identical EW4 load/feedback family, own causal errors.
info=[s3['zero_control'],s3['no_new_control'],s3['winner']]
fig,ax=plt.subplots(figsize=(8.7,3.6),layout='constrained')
names=['零点锁定订单','日内反馈与调整\n不使用后发光伏预报','日内反馈与调整\n使用后发光伏预报']
vals=np.array([a['total_cost'] for a in info])/1e4
bars=ax.bar(np.arange(3),vals,color=[GRAY,BLUE,GREEN],width=.48)
ax.bar_label(bars,labels=[f'{v:.2f}' for v in vals],padding=5)
ax.set(xticks=np.arange(3),xticklabels=names,ylabel='全年总费用 / 万元',ylim=(0,1510))
grid(ax);save(fig,'q3_final_information')

# Validation compares structures, not a chronology of versions.
bylabel={r['label']:r for r in s3['candidates']}
loadrows=[bylabel['W1_Q60_full'],bylabel['W2_Q60_full'],prev3,bylabel['EW4_Q60_full']]
qrows=[bylabel[f'EW4_Q{n}_full'] for n in (40,50,60,70,80)]
fig,ax=plt.subplots(1,2,figsize=(10,3.5),layout='constrained',gridspec_kw={'wspace':.16})
cost=np.array([r['total_cost'] for r in loadrows])/1e4
ax[0].scatter(np.arange(4),cost,color=BLUE,s=30)
for i,c in enumerate(cost): ax[0].annotate(f'{c:.2f}',(i,c),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
ax[0].set(xticks=np.arange(4),xticklabels=['1周','2周均值','4周均值','4周加权'],xlabel='同星期负载参考',ylabel='全年总费用 / 万元',ylim=(1299,1309),xlim=(-.45,3.45))
ax[0].set_title('(a) 负载参考方式');grid(ax[0])
quantiles=np.array([.4,.5,.6,.7,.8]);total=np.array([r['total_cost'] for r in qrows])/1e4
ordinary=np.array([r['ordinary_cost'] for r in qrows])/1e4
ax[1].plot(quantiles,total,'o-',color=BLUE,label='总费用',lw=1.15)
ax[1].plot(quantiles,ordinary,'s--',color=GOLD,label='普通结算',lw=1.05)
ax[1].fill_between(quantiles,ordinary,total,color=GOLD,alpha=.16,label='紧急购电费')
ax[1].annotate(f'{total[2]:.2f}',(.6,total[2]),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
ax[1].set(xticks=quantiles,xlabel='误差准备分位',ylabel='全年费用 / 万元',ylim=(1267,1342));ax[1].set_title('(b) 准备量与购电费用')
ax[1].legend(loc='upper center',ncol=3,frameon=False,fontsize=8.5,columnspacing=.65,handlelength=1.4);grid(ax[1])
save(fig,'q3_final_validation')

# Q4: original verified Q4-2 leaves and final Q4-3 quantile comparison.
tree=old4.set_index(['branch','strategy'])
treevals=np.array([tree.loc[('Q4-2',s),'total_cost'] for s in ('P3-leaves7','P3-full','P3-leaves31')])
delta=treevals-treevals[1]
qr=sorted(s4['candidates'],key=lambda r:r['quantile'])
fig,ax=plt.subplots(1,2,figsize=(10,3.5),layout='constrained',gridspec_kw={'wspace':.16})
ax[0].plot([7,15,31],delta,color=BLUE,marker='o',lw=1.2)
ax[0].axhline(0,color='black',lw=.7)
for n,y in zip([7,15,31],delta): ax[0].annotate(f'{y:+,.0f}',(n,y),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
ax[0].set(xticks=[7,15,31],xlabel='每棵树最多叶节点数',ylabel='相对15叶树费用变化 / 元',ylim=(-8200,3300),xlim=(4,34));ax[0].set_title('(a) 问题四-2：树复杂度');grid(ax[0])
total=np.array([r['total_cost'] for r in qr])/1e4;ordinary=np.array([r['ordinary_settlement_cost'] for r in qr])/1e4
ax[1].plot(quantiles,total,'o-',color=BLUE,label='总费用',lw=1.15)
ax[1].plot(quantiles,ordinary,'s--',color=GOLD,label='普通结算',lw=1.05)
ax[1].fill_between(quantiles,ordinary,total,color=GOLD,alpha=.16,label='紧急购电费')
ax[1].annotate(f'{total[2]:.2f}',(.6,total[2]),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
ax[1].set(xticks=quantiles,xlabel='误差准备分位',ylabel='全年费用 / 万元',ylim=(1330,1414));ax[1].set_title('(b) 问题四-3：准备量与费用')
ax[1].legend(loc='upper center',ncol=3,frameon=False,fontsize=8.5,columnspacing=.65,handlelength=1.4);grid(ax[1])
save(fig,'q4_final_validation')

dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
ids=[int(df.index[df.date==d][0]) for d in dates]
def n(x): return f'{0. if abs(x)<.0005 else x:.2f}'
def clock(k): return f'{k//6:02d}:{(k%6)*10:02d}'
def interval(k): return f'{clock(k)}--{clock(k+1)}'
head=['项目','3月20日','6月21日','9月23日','12月21日']
def table(filename,caption,label,columns,rows,spec):
    content=['% Generated from saved final Q3 trajectories. Do not hand-edit numbers.',r'\begin{table}[H]',r'\centering',r'\caption{'+caption+'}',r'\label{'+label+'}',r'\small',r'\setlength{\tabcolsep}{5pt}',r'\begin{tabular}{'+spec+'}',r'\toprule',' & '.join(columns)+r' \\',r'\midrule']
    content += [' & '.join(row)+r' \\' if isinstance(row,list) else row for row in rows]
    content += [r'\bottomrule',r'\end{tabular}',r'\end{table}','']
    p=TAB/filename;p.write_text('\n'.join(content),encoding='utf-8');outputs.append(p)
slots=[60,72,84,96,108,120]
table('q3_original.tex','指定日期零点原计划的部分时段购电量（kWh）','tab:q3_original_order',['时间段']+head[1:],[[interval(k)]+[n(z['q0'][i,k]) for i in ids] for k in slots],'lrrrr')
rows=[[interval(k)]+[n(z['versions'][i,-1,k]) for i in ids] for k in slots]
rows += [r'\midrule']
for label,vals in [
 ('全天原计划购电量/kWh',[z['q0'][i].sum() for i in ids]),
 ('全天最终普通订单/kWh',[z['versions'][i,-1].sum() for i in ids]),
 ('全天紧急购电量/kWh',[df.loc[i,'emergency_kwh'] for i in ids]),
 ('普通结算费用/元',[df.loc[i,'ordinary_cost'] for i in ids]),
 ('紧急购电费用/元',[df.loc[i,'emergency_cost'] for i in ids]),
 ('全天总费用/元',[df.loc[i,'total_cost'] for i in ids])]:rows.append([label]+[n(x) for x in vals])
table('q3_final.tex','指定日期调整后订单及全天费用（时段订单单位为kWh）','tab:q3_final_order',head,rows,'lrrrr')
rows=[]
for a in range(6):
    sl=slice(a*24,(a+1)*24)
    rows.append([f'{clock(a*24)}--{clock((a+1)*24)}','充电']+[n(z['execution'][i,sl,5:7].sum()) for i in ids])
    rows.append(['','放电']+[n(z['execution'][i,sl,7].sum()) for i in ids])
rows += [r'\midrule',['0:00','内部储电量']+[n(z['execution'][i,0,0]) for i in ids],['24:00','内部储电量']+[n(z['execution'][i,-1,1]) for i in ids]]
table('q3_storage.tex','指定日期的实际充放电及日首尾储电量（kWh）','tab:q3_storage',['时间段','项目']+head[1:],rows,'llrrrr')
rows=[];details={}
for date,i,name in zip(dates,ids,head[1:]):
    ex=z['execution'][i];ks=np.flatnonzero(ex[:,8]>1e-6)
    for j,k in enumerate(ks): rows.append([name if j==0 else '',interval(int(k)),n(ex[k,8])])
    if not len(ks):rows.append([name,'无','0.00'])
    details[date]={**{k:float(df.loc[i,k]) for k in ('initial','final','ordinary_cost','emergency_cost','total_cost','emergency_kwh')},
        'q0_total_kwh':float(z['q0'][i].sum()),'qfinal_total_kwh':float(z['versions'][i,-1].sum()),
        'emergency_intervals':[{'slot':int(k),'time':interval(int(k)),'emergency_kwh':float(ex[k,8]),'storage_start_kwh':float(ex[k,0]),'storage_end_kwh':float(ex[k,1]),'discharge_kwh':float(ex[k,7]),'limitation':'power' if ex[k,7]>=5000/6-1e-6 else 'energy'} for k in ks]}
table('q3_emergency.tex','指定日期发生紧急购电的时段及电量','tab:q3_emergency',['日期','时间段','紧急购电量/kWh'],rows,'llr')

derived={'date_results':details,'monthly':[{'month':int(i),**{c:float(row[c]) for c in ['ordinary_cost','emergency_cost','total_cost']}} for i,row in monthly.iterrows()],
 'q3_final':s3['winner'],'q3_information':info,'q3_load_comparison':loadrows,'q3_quantile_comparison':qrows,
 'q4_final':s4['winner'],'q4_quantile_comparison':qr,
 'q4_tree_comparison':[{'leaves':int(n),'total_cost':float(v),'difference_from_15':float(d)} for n,v,d in zip([7,15,31],treevals,delta)],
 'time_mapping':'Saved arrays are chronological: slot 0=00:00--00:10, slot 143=23:50--24:00; source/template cyclic row shift already applied upstream. No additional roll is performed here.',
 'storage_side':'charge is external-side grid+PV received for charging; discharge is load-side output; storage is internal kWh; eta_charge=eta_discharge=.9.'}
p=META/'derived_values.json';p.write_text(json.dumps(derived,ensure_ascii=False,indent=2),encoding='utf-8');outputs.append(p)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'kind':'Existing result aggregation and figure/table rendering only','source_script':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
 'inputs':[{'path':str(p.resolve()),'sha256':sha(p)} for p in dict.fromkeys(sources)],
 'outputs':[{'path':str(p.resolve()),'sha256':sha(p)} for p in outputs],
 'environment':{'python':platform.python_version(),'matplotlib':matplotlib.__version__,'numpy':np.__version__,'pandas':pd.__version__,'font':'Times New Roman + SimSun'},
 'reproduce':'E:/Anaconda/python.exe -X utf8 scripts/update_result_figures.py --output-root <empty directory>',
 'checks':{'334_days':True,'chronological_array_dates':True,'daily_total_matches_summary':True,'emergency_total_matches_summary':True,'storage_cross_day_continuity':True,'actual_render_visual_review':'pending','embedded_paper_pages':'root agent to check'}}
(META/'result_figures_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'outputs':len(outputs),'specified_dates':details,'month_min':int(monthly.total_cost.idxmin()),'month_max':int(monthly.total_cost.idxmax())},ensure_ascii=False,indent=2))
