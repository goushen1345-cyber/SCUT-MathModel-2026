"""Render existing Q4 evidence only; no fitting, optimization or new scenarios."""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
P = HERE.parents[1]
OLD = P/'questions/Q4/runs/20260912-three-candidates-v1'
DEEP = P/'questions/Q4/runs/20260912-selected-deepening-v1'
FIG = HERE/'figures'
FIG.mkdir(exist_ok=True)
(HERE/'tables').mkdir(exist_ok=True)
sources = set()
def csv(path):
    sources.add(path)
    return pd.read_csv(path)
def js(path):
    sources.add(path)
    return json.loads(path.read_text(encoding='utf-8'))
font_manager.fontManager.addfont('C:/Windows/Fonts/simsun.ttc')
plt.rcParams.update({'font.family':'SimSun','font.size':11,'axes.unicode_minus':False,
    'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
    'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
colors = ['#28628c','#bf693b']
def save(fig,name):
    fig.savefig(FIG/(name+'.png'),dpi=260,bbox_inches='tight',facecolor='white')
    fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight',facecolor='white')
    plt.close(fig)

profile=csv(P/'audit/q4-price-exploration-v1/outputs/intraday_profile.csv')
fig, ax=plt.subplots(figsize=(8.0,3.0),layout='constrained')
ax.fill_between(profile.hour,profile.p10,profile.p90,color=colors[0],alpha=.16,label='同刻价格的10%—90%分位范围')
ax.plot(profile.hour,profile['mean'],color=colors[0],lw=1.8,label='同刻平均价格')
ax.set(xlim=(0,24),xticks=range(0,25,3),xlabel='时刻 / h',ylabel='电价 /（元·kWh$^{-1}$）')
ax.legend(loc='upper left',frameon=False,fontsize=10)
ax.grid(axis='y',alpha=.18)
save(fig,'01_price_pattern')

old=js(OLD/'outputs/common_start/summary.json')['results']
features=csv(DEEP/'analysis/q42_feature_parameter_comparison.csv')
structures=csv(DEEP/'analysis/q43_structure_comparison.csv')
updates=csv(DEEP/'analysis/q43_price_update_value.csv')
metrics=csv(OLD/'interpretation/price_forecast_metrics.csv')
q42=csv(DEEP/'outputs/strategies/Q4-2-P3-leaves31.daily.csv')
q43=csv(DEEP/'outputs/strategies/Q4-3-P2-full.daily.csv')
base42=csv(OLD/'outputs/common_start/Q4-2-P3.daily.csv')
tree43=csv(OLD/'outputs/common_start/Q4-3-P3.daily.csv')

fig,axes=plt.subplots(1,2,figsize=(9,3.15),layout='constrained')
for ax,a,b,title in [(axes[0],q42,base42,'（a）零点分支：31叶树相对15叶树'),
                     (axes[1],q43,tree43,'（b）日内分支：岭回归相对提升树')]:
    assert (a.date==b.date).all()
    delta=pd.DataFrame({'month':pd.to_datetime(a.date).dt.month,'saving':b.total_cost-a.total_cost})
    monthly=delta.groupby('month').saving.sum()/10000
    ax.bar(monthly.index,monthly,color=[colors[0] if x>=0 else colors[1] for x in monthly])
    ax.axhline(0,color='black',lw=.65)
    ax.set(xticks=range(2,13),xlabel='月份',ylabel='相对节费 / 万元',title=title)
    ax.grid(axis='y',alpha=.18)
save(fig,'02_monthly_comparison')

fig,axes=plt.subplots(1,2,figsize=(9,3.25),layout='constrained')
keys=['P3-leaves7','P3-full','P3-leaves31']
rows=features.set_index('strategy').loc[keys]
axes[0].plot([7,15,31],rows.cost_change_vs_full,marker='o',color=colors[0])
axes[0].axhline(0,color='black',lw=.65)
axes[0].set(xticks=[7,15,31],xlabel='每棵树最多叶节点数',ylabel='相对15叶树增费 / 元',title='（a）零点分支的树复杂度检验')
for x,y in zip([7,15,31],rows.cost_change_vs_full):
    axes[0].annotate(f'{y:+,.0f}',(x,y),xytext=(0,9),textcoords='offset points',ha='center',fontsize=10)
axes[0].margins(y=.25)
full=next(x for x in old if x['branch']=='Q4-3' and x['candidate']=='P2')['total_cost']
labels=[];values=[]
for _,r in updates.iterrows():
    s=str(r['strategy'])
    if 'freeze' in s: label='全天保持零点判断'
    elif 'omit6' in s or 'omit-06' in s: label='不使用6点价格更新'
    elif 'omit12' in s or 'omit-12' in s: label='不使用12点价格更新'
    elif 'omit18' in s or 'omit-18' in s: label='不使用18点价格更新'
    else: continue
    labels.append(label);values.append(r.total_cost-full)
assert len(values)==4, list(updates.strategy)
axes[1].barh(labels,values,color=[colors[1] if x>0 else colors[0] for x in values])
axes[1].axvline(0,color='black',lw=.65)
axes[1].set(xlabel='相对完整更新方案增费 / 元',title='（b）日内价格更新的费用作用')
axes[1].set_xlim(-65,420)
for i,v in enumerate(values): axes[1].text(v+6 if v>=0 else 6,i,f'{v:+.2f}',va='center',ha='left',fontsize=9)
axes[1].invert_yaxis()
save(fig,'03_validation')

days=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
selected_days=[]
for name,df in [('零点订电',q42),('日内调整',q43)]:
    for _,r in df[df.date.isin(days)].iterrows():
        selected_days.append({'分支':name,**r.to_dict()})
pd.DataFrame(selected_days).to_csv(HERE/'tables/指定日期汇总.csv',index=False,encoding='utf-8-sig')
lines=[r'\begin{tabular}{llrrrr}',r'\toprule',r'分支 & 日期 & 普通订单/kWh & 紧急购电/kWh & 日末储电/kWh & 总费/元 \\',r'\midrule']
for r in selected_days:
    lines.append(f"{r['分支']} & {r['date'][5:]} & {r['order_kwh']:.2f} & {r['emergency_kwh']:.2f} & {r['final']:.2f} & {r['total_cost']:.2f} "+r'\\')
lines += [r'\bottomrule',r'\end{tabular}']
(HERE/'tables/selected_days.tex').write_text('\n'.join(lines),encoding='utf-8')
finding={'scope':'2025-02-01 to 2025-12-31, 334 days, common initial storage',
         'old_candidates':old,'q42_selected':features[features.strategy=='P3-leaves31'].iloc[0].to_dict(),
         'q43_selected':next(x for x in old if x['branch']=='Q4-3' and x['candidate']=='P2'),
         'selected_days':selected_days,'state_sha256':hashlib.sha256((P/'state/state.json').read_bytes()).hexdigest()}
(HERE/'paper_findings.json').write_text(json.dumps(finding,ensure_ascii=False,indent=2),encoding='utf-8')
sources.update([OLD/'run_compare.py',DEEP/'run_deepening.py',DEEP/'outputs/verification.json',DEEP/'validation_report.md',P/'state/state.json',
 P/'audit/q4-price-exploration-v1/outputs/summary.json',OLD/'interpretation/p2_coefficient_stability.csv',
 DEEP/'analysis/terminal_inventory_valuation.csv',DEEP/'analysis/perfect_price_information_gap.csv',
 DEEP/'analysis/high_price_interval_risk.csv',DEEP/'analysis/consecutive_high_price_blocks.csv',
 P/'questions/Q3/runs/20260911-parameter-interpretability-v1/outputs/margins/q60_b070_w28_h03.npz'])
manifest={'scope':'Existing results only; no new research',
 'inputs':{str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)},
 'outputs':{str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(FIG.iterdir())},
 'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'matplotlib':matplotlib.__version__}
(HERE/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'figures':3,'selected_days':len(selected_days),'scope':'read existing evidence only'}))
