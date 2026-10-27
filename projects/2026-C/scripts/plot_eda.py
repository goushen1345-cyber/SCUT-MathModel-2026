"""Draw paper candidate figures from saved descriptive EDA; no model fitting."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[1]/'tmp/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, dates as mdates
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parents[1]
BLUE='#2166ac'; ORANGE='#c85a17'; GREEN='#24775d'; PURPLE='#7851a9'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='audit/eda-v1')
    parser.add_argument('--output',default='paper/figures/eda-v2')
    args=parser.parse_args()
    source=(P/args.input).resolve(); out=(P/args.output).resolve()
    if not out.is_relative_to(P) or out.exists():
        raise ValueError('Use a new output directory within the project.')
    out.mkdir(parents=True)
    font=font_manager.findfont(font_manager.FontProperties(family='SimSun'),fallback_to_default=False)
    plt.rcParams.update({'font.family':'SimSun','font.size':11,'axes.titlesize':12,'axes.labelsize':11,
                        'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
                        'axes.edgecolor':'black','axes.unicode_minus':False,'pdf.fonttype':42,
                        'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white',
                        'axes.facecolor':'white','legend.frameon':False,'savefig.facecolor':'white'})
    ref=pd.read_csv(source/'reference_profile.csv')
    daily=pd.read_csv(source/'daily_summary.csv',parse_dates=['source_date'])
    monthly=pd.read_csv(source/'monthly_summary.csv')
    mp=pd.read_csv(source/'month_intraday.csv')
    intraday=pd.read_csv(source/'intraday_summary.csv')
    series=pd.read_csv(source/'time_series.csv',parse_dates=['source_date'])
    lags=pd.read_csv(source/'lag_correlations.csv')
    weekdays=pd.read_csv(source/'weekday_summary.csv')
    errors=pd.read_csv(source/'forecast_error_by_lead.csv')
    summary=json.loads((source/'summary.json').read_text(encoding='utf-8'))
    outputs=[]
    def save(fig,name,note):
        fig.text(.015,.015,note,fontsize=9,ha='left',va='bottom',color='black')
        fig.savefig(out/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None},bbox_inches=None)
        fig.savefig(out/(name+'.png'),dpi=180,bbox_inches=None)
        plt.close(fig)
        outputs.append(name)
    def time_axis(ax):
        ax.set_xlim(0,24); ax.set_xticks(range(0,25,4)); ax.set_xlabel('原表时间标签（时）')
        ax.grid(axis='y',alpha=.18)
    # 1. Representative input: power and price separated rather than an ambiguous dual axis.
    fig,axs=plt.subplots(3,1,figsize=(7.1,8.1),layout='constrained')
    fig.get_layout_engine().set(rect=(0,.05,1,.95))
    h=ref.source_minute/60
    axs[0].plot(h,ref.load_kw,color=ORANGE,label='小区负载',lw=1.7)
    axs[0].plot(h,ref.pv_forecast_kw,color=BLUE,label='光伏预测',lw=1.7,ls='--')
    axs[0].set(title='（a）代表日负载与光伏',ylabel='功率（kW）',ylim=(0,8500));axs[0].legend(ncol=2)
    axs[1].plot(h,ref.net_load_kw,color=GREEN,lw=1.5)
    axs[1].fill_between(h,ref.net_load_kw,0,where=ref.net_load_kw<0,color=BLUE,alpha=.2)
    axs[1].axhline(0,color='black',lw=.7)
    axs[1].set(title='（b）负载减去光伏：正值为待补功率，负值为光伏富余',ylabel='功率差（kW）')
    axs[2].plot(h,ref.price_yuan_per_kwh,color=PURPLE,lw=1.6)
    axs[2].set(title='（c）代表日电价',ylabel='电价（元/kWh）',ylim=(0,1.6))
    for ax in axs:time_axis(ax)
    save(fig,'01_reference_day','来源：附件1。点间连线仅辅助读图；尚未将功率积分为区间电量。')
    # 2. All dates are shown; monthly values are means, not totals.
    fig,axs=plt.subplots(3,1,figsize=(7.1,8.1),layout='constrained')
    fig.get_layout_engine().set(rect=(0,.05,1,.95))
    md=pd.to_datetime(['2025-%02d-15'%m for m in monthly.month])
    for ax,col,color,title,unit in zip(axs,['load_kw','pv_actual_kw','price_yuan_per_kwh'],[ORANGE,BLUE,PURPLE],['（a）负载：年内水平与逐日起伏','（b）光伏：年内水平与逐日起伏','（c）电价：年内水平与逐日起伏'],['平均功率（kW）','平均功率（kW）','平均电价（元/kWh）']):
        ax.plot(daily.source_date,daily[col],color=color,alpha=.3,lw=.7,label='每日采样均值')
        ax.plot(md,monthly[col],color=color,lw=1.8,marker='o',ms=4,label='每月采样均值')
        ax.set(title=title,ylabel=unit,ylim=(0,None),xlim=(pd.Timestamp('2025-01-01'),pd.Timestamp('2025-12-31')))
        ax.xaxis.set_major_locator(mdates.MonthLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
        ax.set_xlabel('2025年月');ax.grid(axis='y',alpha=.18);ax.legend(ncol=2,fontsize=9)
    save(fig,'02_year_and_month','来源：附件2、4。按原表归属日统计；平均功率不是日电量。仅一年，不能验证逐年重复。')
    # 3. Four evenly spaced months illustrate how the same clock changes across the year.
    fig,axs=plt.subplots(3,1,figsize=(7.1,8.1),layout='constrained')
    fig.get_layout_engine().set(rect=(0,.05,1,.95))
    for m,color,style in zip([1,4,7,10],[BLUE,GREEN,ORANGE,PURPLE],['-','--','-.',':']):
        frame=mp[mp.month==m]
        for ax,col in zip(axs,['load_kw','pv_actual_kw','net_load_kw']):
            ax.plot(frame.source_minute/60,frame[col],color=color,ls=style,lw=1.7,label=f'{m}月')
    for ax,title in zip(axs,['（a）同一时刻的月平均负载','（b）同一时刻的月平均光伏','（c）同一时刻的月平均功率差']):
        ax.set(title=title,ylabel='功率（kW）');time_axis(ax)
    axs[0].legend(ncol=4);axs[0].set_ylim(0,None);axs[1].set_ylim(0,None);axs[2].axhline(0,color='black',lw=.7)
    save(fig,'03_monthly_intraday','来源：附件2。展示1、4、7、10月的同标签均值；全年全部月份另见月度汇总。')
    # 4. Exact-day lags isolate weekly peaks; residuals remove month x clock mean only.
    fig,axs=plt.subplots(2,1,figsize=(7.1,6.4),layout='constrained')
    fig.get_layout_engine().set(rect=(0,.075,1,.925))
    for col,label,color,marker in [('load_kw','负载',ORANGE,'o'),('pv_actual_kw','光伏',BLUE,'s'),('price_yuan_per_kwh','电价',PURPLE,'^')]:
        g=lags[(lags.signal==col)&(lags.lag_hours%24==0)]
        for ax,metric in zip(axs,['raw_correlation','residual_correlation']):
            ax.plot(g.lag_hours/24,g[metric],label=label,color=color,marker=marker,lw=1.4,ms=4)
    for ax,title in zip(axs,['（a）原始序列：相隔几天的数据更相像','（b）扣除同月、同一时刻均值后，周规律是否仍存在']):
        ax.set(title=title,xlabel='相隔天数',ylabel='滞后相关系数',xticks=range(1,15),ylim=(-1.05,1.05))
        ax.axhline(0,color='black',lw=.6);ax.axvline(7,color='black',ls=':',alpha=.4);ax.grid(axis='y',alpha=.18)
    axs[0].legend(ncol=3)
    save(fig,'04_daily_weekly_patterns','来源：附件2、4。相关系数越接近1，变化越相似；去均值仅为事后诊断，不是预测拟合。')
    # 5. All 365 days and 144 labels; no smoothing or interpolation.
    mat=series.pivot(index='source_date',columns='source_minute',values='net_load_kw')
    fig,ax=plt.subplots(figsize=(7.1,7.7),layout='constrained');fig.get_layout_engine().set(rect=(0,.075,1,.925))
    im=ax.imshow(mat.values,aspect='auto',interpolation='nearest',cmap='RdBu_r',norm=TwoSlopeNorm(vmin=-7000,vcenter=0,vmax=7000),extent=(5/60,24+5/60,365,0))
    starts=[(pd.Timestamp(f'2025-{m:02d}-01')-pd.Timestamp('2025-01-01')).days+.5 for m in range(1,13)]
    ax.set(yticks=starts,yticklabels=[f'{m}月' for m in range(1,13)],xticks=range(0,25,4),xlim=(0,24+5/60),xlabel='原表时间标签（时）',ylabel='2025年原表归属日',title='全年负载与光伏的功率差')
    cb=fig.colorbar(im,ax=ax,pad=.025);cb.set_label('负载减去光伏（kW）')
    save(fig,'05_net_load_calendar','来源：附件2。红色：仍需外网或电池补充；蓝色：光伏富余。\n每格一个原始标签值；不是电池运行结果，也不是已计算的购电量。')
    # 6. Price variation and actual calendar grouping, not assumed working days.
    fig=plt.figure(figsize=(7.1,7.8),layout='constrained');fig.get_layout_engine().set(rect=(0,.06,1,.94))
    gs=fig.add_gridspec(2,2,height_ratios=[1.15,1]);a=fig.add_subplot(gs[0,:]);b=fig.add_subplot(gs[1,0]);c=fig.add_subplot(gs[1,1])
    a.fill_between(intraday.source_minute/60,intraday.price_yuan_per_kwh_p10,intraday.price_yuan_per_kwh_p90,color=PURPLE,alpha=.2,label='各日同标签P10—P90')
    a.plot(ref.source_minute/60,ref.price_yuan_per_kwh,color=PURPLE,lw=1.8,label='附件1电价')
    a.set(title='（a）相同时刻的电价，也会随日期变化',ylabel='电价（元/kWh）',ylim=(0,1.7));time_axis(a);a.legend(fontsize=9)
    names=['一','二','三','四','五','六','日'];colors=[ORANGE if i not in [4,5] else BLUE for i in range(7)]
    for ax,col,title,unit in [(b,'load_kw','（b）按实际星期分组的负载','平均功率（kW）'),(c,'price_yuan_per_kwh','（c）按实际星期分组的电价','平均电价（元/kWh）')]:
        ax.bar(range(7),weekdays[col],color=colors,width=.65)
        ax.set(xticks=range(7),xticklabels=names,xlabel='星期',ylabel=unit,title=title,ylim=(0,None));ax.grid(axis='y',alpha=.18)
    save(fig,'06_prices_and_weekdays','来源：附件1、2、4。P10—P90是实际样本分位范围，不是预测置信区间；按原日期计算星期。')
    # 7. Provided forecast quality is separate from dispatch and economic value.
    fig,axs=plt.subplots(2,1,figsize=(7.1,6.7),layout='constrained');fig.get_layout_engine().set(rect=(0,.085,1,.915))
    for scope,label,color,style in [('all','全部匹配样本',BLUE,'--'),('actual_positive','实际光伏大于0的样本',ORANGE,'-')]:
        g=errors[errors.scope==scope]
        axs[0].plot(g.lead_hours,g.mae_kw,label=label,color=color,ls=style,lw=1.6,marker='o',ms=3)
    axs[0].set(title='（a）提前越久，给定预报的绝对误差总体越大',xlabel='预报提前小时数',ylabel='平均绝对误差（kW）',xticks=[1,6,12,18,24],ylim=(0,None));axs[0].legend(fontsize=9);axs[0].grid(axis='y',alpha=.18)
    pair=summary['forecast']['same_target']['actual_positive']
    vals=[pair['initial_mae_kw'],pair['latest_mae_kw']]
    axs[1].bar([0,1],vals,color=[ORANGE,BLUE],width=.5)
    for i,v in enumerate(vals):axs[1].text(i,v+10,f'{v:.1f}',ha='center',color='black')
    axs[1].set(title=f'（b）对相同目标时刻比较：实际有光伏的{pair["n"]}组',xticks=[0,1],xticklabels=['零点原预报','目标时刻前最新日内预报'],ylabel='平均绝对误差（kW）',ylim=(0,500));axs[1].grid(axis='y',alpha=.18)
    axs[1].text(.98,.9,f'更新后仍有{pair["worse_fraction"]:.1%}的样本误差变大',transform=axs[1].transAxes,ha='right',fontsize=10)
    save(fig,'07_forecast_accuracy','来源：附件2、3，按相同整点标签匹配，不插值。\n下图比较当日7—24点的零点预报与目标前最新预报；误差改善不等于购电费用下降。')
    pdf_python='C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    merge_code='from pypdf import PdfWriter; import sys; w=PdfWriter(); [w.append(p) for p in sys.argv[2:]]; w.write(sys.argv[1]); w.close()'
    subprocess.run([pdf_python,'-c',merge_code,str(out/'eda_figures.pdf')]+[str(out/(name+'.pdf')) for name in outputs],check=True)
    record={'source_directory':str(source.relative_to(P)), 'input_sha256':{f.name:sha(f) for f in source.iterdir() if f.is_file()},
            'script_sha256':sha(Path(__file__)),'python':sys.version,'python_executable':sys.executable,'matplotlib':matplotlib.__version__,'pandas':pd.__version__,'numpy':np.__version__,'font':font,'figures':outputs,
            'outputs_sha256':{f.name:sha(f) for f in out.iterdir() if f.is_file()},'status':'generated_pending_visual_review','png_dpi':180,
            'reproduction_command':'E:/Anaconda/python.exe -X utf8 projects/2026-C/scripts/plot_eda.py --output tmp/eda-figures-reproduction'}
    (out/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'figures':outputs,'directory':str(out),'font':font},ensure_ascii=False))


if __name__=='__main__':
    main()
