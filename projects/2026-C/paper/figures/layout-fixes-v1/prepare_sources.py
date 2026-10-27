"""Derive three figure-only scripts from the original Matplotlib sources.

Only spacing, legend/annotation placement and export settings are changed.
Saved research outputs remain read-only; no model or simulator is invoked.
"""
from pathlib import Path
import textwrap

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
Q1 = PROJECT / 'questions/Q1/runs/20260911-compare-v1'
Q3 = PROJECT / 'questions/Q3/runs/20260911-parameter-interpretability-v1'
PAPER = PROJECT / 'paper/q3_manuscript_v2'

common = '''from pathlib import Path
import json, csv, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
plt.rcParams.update({'font.family':'SimSun','font.size':10,'axes.unicode_minus':False,
 'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black',
 'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
 'axes.axisbelow':True,'savefig.facecolor':'white','legend.frameon':False})
def save(fig, name):
    fig.canvas.draw()
    for ext in ('pdf','png'):
        kw = {'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {}
        fig.savefig(HERE/f'{name}.{ext}',dpi=300,bbox_inches='tight',**kw)
    fig.savefig(HERE/f'{name}_preview.png',dpi=120,bbox_inches='tight')
    plt.close(fig)
'''

# Q3 specified dates: retain the exact date-selection and plotted-array expressions.
source = (PAPER / 'prepare.py').read_text('utf-8')
block = textwrap.dedent(source[source.index('    # Two specified dates:'):source.index('    copy_sources =')])
block = block[:block.index('for extension in ("pdf", "png"):')]
block = block.replace('fig, axes = plt.subplots(3, 2, figsize=(7.3, 5.8), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1]})', '''fig = plt.figure(figsize=(8.8, 8.1))
gs = fig.add_gridspec(5, 2, height_ratios=[.16, 1, 1, .16, 1],
                     left=.09, right=.98, bottom=.075, top=.98, hspace=.40, wspace=.28)
axes = np.array([[fig.add_subplot(gs[r, c]) for c in range(2)] for r in (1,2,4)])
legend_top = fig.add_subplot(gs[0,:]); legend_top.axis('off')
legend_bottom = fig.add_subplot(gs[3,:]); legend_bottom.axis('off')''')
block = block.replace('axes[0,0].legend(loc="upper left", ncol=2, fontsize=8, frameon=False, columnspacing=.8)', '''handles, labels = axes[0,0].get_legend_handles_labels()
legend_top.legend(handles, labels, loc='center', ncol=4, fontsize=10, columnspacing=2)''')
block = block.replace('axes[2,0].legend(loc="upper left", ncol=2, fontsize=8, frameon=False, columnspacing=.8)', '''handles, labels = axes[2,0].get_legend_handles_labels()
legend_bottom.legend(handles, labels, loc='center', ncol=3, fontsize=10, columnspacing=2)''')
block = block.replace('fig.tight_layout(h_pad=1, w_pad=1)', '''for axis in axes[:2,:].ravel():
    axis.set(xlim=(0,24), xticks=np.arange(0,25,4))
    axis.tick_params(labelbottom=False)
save(fig, '01_Q3_specified_days')''')
setup = '''
BASE = PROJECT/'questions/Q3/runs/20260911-four-candidates-v1'
PARAM = PROJECT/'questions/Q3/runs/20260911-parameter-interpretability-v1'
SELECTED = 'M_q60_b070_w28_h03'
trace = dict(np.load(PARAM/f'outputs/strategies/{SELECTED}.npz'))
sources = dict(np.load(BASE/'outputs/sources.npz'))
actual = sources['actual']
days = trace['days'].astype(int)
q0, execution = trace['q0'], trace['execution']
qf = trace['versions'][:,3]
dates = pd.to_datetime('2025-01-01') + pd.to_timedelta(days, unit='D')
slot_map = {str(date.date()): i for i,date in enumerate(dates)}
chosen_dates = ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
BLUE, GREEN, RED, GREY = '#386a94','#5f8768','#b34e4a','#777777'
'''
(HERE/'draw_specified_days.py').write_text(common+setup+block, 'utf-8')

