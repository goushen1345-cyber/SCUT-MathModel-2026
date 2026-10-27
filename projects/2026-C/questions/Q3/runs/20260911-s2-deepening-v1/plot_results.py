"""Generate one paper-candidate result figure from verified summaries."""
from pathlib import Path
import os, json, hashlib, argparse
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
R=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(R/'figures-v1'));args=ap.parse_args();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
assert json.loads((R/'outputs/verification.json').read_text())['status']=='checks_completed'
sens=pd.read_csv(R/'analysis/quantile_sensitivity.csv');mon=pd.read_csv(R/'analysis/monthly.csv')
font=Path('C:/Windows/Fonts/simsun.ttc');name=FontProperties(fname=str(font)).get_name()
plt.rcParams.update({'font.family':name,'font.size':11,'axes.unicode_minus':False,'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black','svg.hashsalt':'q3-s2-deepening-v1','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
fig,(ax,bx)=plt.subplots(2,1,figsize=(8.7,7.3),gridspec_kw={'height_ratios':[1,1]},layout='constrained')
x=np.arange(len(sens));ordinary=sens.ordinary_cost/1e4;emergency=sens.emergency_cost/1e4
ax.bar(x,ordinary,color='#4C78A8',width=.55,label='普通结算（含调整）');ax.bar(x,emergency,bottom=ordinary,color='#E7A35A',width=.55,label='紧急购电')
for i,total in enumerate((sens.total_cost/1e4)):ax.text(i,total+7,f'{total:.2f}',ha='center',fontsize=10)
ax.set_xticks(x,[f'{q:.2f}' for q in sens['quantile']]);ax.set_xlabel('近期净需求误差的分位位置');ax.set_ylabel('2—12月费用 / 万元');ax.set_ylim(0,1550);ax.legend(frameon=False,ncol=2,loc='upper center');ax.text(.01,.96,'(a)',transform=ax.transAxes,va='top')
saving=mon.saving_vs_baseline/1e4;bx.bar(mon.month,saving,color=np.where(saving>=0,'#4C78A8','#E7A35A'),width=.62);bx.axhline(0,color='black',linewidth=.8)
for m,val in zip(mon.month,saving):bx.text(m,val+(.08 if val>=0 else -.08),f'{val:.2f}',ha='center',va='bottom' if val>=0 else 'top',fontsize=9)
bx.set_xticks(mon.month);bx.set_xlabel('月份');bx.set_ylabel('深化方案相对原方案2的节费 / 万元');bx.text(.01,.96,'(b) 正值省钱，负值增加费用',transform=bx.transAxes,va='top')
fig.supxlabel('均采用方案2的光伏融合预测；误差日期权重每天乘0.7。上图只改变准备量分位，下图采用0.65分位。',fontsize=10)
files=[]
for ext in ['png','svg','pdf']:
    p=out/('01_allowance_sensitivity_and_months.'+ext);meta={'Date':None} if ext=='svg' else ({'CreationDate':None,'ModDate':None} if ext=='pdf' else None)
    fig.savefig(p,dpi=300,bbox_inches='tight',facecolor='white',metadata=meta);files.append(p)
plt.close(fig)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources=[R/'analysis/quantile_sensitivity.csv',R/'analysis/monthly.csv',R/'outputs/verification.json']
(out/'manifest.json').write_text(json.dumps(dict(code_sha256=sha(__file__),sources={str(p.relative_to(R)):sha(p) for p in sources},outputs={p.name:sha(p) for p in files},matplotlib=matplotlib.__version__,font=name,font_file=str(font),dpi=300,status='generated_pending_visual_inspection',not_embedded=True),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'outputs':[str(p) for p in files]},ensure_ascii=False))
