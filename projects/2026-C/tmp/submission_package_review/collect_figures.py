from pathlib import Path
import json,shutil,re,textwrap,ast
P=Path(__file__).resolve().parents[2];D=P/'支撑材料';B=P/'shumo_1/shumo_backup_20260913_003434';F=D/'figures';F.mkdir(exist_ok=True);I=D/'figure_inputs';I.mkdir(exist_ok=True)
def put(rel,name):
 dst=I/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/rel,dst)
for p in (B/'图像压缩版/sections').glob('*.tex'):
 for n in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{fig/([^}]+)\}',p.read_text('utf-8')):shutil.copy2(B/'图像压缩版/fig'/n,F/n)
for name in ['monthly_summary.csv','weekday_summary.csv','forecast_error_by_lead.csv']:put('audit/eda-v1/'+name,'eda/'+name)
s=(B/'图像压缩版/scripts/draw_compact_data.py').read_text('utf-8')
s=s.replace("P=Path(__file__).resolve().parents[4]","P=Path(__file__).resolve().parents[1]").replace("paper=Path(__file__).resolve().parents[1]","paper=P/'reproduced/plots'\n(paper/'fig').mkdir(parents=True,exist_ok=True)\n(paper/'scripts').mkdir(exist_ok=True)").replace("source=P/'audit/eda-v1'","source=P/'figure_inputs/eda'")
(D/'code/fig_data.py').write_text(s,encoding='utf-8')
# Q1: preserve the selected three schedules used by the published dispatch figure.
q1path='questions/Q1/runs/20260911-compare-v1'
summary=json.loads((P/q1path/'outputs/summary.json').read_text('utf-8'))
(I/'q1/outputs/schedules').mkdir(parents=True,exist_ok=True)
(I/'q1/outputs/summary.json').write_text(json.dumps({'comparison':summary['comparison']},ensure_ascii=False,indent=2),encoding='utf-8')
for row in summary['comparison']:put(q1path+'/outputs/schedules/'+row['key']+'.csv','q1/outputs/schedules/'+row['key']+'.csv')
s=(P/'paper/figures/layout-fixes-v1/draw_dispatch.py').read_text('utf-8')
s=s.replace('HERE = Path(__file__).resolve().parent\nPROJECT = HERE.parents[2]',"PROJECT=Path(__file__).resolve().parents[1]\nHERE=PROJECT/'reproduced/plots/fig'\nHERE.mkdir(parents=True,exist_ok=True)")
s=s.replace("ROOT=PROJECT/'questions/Q1/runs/20260911-compare-v1'","ROOT=PROJECT/'figure_inputs/q1'")
(D/'code/fig_q1.py').write_text(s,encoding='utf-8')
# Q3 latest daily trajectories and parameter plot, with only their actual numerical inputs.
put('questions/Q3/runs/20260912-forecast-risk-v1/outputs/strategies/EW4_Q60_full.daily.csv','q3_daily.csv')
put('shumo_1/shumo_backup_20260913_003434/scripts/derived_values.json','derived_values.json')
s=(B/'scripts/update_result_figures.py').read_text('utf-8');start=s.index("font_manager.findfont");end=s.index("save(fig,'q3_final_days')")+len("save(fig,'q3_final_days')")
fragment=s[start:end];monthly=fragment.index('# Q3 monthly charges');daily=fragment.index('#',monthly+1)
# Keep original style, helpers and plots up to the final specified-day figure.
prefix="""from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'reproduced/plots/fig';FIG.mkdir(parents=True,exist_ok=True)
z=dict(np.load(ROOT/'results/Q3.npz'))
df=pd.read_csv(ROOT/'figure_inputs/q3_daily.csv')
truth=np.load(ROOT/'data/inputs.npz')['actual']
"""
(D/'code/fig_q3_days.py').write_text(prefix+fragment+'\n',encoding='utf-8')
s=(B/'scripts/draw_q3_quantile.py').read_text('utf-8')
s=s.replace("base=Path(__file__).resolve().parents[1]\nsource=base/'scripts/derived_values.json'","ROOT=Path(__file__).resolve().parents[1]\nbase=ROOT/'reproduced/plots'\n(base/'fig').mkdir(parents=True,exist_ok=True)\n(base/'scripts').mkdir(exist_ok=True)\nsource=ROOT/'figure_inputs/derived_values.json'")
(D/'code/fig_q3_quantile.py').write_text(s,encoding='utf-8')
# Q2 parameter chart: original plotting block and original comparison rows.
for key in ['refinement','validation','supplement']:put('questions/Q2/runs/20260911-annual-validation-v1/'+key+'/comparison.csv','q2/'+key+'/comparison.csv')
s=(P/'paper/q2_manuscript_v3/prepare.py').read_text('utf-8');start=s.index('    allrows=pd.concat');end=s.index("    pd.DataFrame(sens).to_csv",start);end=s.index('\n',end)
style=s[s.index('plt.rcParams.update'):s.index('INPUTS =')]
prefix="""from pathlib import Path
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
"""
(D/'code/fig_q2_sensitivity.py').write_text(prefix+style+textwrap.dedent(s[start:end])+'\n',encoding='utf-8')
shutil.copy2(P/'paper/figures/model-framework-v4/framework.tex',D/'code/framework.tex')
shutil.copy2(P/'paper/q1_manuscript_v1/figures/energy_paths.tex',D/'code/energy_paths.tex')
(F/'图源说明.md').write_text('''# 图源与复现

本目录保留图像压缩版论文实际使用的九张图。数据图和结果图由Python绘制，总体框架图与电量流示意图由TikZ绘制；源文件均在code中。

依次运行`python code/fig_data.py`、`python code/fig_q1.py`、`python code/fig_q2_sensitivity.py`、`python code/fig_q3_days.py`、`python code/fig_q3_quantile.py`，输出在reproduced/plots/fig。绘图需要宋体和Times New Roman，字体不同可能改变文字尺寸。两份TikZ源文件可用XeLaTeX独立编译。

weiwang.png为队员提供并指定保留的立体示意图，用于说明系统组成，不参与计算。其原始制作工程文件、工具和版本未随本项目记录提供。其余图均有对应源程序；q1_1.png对应energy_paths.tex，总体框架model.pdf对应framework.tex。

figure_inputs保存原研究中用于作图和比较的数值，results保存最终逐段运行结果。源文件整理仅改变文件读取位置与输出位置，不重新调整图内研究数据。
''',encoding='utf-8')
# Copy numerical summaries supporting the comparison / sensitivity conclusions.
paths={
'Q1_strategy_comparison.csv':'questions/Q1/runs/20260911-compare-v1/outputs/comparison.csv',
'Q1_storage_sensitivity.csv':'questions/Q1/runs/20260911-close-v1/outputs/sensitivity.csv',
'Q2_annual_candidates.csv':'questions/Q2/runs/20260911-annual-validation-v1/annual/comparison.csv',
'Q2_refinement.csv':'questions/Q2/runs/20260911-annual-validation-v1/refinement/comparison.csv',
'Q2_validation.csv':'questions/Q2/runs/20260911-annual-validation-v1/validation/comparison.csv',
'Q3_final_comparison.csv':'questions/Q3/runs/20260912-forecast-risk-v1/outputs/comparison.csv',
'Q4_validation.csv':'questions/Q4/runs/20260912-selected-deepening-v1/outputs/comparison.csv',
'Q4_final_comparison.csv':'questions/Q4/runs/20260913-q3-transfer-v1/outputs/comparison.csv'}
for n,p in paths.items():shutil.copy2(P/p,D/'evidence'/n)
print('Nine final figures, source programs and numerical evidence collected.')
