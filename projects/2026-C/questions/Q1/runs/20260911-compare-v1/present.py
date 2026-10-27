"""Summarize and plot the saved comparison, without running any model."""
from pathlib import Path
import argparse, csv, hashlib, json, os, sys
ROOT=Path(__file__).resolve().parent; PROJECT=ROOT.parents[3]
os.environ.setdefault('MPLCONFIGDIR',str(PROJECT/'tmp/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj): Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--figures',default='figures'); args=ap.parse_args()
    out=ROOT/'outputs'; figout=ROOT/args.figures
    assert not figout.exists(); figout.mkdir()
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    selected={r['candidate']:r for r in summary['comparison']}
    schedules={c:rows(out/'schedules'/f'{r["key"]}.csv') for c,r in selected.items()}
    p=np.array([float(r['price']) for r in schedules['04']]); t=np.arange(144)/6
    result={'savings':{},'events':{},'paired':{k:summary[k] for k in ['paired_improved','paired_worsened','paired_tied','matched_at_03_best']}}
    for a,b in [('03','04'),('10','04'),('03','10')]:
        saving=selected[a]['cost_yuan']-selected[b]['cost_yuan']
        result['savings'][f'{a}_to_{b}']={'yuan':saving,'percent':100*saving/selected[a]['cost_yuan']}
    peak=int(p.argmax()); result['price_peak']={'time':schedules['04'][peak]['start_label'],'price':float(p[peak])}
    for c,rr in schedules.items():
        hits=[int(r['end_minute']) for r in rr if float(r['state_end'])<=1200.00001 and int(r['end_minute'])>=960]
        result['events'][c]={'first_minimum_after_16_hour':min(hits)/60 if hits else None,
            'state_at_20':float(rr[119]['state_end']),
            'peak_purchase_kwh':float(rr[peak]['purchase_kwh']),
            'peak_discharge_kwh':float(rr[peak]['discharge']),
            'mean_purchase_price':selected[c]['cost_yuan']/selected[c]['purchase_kwh'],
            'cost_04_08':sum(float(r['cost_yuan']) for r in rr[24:48]),
            'cost_20_24':sum(float(r['cost_yuan']) for r in rr[120:144])}
    result['extra_grid_04_vs03_kwh']=selected['04']['purchase_kwh']-selected['03']['purchase_kwh']
    result['extra_loss_04_vs03_kwh']=selected['04']['loss_kwh']-selected['03']['loss_kwh']
    pairing=rows(out/'paired_comparison.csv'); result['paired_detail_at_10_best']=pairing[summary['selected_parameters']['10']['param_index']-1]
    # Source-independent rerun comparison, excluding timings and provenance timestamps.
    repro=ROOT/'reproduction'
    names=['input_mapping.csv','comparison.csv','paired_comparison.csv','four_hour_summary.csv']
    names += [str(p.relative_to(out)) for p in sorted((out/'schedules').glob('*.csv'))]
    result['reproduction']={n:sha(out/n)==sha(repro/n) for n in names}
    assert all(result['reproduction'].values())
    write(out/'interpretation.json',result)
    font=font_manager.findfont(font_manager.FontProperties(family='SimSun'),fallback_to_default=False)
    plt.rcParams.update({'font.family':'SimSun','font.size':11,'axes.labelsize':11,'axes.titlesize':12,
        'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
        'axes.unicode_minus':False,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
        'legend.frameon':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    names_cn={'03':'峰谷策略','04':'线性规划','10':'光伏预留策略'}
    colors={'03':'#b65a32','04':'#1f66a5','10':'#32805a'}
    styles={'03':'--','04':'-','10':':'}
    render_checks={}
    def save(fig,name):
        fig.canvas.draw()
        renderer=fig.canvas.get_renderer(); width,height=fig.canvas.get_width_height()
        clipped=[]
        for text in fig.findobj(matplotlib.text.Text):
            if not text.get_visible() or not text.get_text().strip(): continue
            bb=text.get_window_extent(renderer)
            if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > width+1 or bb.y1 > height+1:
                clipped.append(text.get_text())
        assert not clipped,(name,clipped)
        render_checks[name]={'visible_text_within_canvas':True,'checked_text_count':len(fig.findobj(matplotlib.text.Text))}
        fig.savefig(figout/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None})
        fig.savefig(figout/(name+'.png'),dpi=180); plt.close(fig)
    fig,axs=plt.subplots(3,1,figsize=(8.2,8.5),layout='constrained',sharex=True)
    fig.get_layout_engine().set(rect=(0,.045,1,.91))
    axs[0].step(np.r_[t,24],np.r_[p,p[-1]],where='post',color='#444444',lw=1.5)
    axs[0].set_ylabel('电价（元/kWh）'); axs[0].set_title('同一天，不同策略怎样安排电池和购电')
    axs[0].axvline(t[peak],color='#999999',lw=.8,ls=':')
    axs[0].annotate('当天最高价',xy=(t[peak],p[peak]),xytext=(16,p[peak]+.12),
        arrowprops={'arrowstyle':'->','color':'black'},fontsize=10)
    axs[0].set_ylim(0,max(p)+.3)
    for c in ['03','10','04']:
        rr=schedules[c]; ss=[float(rr[0]['state_start'])]+[float(r['state_end']) for r in rr]
        axs[1].plot(np.arange(145)/6,ss,label=names_cn[c],color=colors[c],ls=styles[c],lw=1.6)
        qq=np.array([float(r['purchase_kwh']) for r in rr])*6
        axs[2].step(np.r_[t,24],np.r_[qq,qq[-1]],where='post',label=names_cn[c],color=colors[c],ls=styles[c],lw=1.25)
    for bound in [1200,10800]: axs[1].axhline(bound,color='#888888',ls=':',lw=.8)
    axs[1].set_ylim(0,12000); axs[1].set_yticks([1200,6000,10800]); axs[1].set_ylabel('内部储电量（kWh）')
    axs[1].legend(ncol=3,loc='upper left'); axs[2].set_ylabel('外网购电功率（kW）'); axs[2].set_xlabel('时刻（时）')
    for ax in axs:
        ax.set_xlim(0,24); ax.set_xticks(range(0,25,2)); ax.grid(axis='y',alpha=.18)
    fig.text(.04,.012,'同一代表日；两种规则各选27组参数中费用最低者。首尾均为6000 kWh，充放效率各90%。',fontsize=9)
    save(fig,'01_daily_dispatch')
    scores=rows(out/'parameter_scores.csv')
    fig,ax=plt.subplots(figsize=(7.4,4.9),layout='constrained')
    fig.get_layout_engine().set(rect=(0,.13,1,.85))
    high_colors=['#2166ac','#27816c','#b95c2e']
    # The three tested low-price quantiles produce coincident paired differences.
    # Verify this before combining the redundant panels into one readable plot.
    for i in range(9):
        assert max(abs(float(pairing[i]['saving_yuan'])-float(pairing[i+offset]['saving_yuan'])) for offset in [9,18])<1e-6
    for hq,color in zip([.65,.75,.85],high_colors):
        group=[r for r in scores if r['candidate']=='03' and abs(float(r['low_quantile'])-.15)<1e-10 and abs(float(r['high_quantile'])-hq)<1e-10]
        x=[float(r['target_kwh']) for r in group]
        y=[float(pairing[int(r['param_index'])-1]['saving_yuan']) for r in group]
        ax.plot(x,y,marker='o',color=color,label=f'高价分位 {hq:.0%}',lw=1.6)
    ax.set_title('光伏预留主要改善充电目标偏高的规则组合')
    ax.set_xticks([6000,8400,10800]); ax.set_xlabel('基础充电目标（kWh）')
    ax.axhline(0,color='#777777',lw=.7); ax.grid(axis='y',alpha=.2)
    ax.set_ylabel('加入光伏预留后节省的费用（元）'); ax.legend(loc='upper left')
    ax.set_ylim(-150,2300); ax.set_yticks([0,500,1000,1500,2000])
    fig.text(.04,.052,'低价分位15%、25%、35%的配对结果重合；共27组中18组节费、9组不变。',fontsize=9)
    fig.text(.04,.015,'以上是同一代表日的参数比较，不代表全年或其他参数范围均有改善。',fontsize=9)
    save(fig,'02_matched_rule_comparison')
    write(figout/'manifest.json',dict(script=sha(__file__),summary=sha(out/'summary.json'),
        comparison=sha(out/'comparison.csv'),paired=sha(out/'paired_comparison.csv'),
        selected_schedules={c:sha(out/'schedules'/f'{r["key"]}.csv') for c,r in selected.items()},
        matplotlib=matplotlib.__version__,python=sys.version,font=font,render_checks=render_checks,
        outputs={p.name:sha(p) for p in sorted(figout.glob('*')) if p.is_file()}))
    print(json.dumps({k:v for k,v in result.items() if k!='reproduction'},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
