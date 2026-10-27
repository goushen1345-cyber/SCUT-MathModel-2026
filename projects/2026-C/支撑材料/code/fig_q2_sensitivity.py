from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'figure_inputs/q2'
out=ROOT/'reproduced/plots/fig';out.mkdir(parents=True,exist_ok=True)
read=lambda p:pd.read_csv(p)
def save(fig,name):
 for ext in ('png','pdf'):fig.savefig(out/f'{name}.{ext}',dpi=300,bbox_inches='tight')
 plt.close(fig)
plt.rcParams.update({'font.family':'SimSun', 'font.size':10, 'axes.unicode_minus':False,
    'text.color':'black', 'axes.labelcolor':'black', 'xtick.color':'black', 'ytick.color':'black',
    'pdf.fonttype':42, 'axes.spines.top':False, 'axes.spines.right':False,
    'axes.axisbelow':True, 'savefig.facecolor':'white'})
BLUE, GREEN, ORANGE, RED = '#386a94', '#5f8768', '#c39243', '#b34e4a'
allrows=pd.concat([read(B/f'{p}/comparison.csv') for p in ['refinement','validation','supplement']]).set_index('variant')
base=allrows.loc['error-decay70']
choices=[['selected-q60','error-decay70','selected-q80'],['error-decay70','weighted-error','error-decay90']]
fig,axes=plt.subplots(1,2,figsize=(7.3,3.1),sharey=True)
sens=[]
for j,(keys,labels,title) in enumerate(zip(choices,[['0.6','0.7','0.8'],['0.7','0.8','0.9']],['分位位置 α（固定 β=0.7）','时间衰减 β（固定 α=0.7）'])):
    rows=allrows.loc[keys];xs=np.arange(3)
    ordinary=(rows.ordinary_cost-base.ordinary_cost)/1e4
    emergency=(rows.emergency_cost-base.emergency_cost)/1e4
    total=(rows.total_cost-base.total_cost)/1e4
    axes[j].bar(xs-.16,ordinary,width=.29,color=BLUE,label='普通电费变化')
    axes[j].bar(xs+.16,emergency,width=.29,color=ORANGE,label='紧急电费变化')
    axes[j].plot(xs,total,'ko-',lw=1,ms=3,label='总电费变化')
    axes[j].axhline(0,color='black',lw=.7)
    axes[j].set(xticks=xs,xticklabels=labels,xlabel=title,ylim=(-40,55))
    axes[j].grid(axis='y',alpha=.15)
    for x,y in zip(xs,total):axes[j].annotate(f'{y:.2f}',(x,y),xytext=(0,6),textcoords='offset points',ha='center',fontsize=8)
    for key,l in zip(keys,labels):sens.append({'parameter':'alpha' if j==0 else 'beta','value':l,'variant':key,**allrows.loc[key,['ordinary_cost','emergency_cost','total_cost']].to_dict()})
axes[0].set_ylabel('相对 α=β=0.7 的费用变化 / 万元')
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=3,frameon=False,fontsize=9)
fig.tight_layout(rect=(0,0,1,.88));save(fig,'sensitivity')
pd.DataFrame(sens).to_csv(out/'sensitivity_input.csv',index=False)
