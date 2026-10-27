"""Six Q2 exploratory figures from independently saved results, no model execution."""
from pathlib import Path
import argparse,hashlib,json,os
P=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(P/'tmp/matplotlib-q2'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import numpy as np

parser=argparse.ArgumentParser();parser.add_argument('--output',default='paper/figures/q2-exploration-v1');a=parser.parse_args()
O=P/'audit/q2-exploration-v1/outputs';F=(P/a.output).resolve()
assert F.is_relative_to(P) and not F.exists()
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for name,h in json.loads((O/'output_hashes.json').read_text(encoding='utf-8')).items():assert sha(O/name)==h
font=font_manager.findfont(font_manager.FontProperties(family='SimSun'),fallback_to_default=False)
plt.rcParams.update({'font.family':'SimSun','font.size':11,'axes.titlesize':12,'axes.labelsize':11,
 'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black','axes.edgecolor':'black',
 'axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,
 'figure.facecolor':'white','axes.facecolor':'white','legend.frameon':False,'savefig.facecolor':'white'})
B='#2166ac';R='#bd5414';G='#23806c';V='#7651a8';F.mkdir(parents=True);entries=[]
def read(name,**kw):return pd.read_csv(O/name,**kw)
def save(fig,name,note):
    fig.get_layout_engine().set(rect=(0,.08,1,.90))
    fig.text(.025,.012,note,fontsize=9,va='bottom',color='black')
    fig.canvas.draw();renderer=fig.canvas.get_renderer();W,H=fig.canvas.get_width_height()
    outside=[];not_drawn_ticks=set()
    for ax in fig.axes:
        for axis in (ax.xaxis,ax.yaxis):
            lo,hi=sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                if not lo<=tick.get_loc()<=hi:
                    not_drawn_ticks.update((id(tick.label1),id(tick.label2)))
    for text in fig.findobj(matplotlib.text.Text):
        if not text.get_visible() or not text.get_text() or id(text) in not_drawn_ticks:continue
        box=text.get_window_extent(renderer)
        if box.x0< -2 or box.y0< -2 or box.x1>W+2 or box.y1>H+2:outside.append(text.get_text())
    assert not outside,outside
    fig.savefig(F/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None})
    fig.savefig(F/(name+'.png'),dpi=300)
    plt.close(fig);entries.append(name)
daily=read('daily.csv',parse_dates=['date']);monthly=read('monthly.csv');week=read('weekday.csv');curves=read('weekday_curves.csv')
fig,axs=plt.subplots(2,1,figsize=(8,7),layout='constrained')
axs[0].plot(monthly.month,monthly.daily_mean_load_kwh/1000,'o-',color=R,label='日均负载')
axs[0].plot(monthly.month,monthly.daily_mean_pv_kwh/1000,'s--',color=B,label='日均光伏')
axs[0].set(title='（a）不同月份，需要用电和能够发电的水平不同',ylabel='日均电量（MWh）',xticks=range(1,13));axs[0].legend(ncol=2)
axs[1].bar(monthly.month,monthly.daily_mean_direct_pv_kwh/1000,color=B,label='同时段直接供负载')
axs[1].bar(monthly.month,monthly.daily_mean_surplus_kwh/1000,bottom=monthly.daily_mean_direct_pv_kwh/1000,color=G,label='超过当时负载的光伏')
axs[1].set(title='（b）发电多出来的部分仍需要储能接住',ylabel='日均光伏电量（MWh）',xlabel='2025年月',xticks=range(1,13),ylim=(0,85));axs[1].legend(ncol=2,loc='upper left')
for ax in axs:ax.grid(axis='y',alpha=.18)
save(fig,'01_monthly_supply','本项目附件2重新计算；按区间起点归真实日期。1月仅含2—31日，其余为完整月。\n光伏富余不是最终弃光，尚未模拟储能。')
fig,axs=plt.subplots(2,1,figsize=(8,7),layout='constrained')
colors=[G if d in [4,5] else B for d in week.weekday]
axs[0].bar(week.weekday,week.daily_mean_load_kwh/1000,color=colors)
axs[0].set(title='（a）数据中的低用电日是周五、周六',xticks=range(7),xticklabels=['一','二','三','四','五','六','日'],xlabel='星期',ylabel='日均负载（MWh）',ylim=(0,140))
for x,y in zip(week.weekday,week.daily_mean_load_kwh/1000):axs[0].text(x,y+2,f'{y:.1f}',ha='center',fontsize=10)
for days,color,label,ls in [([4,5],G,'周五、周六','--'),([0,1,2,3,6],B,'其余五天','-')]:
    c=curves[curves.weekday.isin(days)].groupby('minute').load_kw.mean()
    axs[1].step(np.r_[c.index/60,24],np.r_[c.values,c.values[-1]],where='post',color=color,ls=ls,label=label)
axs[1].set(title='（b）星期差异贯穿多个用电时段',xlim=(0,24),xticks=range(0,25,4),xlabel='区间起点（时）',ylabel='平均负载功率（kW）');axs[1].legend()
for ax in axs:ax.grid(axis='y',alpha=.18)
save(fig,'02_weekday_structure','范围：2025年1月2日—12月31日，每个星期类别均52天。\n按实际日期分组；不把低用电日擅自改成通常的周末。')
interval=read('intervals.csv',parse_dates=['interval_start']);ev=interval[(interval.interval_start>='2025-02-01')&(interval.interval_start<'2026-01-01')]
dd=daily[daily.date>='2025-02-01']
fig,axs=plt.subplots(2,1,figsize=(8,7),layout='constrained')
axs[0].hist(dd.surplus_kwh/1000,bins=22,color=G,edgecolor='white')
axs[0].axvline(9600/.9/1000,color='black',ls='--',label='一次从下限充到上限：10.67 MWh')
axs[0].set(title='（a）一天的富余光伏可能多于电池一次能装入的电量',xlabel='每日富余光伏（MWh）',ylabel='天数');axs[0].legend(fontsize=10)
for vals,color,label in [(ev.net_kw[ev.net_kw>0],R,'光伏直供后的负载缺口'),(-ev.net_kw[ev.net_kw<0],G,'光伏直供后的发电富余')]:
    x=np.sort(vals);axs[1].plot(x,np.arange(1,len(x)+1)/len(x)*100,color=color,label=label)