# Q3 parameter figure: keep the original filters, values, labels and four panels.
source = (Q3/'plot.py').read_text('utf-8')
source = source.replace('R = Path(__file__).resolve().parent', "HERE = Path(__file__).resolve().parent\nR = HERE.parents[2] / 'questions/Q3/runs/20260911-parameter-interpretability-v1'")
source = source.replace('OUT = R / "figures-v1"', 'OUT = HERE')
source = source.replace('figsize=(10.8, 7.4)', 'figsize=(11.2, 8.2)')
source = source.replace('xytext=(0, -22)', 'xytext=(0, 12)')
source = source.replace('ax.set_title("(a) 多准备与紧急补购的取舍")', 'ax.set_title("(a) 多准备与紧急补购的取舍", pad=34)')
source = source.replace('ax.legend(frameon=False, ncol=2, loc="upper left")', '''ax.legend(frameon=False, ncol=2, loc='lower center', bbox_to_anchor=(.5,1.01))
ax.set_ylim(0, float((ordinary+emergency).max())*1.14)''')
source = source.replace('bx.set_title("(b) 近期误差应占更大作用")', 'bx.set_title("(b) 近期误差应占更大作用", pad=34)\nbx.margins(x=.12,y=.18)')
source = source.replace('bx.annotate(f"{row.total_cost/1e4:.2f}", (row.beta, row.total_cost/1e4), xytext=(0, 7), textcoords="offset points", ha="center")', 'bx.annotate(f"{row.total_cost/1e4:.2f}", (row.beta, row.total_cost/1e4), xytext=(-10, 14) if np.isclose(row.beta,.8) else (0,12), textcoords="offset points", ha="right" if np.isclose(row.beta,.8) else "center")')
source = source.replace('cx.annotate(f"{row.total_cost/1e4:.2f}", (row.block_hours, row.total_cost/1e4), xytext=(0, 7)', 'cx.annotate(f"{row.total_cost/1e4:.2f}", (row.block_hours, row.total_cost/1e4), xytext=(0, 14)')
source = source.replace('cx.set_title("(c) 三小时分组兼顾细节与稳定性")', 'cx.set_title("(c) 三小时分组兼顾细节与稳定性", pad=12)\ncx.margins(x=.12,y=.18)')
source = source.replace('dx.set_title("(d) 14—56天内结果基本稳定")', 'dx.set_title("(d) 14—56天内结果基本稳定", pad=12)\ndx.set_ylim(0, float(change.max())+4)')
source = source.replace('01_parameter_interpretability.', '02_Q3_parameter_interpretability.')
source = source.replace('plt.close(fig)', "fig.savefig(OUT/'02_Q3_parameter_interpretability_preview.png',dpi=120,bbox_inches='tight')\nplt.close(fig)")
source = source.replace('OUT / "manifest.json"', 'OUT / "parameter_manifest.json"')
(HERE/'draw_parameters.py').write_text(source, 'utf-8')

# Q1: the same selected schedule curves; reserve a full row for the strategy legend.
source = (Q1/'present.py').read_text('utf-8')
block = textwrap.dedent(source[source.index('    fig,axs=plt.subplots(3,1'):source.index("    scores=rows(out/'parameter_scores.csv')")])
block = block.replace("fig,axs=plt.subplots(3,1,figsize=(8.2,8.5),layout='constrained',sharex=True)\nfig.get_layout_engine().set(rect=(0,.045,1,.91))", '''fig=plt.figure(figsize=(8.2,9.1))
gs=fig.add_gridspec(4,1,height_ratios=[1,.21,1,1],left=.115,right=.975,bottom=.10,top=.94,hspace=.18)
axs=[fig.add_subplot(gs[r]) for r in (0,2,3)]
legend_ax=fig.add_subplot(gs[1]); legend_ax.axis('off')''')
block = block.replace("axs[1].legend(ncol=3,loc='upper left');", "handles,labels=axs[1].get_legend_handles_labels()\nlegend_ax.legend(handles,labels,ncol=3,loc='center',fontsize=11);")
block = block.replace("fig.text(.04,.012", "fig.text(.06,.022")
block = block.replace("save(fig,'01_daily_dispatch')", "for axis in axs[:2]: axis.tick_params(labelbottom=False)\nsave(fig,'03_Q1_daily_dispatch')")
setup = '''
ROOT=PROJECT/'questions/Q1/runs/20260911-compare-v1'
def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
summary=json.loads((ROOT/'outputs/summary.json').read_text('utf-8'))
selected={row['candidate']:row for row in summary['comparison']}
schedules={c:rows(ROOT/'outputs/schedules'/f"{row['key']}.csv") for c,row in selected.items()}
p=np.array([float(r['price']) for r in schedules['04']]); t=np.arange(144)/6
peak=int(p.argmax())
names_cn={'03':'峰谷策略','04':'线性规划','10':'光伏预留策略'}
colors={'03':'#b65a32','04':'#1f66a5','10':'#32805a'}
styles={'03':'--','04':'-','10':':'}
'''
(HERE/'draw_dispatch.py').write_text(common+setup+block,'utf-8')
print('Three figure-only scripts prepared; original sources and research outputs unchanged.')
