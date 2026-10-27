"""Redraw the approved Q3 quantile panel from existing verified results; no experiments."""
from pathlib import Path
import json, hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'reproduced/plots'
(base/'fig').mkdir(parents=True,exist_ok=True)
(base/'scripts').mkdir(exist_ok=True)
source=ROOT/'figure_inputs/derived_values.json'
rows=sorted(json.loads(source.read_text('utf-8'))['q3_quantile_comparison'],key=lambda r:r['q'])
plt.rcParams.update({'font.family':['Times New Roman','SimSun'],'font.size':11,
                     'axes.unicode_minus':False,'pdf.fonttype':42,'ps.fonttype':42})
q=[r['q'] for r in rows]
total=[r['total_cost']/1e4 for r in rows]
ordinary=[r['ordinary_cost']/1e4 for r in rows]
fig,ax=plt.subplots(figsize=(6.8,3.5),layout='constrained')
ax.plot(q,total,'o-',color='#396e96',label='总费用',lw=1.15)
ax.plot(q,ordinary,'s--',color='#bf913c',label='普通结算',lw=1.05)
ax.fill_between(q,ordinary,total,color='#bf913c',alpha=.16,label='紧急购电费')
ax.annotate(f'{total[2]:.2f}',(.6,total[2]),xytext=(0,9),textcoords='offset points',ha='center',fontsize=10)
ax.set(xticks=q,xlabel='误差准备分位',ylabel='评价期费用 / 万元',ylim=(1267,1342))
ax.legend(loc='upper center',ncol=3,frameon=False,fontsize=10,columnspacing=1,handlelength=1.5)
ax.grid(axis='y',color='#dddddd',linewidth=.5)
ax.set_axisbelow(True)
ax.spines[['top','right']].set_visible(False)
for ext in ('pdf','png'):
    kw={'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {'dpi':300}
    fig.savefig(base/f'fig/q3_final_quantile.{ext}',bbox_inches='tight',**kw)
plt.close(fig)
(base/'scripts/q3_quantile_manifest.json').write_text(json.dumps({
    'source':'scripts/derived_values.json','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'data_key':'q3_quantile_comparison','script':'scripts/draw_q3_quantile.py',
    'outputs':['fig/q3_final_quantile.pdf','fig/q3_final_quantile.png'],
    'scope':'Existing result visualization only; no new modeling or validation.'},ensure_ascii=False,indent=2),'utf-8')
print('Q3 quantile PDF and PNG generated from existing result data.')
