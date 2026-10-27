"""Render only existing Q2 results; no training, planning or simulation."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
B = PROJECT / 'questions/Q2/runs/20260911-annual-validation-v1'
T = PROJECT / 'questions/Q2/runs/20260911-targeted-validation-v1'
plt.rcParams.update({'font.family':'SimSun', 'font.size':10, 'axes.unicode_minus':False,
    'text.color':'black', 'axes.labelcolor':'black', 'xtick.color':'black', 'ytick.color':'black',
    'pdf.fonttype':42, 'axes.spines.top':False, 'axes.spines.right':False,
    'axes.axisbelow':True, 'savefig.facecolor':'white'})
BLUE, GREEN, ORANGE, RED = '#386a94', '#5f8768', '#c39243', '#b34e4a'
INPUTS = [B/'delivery_data/summary.json',B/'delivery_data/selected_monthly.csv',
 B/'delivery_data/selected_execution.csv.gz',B/'delivery_data/paired_days.csv',
 B/'annual/comparison.csv',B/'refinement/comparison.csv',B/'validation/comparison.csv',
 B/'supplement/comparison.csv',B/'delivery_data/specified_table1.csv',
 B/'delivery_data/specified_table2.csv',B/'delivery_data/specified_table3.csv',
 T/'analysis/scenario_comparison.csv',T/'analysis/tails.json',T/'analysis/group_paired.csv',
 B/'deliverables/result2.xlsx',PROJECT/'data/prepared-v1/actual_power.csv',
 PROJECT/'data/prepared-v1/day_reference.csv',
 PROJECT/'questions/Q1/runs/20260911-close-v1/outputs/summary.json',
 PROJECT/'questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return pd.read_csv(p)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=HERE/'figures');args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    fingerprints={str(p.relative_to(PROJECT)):sha(p) for p in INPUTS}
    guard=HERE/'source_manifest.json'
    if guard.exists():
        assert json.loads(guard.read_text('utf-8'))['source_sha256']==fingerprints,'Source changed'
    else:
        guard.write_text(json.dumps({'scope':'read existing results only','source_sha256':fingerprints},ensure_ascii=False,indent=2),'utf-8')
    outputs=[]
    def save(fig,name):
        for ext in ('pdf','png'):
            p=out/f'{name}.{ext}'
            kw={'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}
            fig.savefig(p,dpi=300,bbox_inches='tight',**kw);outputs.append(p)
        plt.close(fig)
    summary=json.loads((B/'delivery_data/summary.json').read_text('utf-8'))
    month=read(B/'delivery_data/selected_monthly.csv')
    paired=read(B/'delivery_data/paired_days.csv')
    paired['month']=pd.to_datetime(paired.decision_date).dt.month
    savings=paired.groupby('month').saving.sum().reindex(month.month)
    fig,axes=plt.subplots(2,1,figsize=(7.3,4.2),sharex=True,gridspec_kw={'height_ratios':[1.45,1]})
    axes[0].bar(month.month,month.ordinary_cost/1e4,color=BLUE,width=.63,label='普通电费')
    axes[0].bar(month.month,month.emergency_cost/1e4,bottom=month.ordinary_cost/1e4,color=ORANGE,width=.63,label='紧急电费')
    axes[0].set(ylabel='近期加权方案费用 / 万元',ylim=(0,month.total_cost.max()/1e4*1.25))
    axes[0].legend(ncol=2,loc='upper left',frameon=False)
    axes[1].bar(month.month,savings.values/1e4,color=GREEN,width=.63)
    axes[1].set(ylabel='相对等权方案节省 / 万元',xlabel='月份',xticks=month.month,ylim=(0,19))
    axes[1].axhline(0,color='black',lw=.7)
    for ax in axes:ax.grid(axis='y',alpha=.17)
    fig.tight_layout();save(fig,'monthly_cost')
    pd.DataFrame({'month':month.month,'ordinary_cost':month.ordinary_cost,'emergency_cost':month.emergency_cost,'saving_vs_uniform':savings.values}).to_csv(out/'monthly_input.csv',index=False)

    execution=read(B/'delivery_data/selected_execution.csv.gz')
    days=['2025-03-20','2025-06-21']
    selected=execution[execution.date.isin(days)].copy()
    selected.to_csv(out/'specified_days_input.csv',index=False)
    fig,axs=plt.subplots(3,2,figsize=(7.3,5.7),sharex=True,gridspec_kw={'height_ratios':[1,1,1]})
    for j,date in enumerate(days):
        df=selected[selected.date==date].sort_values('slot');assert len(df)==144
        x=df.slot.to_numpy()/6
        axs[0,j].step(x,df.load_kw,where='post',color='black',lw=1,label='实际负载')
        axs[0,j].step(x,df.pv_kw,where='post',color=GREEN,lw=1.2,label='实际光伏')
        axs[0,j].step(x,df.order_kwh*6,where='post',color=BLUE,lw=.9,alpha=.8,label='计划购电')
        axs[0,j].set_title('3月20日' if j==0 else '6月21日',fontsize=11)
        axs[0,j].set_ylim(0,max(df.load_kw.max(),df.pv_kw.max(),df.order_kwh.max()*6)*1.4)
        s=np.r_[df.storage_start_kwh.iloc[0],df.storage_end_kwh]
        axs[1,j].plot(np.arange(145)/6,s,color=BLUE,lw=1.3)
        for bound in (1200,10800):axs[1,j].axhline(bound,color='#666666',ls='--',lw=.7)
        axs[1,j].set(ylim=(0,12000),yticks=[1200,6000,10800])
        gap=np.maximum((df.load_kw-df.pv_kw)/6-df.order_kwh,0)
        axs[2,j].fill_between(x,gap,step='post',color='#d7d7d7',label='计划电之后的缺口')
        axs[2,j].step(x,df.discharge_kwh,where='post',color=BLUE,lw=1,label='电池补充')
        axs[2,j].bar(x,df.emergency_kwh,width=1/6,align='edge',color=RED,label='紧急购电')
        axs[2,j].set(xlim=(0,24),xticks=np.arange(0,25,4),xlabel='时刻 / h',ylim=(0,1100))
        for ax in axs[:,j]:ax.grid(axis='y',alpha=.15)
    axs[0,0].set_ylabel('功率 / kW');axs[1,0].set_ylabel('内部储电量 / kWh');axs[2,0].set_ylabel('每10分钟电量 / kWh')
    axs[0,0].legend(loc='upper left',ncol=3,fontsize=8,frameon=False,columnspacing=.7,handlelength=1.3)
    axs[2,0].legend(loc='upper left',fontsize=8,frameon=False,ncol=2,columnspacing=.7,handlelength=1.2)
    axs[2,0].annotate('20:40 紧急补购',xy=(20.75,329.52),xytext=(11,610),fontsize=8,
        arrowprops={'arrowstyle':'->','color':'black','lw':.6})
    axs[2,1].text(.05,.82,'全天无紧急购电',transform=axs[2,1].transAxes,fontsize=9)
    fig.tight_layout(h_pad=1,w_pad=1);save(fig,'specified_days')

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

    if out==HERE/'figures':
        tex=HERE/'tables';tex.mkdir(exist_ok=True)
        def write(name,s): (tex/name).write_text(s.rstrip()+'\n','utf-8')
        def row(vals):return ' & '.join(vals)+r' \\'+'\n'
        models=read(B/'annual/comparison.csv').set_index('variant')
        names={'T1':'历史分别预测，无误差准备','T2':'分别岭回归，无误差准备','T3':'分别提升树，无误差准备','T4':'历史分别预测，等权误差准备'}
        body=''
        for k in ['T1','T2','T3','T4']:
            r=models.loc[k];body+=row([names[k]]+[f'{r[c]/1e4:.2f}' for c in ['ordinary_cost','emergency_cost','total_cost']])
        body+=row([r'\textbf{历史分别预测，近期加权准备}']+[r'\textbf{'+f'{base[c]/1e4:.2f}'+'}' for c in ['ordinary_cost','emergency_cost','total_cost']])
        write('comparison.tex',body)
        t1=read(B/'delivery_data/specified_table1.csv');body=''
        for col,label in [(c,c[:11]) for c in t1.columns if c.endswith('_plan_kwh')]+[
            ('plan_daily_kwh','全天计划购电量'),('emergency_daily_kwh','全天紧急购电量'),
            ('all_purchased_daily_kwh','全天购电合计'),('ordinary_fee','普通电费 / 元'),
            ('emergency_fee','紧急电费 / 元'),('total_fee','总电费 / 元')]:
            body+=row([label]+[f'{v:.2f}' for v in t1[col]])
        write('purchase.tex',body)
        t2=read(B/'delivery_data/specified_table2.csv');body=''
        for interval in t2.interval.unique():
            rows=t2[t2.interval==interval]
            for col,label in [('charge_kwh','充电'),('discharge_kwh','放电')]:
                body+=row([interval if label=='充电' else '',label]+[f'{v:.2f}' for v in rows[col]])
        r=t2.groupby('date',sort=False).first()
        body+=row([r'\multicolumn{2}{l}{0:00 内部储电量}']+[f'{v:.2f}' for v in r.day_start_kwh])
        body+=row([r'\multicolumn{2}{l}{24:00 内部储电量}']+[f'{v:.2f}' for v in r.day_end_kwh])
        write('storage.tex',body)
        t3=read(B/'delivery_data/specified_table3.csv')
        write('emergency.tex',''.join(row([r.date[5:].replace('-','/'),r.interval,f'{r.kwh:.2f}',f'{r.cost:.2f}']) for r in t3.itertuples()))
    manifest={'source_sha256':fingerprints,'script_sha256':sha(Path(__file__)),
        'matplotlib':matplotlib.__version__,'font':'SimSun','dpi':300,
        'outputs':{p.name:sha(p) for p in outputs},'scope':'No new model computation'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'figures':len(outputs),'source_files':len(INPUTS),'output':str(out)},ensure_ascii=False))
if __name__=='__main__':main()
