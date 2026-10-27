"""Plot verified saved costs only. Reproduce to a new --output directory."""
from pathlib import Path
import os, json, hashlib, argparse, warnings
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
warnings.filterwarnings('ignore',message='Pandas requires version')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

R=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(R/'figures-v1'))
args=parser.parse_args();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
font=Path('C:/Windows/Fonts/simsun.ttc');assert font.exists()
name=FontProperties(fname=str(font)).get_name()
plt.rcParams.update({'font.family':name,'font.size':12,'axes.unicode_minus':False,
    'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
    'svg.hashsalt':'q3-trial-20260911','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
summary=json.loads((R/'outputs/summary.json').read_text(encoding='utf-8'))
assert json.loads((R/'outputs/verification.json').read_text())['status']=='checks_completed'
d={x['label']:x for x in summary['annual']}
monthly=pd.read_csv(R/'interpretation/monthly_comparison.csv')
colors=['#4C78A8','#E7A35A'];files=[]
def finish(fig,stem):
    for ext in ['png','svg','pdf']:
        p=out/(stem+'.'+ext)
        meta={'Date':None} if ext=='svg' else ({'CreationDate':None,'ModDate':None} if ext=='pdf' else None)
        fig.savefig(p,dpi=200,bbox_inches='tight',facecolor='white',metadata=meta);files.append(p)
    plt.close(fig)

fig,(ax,lower)=plt.subplots(2,1,figsize=(9,8),gridspec_kw={'height_ratios':[1.15,1]},layout='constrained')
keys=['S1_raw','S2_fused','S3_tree','S4_margin'];x=np.arange(4)
ordinary=np.array([d[k]['ordinary_cost']/1e4 for k in keys]);emergency=np.array([d[k]['emergency_cost']/1e4 for k in keys])
ax.bar(x,ordinary,color=colors[0],label='普通结算（含调整）',width=.55)
ax.bar(x,emergency,bottom=ordinary,color=colors[1],label='紧急购电',width=.55)
for i,v in enumerate(ordinary+emergency):ax.text(i,v+17,f'{v:.2f}',ha='center',va='bottom')
ax.set_xticks(x,['直接预报','历史融合','树模型修正','融合＋准备量*']);ax.set_ylabel('2—12月费用 / 万元')
ax.set_ylim(0,1700);ax.legend(loc='upper center',ncol=2,frameon=False)
ax.text(.02,.96,'(a)',transform=ax.transAxes,va='top')
saving=monthly.saving_fused_vs_raw.to_numpy()/1e4
lower.bar(monthly.month,saving,color=np.where(saving>=0,colors[0],colors[1]),width=.62)
lower.axhline(0,color='black',linewidth=.8);lower.set_xticks(monthly.month);lower.set_xlabel('月份')
lower.set_ylabel('历史融合相对直接预报的节费 / 万元');lower.set_ylim(min(saving)-.35,max(saving)+.55)
for m,v in zip(monthly.month,saving):lower.text(m,v+(.06 if v>=0 else -.07),f'{v:.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=10)
lower.text(.02,.96,'(b) 正值省钱，负值增加费用',transform=lower.transAxes,va='top')
fig.supxlabel('* 1月选择为零准备量，因此与历史融合完全相同。334天同起点、同设备、各自跨日衔接。',fontsize=10)
finish(fig,'01_candidate_costs_and_months')

fig,ax=plt.subplots(figsize=(9,5.6),layout='constrained')
keys=['I0_zero_only','I1_no_new_forecast','S1_raw'];x=np.arange(3)
ordinary=np.array([d[k]['ordinary_cost']/1e4 for k in keys]);emergency=np.array([d[k]['emergency_cost']/1e4 for k in keys])
ax.bar(x,ordinary,color=colors[0],label='普通结算（含调整）',width=.5)
ax.bar(x,emergency,bottom=ordinary,color=colors[1],label='紧急购电',width=.5)
for i,v in enumerate(ordinary+emergency):ax.text(i,v+22,f'{v:.2f}',ha='center')
ax.set_xticks(x,['零点订电\n全天不改订单','允许日内调整\n不使用后发官方预报','允许日内调整\n使用新官方预报'])
ax.set_ylabel('2—12月费用 / 万元');ax.set_ylim(0,2000)
ax.legend(loc='upper right',ncol=2,frameon=False)
ax.annotate('',xy=(.0,1820),xytext=(1.,1820),arrowprops={'arrowstyle':'<->','color':'black'})
ax.text(.5,1835,'减少175.51万元',ha='center',va='bottom',fontsize=11)
ax.annotate('',xy=(1.,1710),xytext=(2.,1710),arrowprops={'arrowstyle':'<->','color':'black'})
ax.text(1.5,1725,'再减少21.78万元',ha='center',va='bottom',fontsize=11)
fig.supxlabel('原始预报方案的条件对照：先比较反馈与改约，再比较新增官方预报。\n两项差额依赖此对照顺序，不能当作各因素在所有策略下固定不变的价值。',fontsize=10)
finish(fig,'02_information_value')

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources=[R/'outputs/summary.json',R/'outputs/verification.json',R/'interpretation/monthly_comparison.csv']
manifest=dict(code_sha256=sha(__file__),sources={str(p.relative_to(R)):sha(p) for p in sources},
    outputs={p.name:sha(p) for p in files},matplotlib=matplotlib.__version__,font=name,font_file=str(font),
    dpi=200,colors='ordinary blue; emergency orange; monthly negative orange; text black',
    status='generated_pending_visual_inspection',not_embedded_in_manuscript=True)
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'outputs':[str(p) for p in files]},ensure_ascii=False))