axs[1].axvline(5000,color='black',ls='--',label='电池充/放功率上限')
axs[1].set(title='（b）电池不仅会装满，也可能来不及充放',xlabel='功率（kW）',ylabel='不超过该功率的时段比例（%）',ylim=(0,101));axs[1].legend(fontsize=10)
for ax in axs:ax.grid(axis='y',alpha=.18)
save(fig,'03_storage_limits','范围：2—12月334天；10.67 MWh是一次充满的外侧电量，绝非每日充电上限。\n高于放电功率的缺口需要外网供电，但不等于一定紧急购电。')
m=read('history_reference_metrics.csv');names=['lag1','lag7','mean3','mean7','mean14','mean28','weekday4'];labels=['昨天同刻','上周同日','近3天均值','近7天均值','近14天均值','近28天均值','近4个同星期']
fig,axs=plt.subplots(1,2,figsize=(10,6),layout='constrained',sharey=True)
for ax,variable,title in zip(axs,['load','pv'],['负载','光伏']):
    for delta,span,color,label in [(-.16,'Feb-Jun',B,'2—6月'),(.16,'Jul-Dec',R,'7—12月')]:
        vals=m[(m.variable==variable)&(m.span==span)].set_index('method').loc[names,'mae_kw']
        ax.barh(np.arange(7)+delta,vals,height=.3,color=color,label=label)
    ax.set(title=title+'：固定历史参照的平均绝对误差',xlabel='平均绝对误差（kW）',yticks=range(7),yticklabels=labels);ax.invert_yaxis() if variable=='load' else None
    ax.set_ylim(7.4,-.6)
    ax.grid(axis='x',alpha=.18);ax.legend(loc='lower left',ncol=2)
save(fig,'04_history_references','七种参照全程固定，只使用当天零点前已经结束的历史区间；未按这两段结果挑选设置。\n光伏此图含夜间；发电时段单独指标见报告，误差小不直接等于购电费低。')
corr=read('error_autocorrelation.csv');wins=read('six_hour_error_windows.csv')
fig,axs=plt.subplots(2,1,figsize=(8,7),layout='constrained')
for key,color,label,ls in [('week1_pv7',B,'上周负载＋7日光伏','-'),('week4_pv7',R,'4周同日负载＋7日光伏','--')]:
    c=corr[corr.pair==key];axs[0].plot(c.lag_minutes/60,c.correlation,marker='o',color=color,ls=ls,label=label)
    x=np.sort(wins[wins.pair==key].signed_error_kwh/1000);axs[1].plot(x,np.arange(1,len(x)+1)/len(x)*100,color=color,ls=ls,label=label)
axs[0].set(title='（a）相邻时段的供需判断偏差具有持续性',xlabel='间隔（小时）',ylabel='净供需误差相关系数',ylim=(0,1));axs[0].legend(fontsize=10)
axs[1].axvline(0,color='black',lw=.8);axs[1].axhline(95,color='gray',ls=':',label='95%分位位置')
axs[1].set(title='（b）连续6小时的累计低估可能达到数千度电',xlabel='6小时有符号累计误差（MWh；正值表示低估需求）',ylabel='累计比例（%）',ylim=(0,101));axs[1].legend(fontsize=10)
for ax in axs:ax.grid(axis='y',alpha=.18)
save(fig,'05_error_continuity','范围：2—12月；净供需误差＝实际（负载－光伏）－历史参照（负载－光伏）。\n6小时窗口可重叠且不跨日；这是误差诊断，不是紧急购电量或推荐备用量。')
specified=read('specified_days.csv',parse_dates=['interval_start','date'])
fig,axs=plt.subplots(2,2,figsize=(10,6.8),layout='constrained',sharex=True,sharey=True)
for ax,(date,d) in zip(axs.ravel(),specified.groupby('date')):
    h=d.minute/60
    ax.plot(h,d.net_kw,color=B,label='实际净供需')
    ax.plot(h,d.week1_pv7_reference_net_kw,color=R,ls='--',label='历史参照')
    ax.axhline(0,color='black',lw=.7)
    ax.set(title=date.strftime('%m月%d日'),xlim=(0,24),xticks=range(0,25,6),xlabel='区间起点（时）',ylabel='净供需功率（kW）');ax.grid(axis='y',alpha=.18)
axs[0,0].legend(fontsize=10)
save(fig,'06_specified_days','题目指定的4天全部展示；历史参照固定为上周同日负载＋近7天光伏均值。\n正值需外网/电池补足，负值有光伏富余；不是已执行的购电或储能方案。')
manifest={'source_directory':str(O.relative_to(P)),'script_sha256':sha(Path(__file__)),
 'source_sha256':{f.name:sha(f) for f in O.glob('*.csv')},'matplotlib':matplotlib.__version__,'font':font,
 'figures':entries,'dpi':300,'output_sha256':{f.name:sha(f) for f in sorted(F.iterdir()) if f.is_file()},
 'all_text_within_canvas':True,'visual_qa':'pending actual inspection','models_run':0}
(F/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'figures':entries,'directory':str(F),'matplotlib':matplotlib.__version__},ensure_ascii=False))
