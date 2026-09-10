"""Figures consume locked EDA output only; do not run analysis/models."""
from pathlib import Path
import json,argparse,hashlib
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
from matplotlib.colors import ListedColormap
from matplotlib.ticker import NullFormatter

HERE=Path(__file__).resolve().parent
FONT=Path('C:/Windows/Fonts/simsun.ttc')
font_manager.fontManager.addfont(str(FONT))
mpl.rcParams.update({'font.family':'SimSun','font.size':10,'axes.unicode_minus':False,'pdf.fonttype':42,'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black','figure.facecolor':'white','axes.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})
COLORS=['#526f91','#a4b5c5','#438878','#aecaba','#9b755b']
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,default=HERE/'results/eda.json');ap.add_argument('--output',type=Path,default=HERE/'figures');args=ap.parse_args()
    d=json.loads(args.input.read_text(encoding='utf-8'));out=args.output;out.mkdir(parents=True,exist_ok=False)
    cats=d['categories'];types=d['land_types'];manifest=[]
    def save(fig,name):
        for fmt in ['pdf','png','svg']:fig.savefig(out/(name+'.'+fmt),dpi=200,bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None} if fmt=='pdf' else None)
        manifest.append({'name':name,'size_inches':list(fig.get_size_inches()),'input':str(args.input.resolve())});plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(8.2,3.4),layout='constrained')
    ls=d['land_stats'];y=np.arange(6)
    axs[0].barh(y,[x['area'] for x in ls],color='#a4b5c5',edgecolor='black',linewidth=.5)
    axs[0].set_yticks(y,types);axs[0].invert_yaxis();axs[0].set(xlabel='物理面积（亩）',title='(a) 各地类面积')
    for j,x in enumerate(ls):axs[0].text(x['area']+8,j,f"{x['area']:g}亩 / {x['count']}块",va='center',fontsize=9)
    axs[0].set_xlim(0,max(x['area'] for x in ls)*1.42)
    for j,t in enumerate(types):
        xs=sorted(x['area'] for x in d['lands'] if x['land_type']==t)
        offsets=np.linspace(-.15,.15,len(xs))
        axs[1].scatter(xs,j+offsets,c='white',edgecolors='black',s=22,linewidths=.65)
    axs[1].set_yticks(y,types);axs[1].invert_yaxis();axs[1].set_xscale('log');axs[1].set(xlabel='单地块面积（亩，对数轴）',title='(b) 54个地块的面积分布')
    axs[1].set_xticks([.6,1,5,10,50,100],['0.6','1','5','10','50','100']);axs[1].grid(axis='x',alpha=.25)
    save(fig,'01_land')
    fig,ax=plt.subplots(figsize=(8.2,8.8),layout='constrained')
    m=np.array(d['coverage_matrix']);ax.imshow(m,cmap=ListedColormap(['#ffffff','#d9d9d9','#438878']),vmin=0,vmax=2,aspect='auto',interpolation='nearest')
    ii,jj=np.where(m==2);ax.scatter(jj,ii,s=6,color='black',marker='o')
    labels=[a+'\n'+b for a,b in d['coverage_columns']]
    ax.set_xticks(range(10),labels,fontsize=10.5);ax.xaxis.tick_top();ax.set_yticks(range(41),[f'{i+1:02d} {n}' for i,n in enumerate(d['crop_names'])],fontsize=11.5)
    ax.set_xticks(np.arange(-.5,10,1),minor=True);ax.set_yticks(np.arange(-.5,41,1),minor=True);ax.grid(which='minor',color='#aaaaaa',linewidth=.4);ax.tick_params(which='minor',length=0)
    ax.legend(handles=[Patch(facecolor='white',edgecolor='black',label='规则不适用'),Patch(facecolor='#d9d9d9',edgecolor='black',label='适种但2023未记录'),Patch(facecolor='#438878',edgecolor='black',label='适种且2023有记录（点）')],loc='upper center',bbox_to_anchor=(.5,-.025),ncol=3,fontsize=9)
    save(fig,'02_coverage')
    fig,axs=plt.subplots(1,2,figsize=(8.2,3.5),layout='constrained')
    for ax,subset in zip(axs,[types[:4],types[4:]]):
        ys=np.arange(len(subset));left=np.zeros(len(subset))
        for ci,c in enumerate(cats):
            vals=[next(x for x in d['history_by_type'] if x['type']==t)['areas'][c] for t in subset]
            ax.barh(ys,vals,left=left,color=COLORS[ci],label=c,edgecolor='black',linewidth=.45,hatch=['//','','xx','..','\\\\'][ci]);left+=vals
        ax.set_yticks(ys,subset);ax.invert_yaxis();ax.set_xlabel('2023年累计播种面积（亩次）');ax.set_xlim(0,max(left)*1.12)
        for j,v in enumerate(left):ax.text(v+.015*max(left),j,f'{v:g}',va='center',fontsize=9)
    axs[0].set_title('(a) 露天地块');axs[1].set_title('(b) 大棚（独立横轴尺度）')
    handles,labels=axs[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=5,fontsize=9)
    save(fig,'03_history_structure')
    fig,axs=plt.subplots(1,3,figsize=(8.2,3.1),layout='constrained')
    broad=[('粮食',lambda x:x['category'].startswith('粮食')),('蔬菜',lambda x:x['category'].startswith('蔬菜')),('食用菌',lambda x:x['category']=='食用菌')]
    for ai,(ax,(name,cond)) in enumerate(zip(axs,broad)):
        xs=[x for x in d['parameters'] if cond(x)]
        coords={}
        for x in xs:coords.setdefault((x['yield'],x['cost']),[]).append(x)
        for (yy,cc),rs in coords.items():ax.scatter(yy,cc,s=24+len(rs)*7,facecolor=['#a4b5c5','#aecaba','#c6a78f'][ai],edgecolor='black',linewidth=.6)
        ax.set_xscale('log');ax.set_yscale('log');ax.set_xlim(80,20000);ax.set_ylim(200,15000);ax.set_title(f'{name}（{len(xs)}条参数）');ax.set_xlabel('亩产（斤/亩，对数轴）');ax.grid(alpha=.2)
        if ai==0:ax.set_ylabel('成本（元/亩，对数轴）')
    fig.get_layout_engine().set(rect=(0,.07,1,1));fig.text(.5,.01,'同坐标记录合并为圆点，圆面积随记录数增加；统计参数不视为独立观测。',ha='center',fontsize=9)
    save(fig,'04_yield_cost')
    fig,axs=plt.subplots(1,2,figsize=(8.2,8.7),sharey=True,layout='constrained');ch=d['crop_history'];ys=np.arange(41)
    colors=[COLORS[cats.index(x['category'])] for x in ch]
    axs[0].scatter([x['area'] for x in ch],ys,c=colors,edgecolor='black',linewidth=.5,s=23);axs[0].set_xscale('log');axs[0].set_xlabel('累计播种面积（亩次，对数轴）');axs[0].set_yticks(ys,[x['name'] for x in ch]);axs[0].invert_yaxis();axs[0].set_xticks([.1,1,10,100],['0.1','1','10','100']);axs[0].xaxis.set_minor_formatter(NullFormatter());axs[0].grid(axis='x',alpha=.2)
    axs[1].barh(ys,[x['plots'] for x in ch],color=colors,edgecolor='black',linewidth=.4);axs[1].set_xlabel('种植地块数（去重）');axs[1].set_xticks(range(0,11,2))
    for i,x in enumerate(ch):
        axs[0].text(x['area']*1.09,i,f"{x['area']:g}",va='center',fontsize=8)
        axs[1].text(x['plots']+.1,i,str(x['plots']),va='center',fontsize=8)
    axs[0].tick_params(axis='y',labelsize=11.5)
    for ax in axs:
        for txt in ax.texts:txt.set_fontsize(10.5)
    axs[0].set_xlim(.1,600);axs[1].set_xlim(0,max(x['plots'] for x in ch)+1.3);save(fig,'05_crop_history')
    fig,ax=plt.subplots(figsize=(8.2,8.7),layout='constrained')
    for i,x in enumerate(d['price_intervals']):
        offsets=np.linspace(-.18,.18,len(x['intervals'])) if len(x['intervals'])>1 else [0]
        for off,v in zip(offsets,x['intervals']):
            special=all(t['land_type']=='智慧大棚' and t['season']=='第二季' for t in v['sources'])
            ax.plot([v['low'],v['high']],[i+off]*2,color='black',lw=1.3,marker='|' if not special else 'o',markersize=3 if special else 7,linestyle='--' if special else '-')
    ax.set_yticks(ys,d['crop_names'],fontsize=11.5);ax.invert_yaxis();ax.set_xscale('log');ax.set_xlabel('原始销售价格区间（元/斤，对数轴）');ax.grid(axis='x',alpha=.2)
    ax.set_xticks([1,2,5,10,20,50,100],['1','2','5','10','20','50','100'])
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.plot([],[],color='black',marker='|',label='原表一般条件');ax.plot([],[],color='black',marker='o',ls='--',label='智慧大棚第二季')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.065),ncol=2,fontsize=9)
    save(fig,'06_price_intervals')
    (out/'manifest.json').write_text(json.dumps({'figures':manifest,'matplotlib':mpl.__version__,'font':str(FONT),'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
