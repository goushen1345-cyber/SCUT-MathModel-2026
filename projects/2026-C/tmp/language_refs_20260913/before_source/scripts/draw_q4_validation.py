"""Redraw the existing Q4 figure, correcting only the evaluation-period label."""
from pathlib import Path
import json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
out=Path(__file__).resolve().parents[1]
source=out.parent/'scripts/derived_values.json'
d=json.loads(source.read_text('utf-8'))
plt.rcParams.update({'font.family':['Times New Roman','SimSun'],'font.size':11,'axes.titlesize':12,'axes.labelsize':11,'legend.fontsize':10,'axes.unicode_minus':False,'pdf.fonttype':42,'ps.fonttype':42,'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.8,'savefig.facecolor':'white','figure.facecolor':'white','axes.axisbelow':True})
BLUE='#396e96';GOLD='#bf913c'
fig,ax=plt.subplots(1,2,figsize=(10,3.5),layout='constrained',gridspec_kw={'wspace':.16})
tree=d['q4_tree_comparison'];delta=[r['difference_from_15'] for r in tree]
ax[0].plot([7,15,31],delta,color=BLUE,marker='o',lw=1.2);ax[0].axhline(0,color='black',lw=.7)
for n,y in zip([7,15,31],delta):ax[0].annotate(f'{y:+,.0f}',(n,y),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
ax[0].set(xticks=[7,15,31],xlabel='每棵树最多叶节点数',ylabel='相对15叶树费用变化 / 元',ylim=(-8200,3300),xlim=(4,34));ax[0].set_title('(a) 问题四-2：树复杂度')
qr=d['q4_quantile_comparison'];qs=[r['quantile'] for r in qr]
total=np.array([r['total_cost'] for r in qr])/1e4;ordinary=np.array([r['ordinary_settlement_cost'] for r in qr])/1e4
ax[1].plot(qs,total,'o-',color=BLUE,label='总费用',lw=1.15);ax[1].plot(qs,ordinary,'s--',color=GOLD,label='普通结算',lw=1.05)
ax[1].fill_between(qs,ordinary,total,color=GOLD,alpha=.16,label='紧急购电费')
ax[1].annotate(f'{total[2]:.2f}',(.6,total[2]),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
ax[1].set(xticks=qs,xlabel='误差准备分位',ylabel='评价期费用 / 万元',ylim=(1330,1414));ax[1].set_title('(b) 问题四-3：准备量与费用')
ax[1].legend(loc='upper center',ncol=3,frameon=False,fontsize=8.5,columnspacing=.65,handlelength=1.4)
for a in ax:a.grid(axis='y',color='#dddddd',lw=.5)
for ext in ('pdf','png'):fig.savefig(out/'fig'/f'q4_final_validation.{ext}',bbox_inches='tight',pad_inches=.07,**({'dpi':300} if ext=='png' else {'metadata':{'CreationDate':None,'ModDate':None}}))
plt.close(fig)
(out/'scripts/q4_validation_manifest.json').write_text(json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'change':'axis label 全年费用 -> 评价期费用; existing numbers unchanged'},ensure_ascii=False,indent=2),'utf-8')
