from pathlib import Path
import json,hashlib,shutil,datetime,csv
import numpy as np
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
orig=root/'shumo_1/shumo_backup_20260913_003434'; dst=orig/'压缩版'
audit=root/'tmp'/('compressed_details_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
audit.mkdir()
shutil.copytree(dst,audit/'before_source');shutil.copy2(orig/'main（压缩版）.pdf',audit/'before.pdf')
(root/'tmp/compressed_details_audit_path.txt').write_text(str(audit),'utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
original_hashes={str(p.relative_to(orig)):sha(p) for p in [orig/'main.pdf',orig/'main.tex',*list((orig/'sections').glob('*')),*list((orig/'tables').glob('*')),*list((orig/'fig').glob('*'))] if p.is_file()}
(audit/'original_hashes.json').write_text(json.dumps(original_hashes,indent=2),'utf-8')
def change(file,old,new):
 p=dst/file;s=p.read_text('utf-8');assert old in s,(file,old);p.write_text(s.replace(old,new),'utf-8')
restored=root/'tmp/choice_explanations_before_20260913_125957/sections/sec_9_create.tex'
if not restored.exists():
 candidates=list((root/'tmp/choice_explanations_before_20260913_125957').rglob('sec_9_create.tex'));assert len(candidates)==1;restored=candidates[0]
shutil.copy2(restored,dst/'sections/sec_9_create.tex')
change('sections/sec_3_model_assumption.tex','其中设备容量、功率和效率均直接采用题目给定参数，而非额外假设。','储能额定容量为12000 kWh，运行储电量限制与最大充放电功率按附录1设置，充电效率与放电效率均按90\\%计。')
change('sections/sec_6_q2.tex',r'\input{tables/q2_emergency.tex}',r'''\input{tables/q2_emergency.tex}
6月21日和12月21日均未发生紧急购电，未列出的时段紧急购电量为零。''')
change('sections/sec_6_q2.tex','完整10分钟结果保存于\\texttt{result2.xlsx}。','完整10分钟结果保存于\\texttt{result2.xlsx}。其中，计划购电表的全天购电量与费用只计普通订单，紧急购电另表列示；论文中的总费用为普通电费与紧急电费之和。')
change('sections/sec_5_q1.tex','指定结果见表~\\ref{tab:q1_purchase_result}和表~\\ref{tab:q1_storage_result}。','指定结果见表~\\ref{tab:q1_purchase_result}和表~\\ref{tab:q1_storage_result}，电量单位为kWh、费用单位为元。完整策略保存于\\texttt{result1.xlsx}。')
change('sections/sec_7_q3.tex','这里的最终订单是该区间执行前最后确定的总量，并非相对零点的增减量。','这里的最终订单是该区间执行前最后确定的总量，并非相对零点的增减量。6:00、12:00和18:00分别形成剩余时段的订单版本，已执行部分保持不变；各次版本用于追溯调整过程，最终订单用于实际结算。')
change('sections/sec_8_q4.tex','问题四两种策略的全年费用结果','问题四两种策略在2025年2—12月的费用结果')
change('sections/sec_8_q4.tex','四个指定日期的结果见表\\ref{tab:q4_specified_dates}。','四个指定日期的结果见表\\ref{tab:q4_specified_dates}；指定10分钟时段的订单、各4小时区间的充放电量、日首尾库存及紧急购电时段详见附录\\ref{app:q4_details}。')
change('main.tex',r'\input{sections/sec_9_create.tex}',r'''\input{sections/sec_9_create.tex}
\clearpage
\input{sections/appendix_q4_details.tex}''')
sources=[];checks=[]
def load(p):sources.append(p);return dict(np.load(p))
prices=load(root/'questions/Q4/runs/20260913-q3-transfer-v1/outputs/supply.npz')['price']
dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21'];names=['3月20日','6月21日','9月23日','12月21日']
def num(x):return f'{0 if abs(x)<0.0005 else x:.2f}'
def clock(k):return f'{k//6:02d}:{k%6*10:02d}'
def table(caption,label,cols,rows,spec):
 return '\n'.join([r'\begin{table}[H]',r'\centering',r'\small',r'\setstretch{1.08}',r'\setlength{\tabcolsep}{5pt}',r'\caption{'+caption+'}',r'\label{'+label+'}',r'\begin{tabular}{'+spec+'}',r'\toprule',' & '.join(cols)+r' \\',r'\midrule',*[' & '.join(r)+r' \\' for r in rows],r'\bottomrule',r'\end{tabular}',r'\end{table}'])
out=[r'''% !TEX root = ../main.tex
\section*{附录A\quad 问题四指定日期的详细调度结果}
\phantomsection\label{app:q4_details}
以下结果分别对应问题四的零点分支与日内分支。购电量和充放电量以kWh计，费用以元计；充放电量在设备外侧计量，储电量在电池内部计量。总费用包含普通购电、调整和紧急购电费用，各项分别四舍五入，合计由未舍入值计算。''']
branches=[('42','问题四-2：零点固定订单',root/'questions/Q4/runs/20260912-selected-deepening-v1/outputs/strategies/Q4-2-P3-leaves31',14248570.87),('43','问题四-3：日内调整订单',root/'questions/Q4/runs/20260913-q3-transfer-v1/outputs/strategies/EW4_P2_Q60',13695929.70)]
for key,title,path,expected in branches:
 z=load(path.with_suffix('.npz'));p=path.with_suffix('.daily.csv');sources.append(p)
 with p.open(encoding='utf-8-sig',newline='') as f:df=list(csv.DictReader(f))
 assert abs(sum(float(r['total_cost']) for r in df)-expected)<.01
 ids=[next(i for i,r in enumerate(df) if r['date']==d) for d in dates]
 order=z['order'] if 'order' in z else z['versions'][:,-1,:]
 if key=='43':out.append(r'\clearpage')
 out.append(r'\subsection*{'+title+'}')
 if key=='43':
  out.append('零点原计划作为调整基准；最终普通订单是各时段执行前最后确定的购电总量，不是调整差额。')
  rows=[[clock(k)+'--'+clock(k+1)]+[num(z['q0'][i,k]) for i in ids] for k in [60,72,84,96,108,120]]
  rows.append(['全天原计划购电量']+[num(z['q0'][i].sum()) for i in ids])
  out.append(table('问题四-3指定日期的零点原计划','tab:app43_original',['时间段']+names,rows,'lrrrr'))
 rows=[[clock(k)+'--'+clock(k+1)]+[num(order[i,k]) for i in ids] for k in [60,72,84,96,108,120]]
 rows += [['全天普通订单']+[num(order[i].sum()) for i in ids],['全天紧急购电量']+[num(z['execution'][i,:,8].sum()) for i in ids]]
 for label,col in [('普通购电费','ordinary_cost'),('调整费','adjustment_cost'),('紧急购电费','emergency_cost'),('全天总费用','total_cost')]:rows.append([label]+[num(float(df[i][col])) for i in ids])
 out.append(table(title+'的指定时段订单与费用','tab:app'+key+'_order',['项目']+names,rows,'lrrrr'))
 rows=[]
 for a in range(6):
  sl=slice(a*24,(a+1)*24)
  rows.append([clock(a*24)+'--'+clock((a+1)*24),'充电']+[num(z['execution'][i,sl,5:7].sum()) for i in ids])
  rows.append(['','放电']+[num(z['execution'][i,sl,7].sum()) for i in ids])
 rows.extend([['0:00','内部储电量']+[num(z['execution'][i,0,0]) for i in ids],['24:00','内部储电量']+[num(z['execution'][i,-1,1]) for i in ids]])
 out.append(table(title+'的充放电与日首尾储电量','tab:app'+key+'_storage',['时间段','项目']+names,rows,'llrrrr'))
 events=[]
 for i,name in zip(ids,names):
  ex=z['execution'][i];day=int(df[i]['day']);pr=prices[day];em=ex[:,8]
  ordinary=float(pr@order[i]);adj=0 if key=='42' else float(.5*pr@abs(order[i]-z['q0'][i]));ec=float(5*pr@em)
  assert abs(ordinary+adj+ec-float(df[i]['total_cost']))<1e-6
  assert np.max(abs(ex[:,1]-ex[:,0]-.9*(ex[:,5]+ex[:,6])+ex[:,7]/.9))<1e-7
  assert abs(em.sum()-float(df[i]['emergency_kwh']))<1e-6
  ks=np.flatnonzero(em>1e-6)
  # Merge adjacent emergency intervals, following the problem's table-4 example.
  groups=np.split(ks,np.where(np.diff(ks)>1)[0]+1) if len(ks) else []
  for j,g in enumerate(groups):events.append([name if j==0 else '',clock(int(g[0]))+'--'+clock(int(g[-1])+1),num(em[g].sum()),num(5*(pr[g]@em[g]))])
  if not groups:events.append([name,'无','0.00','0.00'])
  checks.append({'branch':key,'date':df[i]['date'],'ordinary':ordinary,'adjustment':adj,'emergency':ec,'total':ordinary+adj+ec,'emergency_kwh':float(em.sum())})
 out.append(table(title+'的紧急购电时段','tab:app'+key+'_emergency',['日期','时间段','紧急购电量/kWh','费用/元'],events,'llrr'))
 out.append('连续发生的紧急购电按相邻时段合并，电量与费用取区间内合计；未列出的时段紧急购电量为零。')
(dst/'sections/appendix_q4_details.tex').write_text('\n\n'.join(out)+'\n','utf-8')
manifest={'restored_evaluation':str(restored),'restored_sha256':sha(restored),'sources':[{'path':str(p),'sha256':sha(p)} for p in sources],'checks':checks,'scope':'existing results only; no new model runs or Excel exports','original_hashes':original_hashes}
(audit/'changes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
print(audit)
