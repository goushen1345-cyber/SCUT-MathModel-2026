from pathlib import Path
import json,hashlib,shutil,ast,io,zipfile
import pandas as pd
import numpy as np
P=Path(__file__).resolve().parents[2];D=P/'支撑材料';C=P/'paper/提交配套';T=Path(__file__).resolve().parent
for name in ['reproduced','code/__pycache__']:
 src=(D/name).resolve();assert src.is_relative_to(D.resolve())
 if src.exists():
  dst=T/('final_checked_'+name.replace('/','_'));assert not dst.exists();shutil.move(src,dst)
for n in ['monthly_summary.csv','weekday_summary.csv','forecast_error_by_lead.csv']:
 a=pd.read_csv(T/'final_checked_reproduced/eda'/n);b=pd.read_csv(P/'audit/eda-v1'/n)
 pd.testing.assert_frame_equal(a,b,check_exact=False,atol=1e-9,rtol=1e-12)
old=pd.read_csv(P/'questions/Q1/runs/20260911-close-v1/outputs/sensitivity.csv')
new=pd.read_csv(T/'parameter_check_corrected/Q1_comparisons.csv').dropna(subset=['initial'])
for r in old.to_dict('records'):
 match=new[new.initial==r['initial_kwh']].iloc[0]
 assert abs(match.cost_yuan-r['cost_yuan'])<1e-7
(D/'evidence/extra_reproduction_check.json').write_text(json.dumps(dict(eda='three plotted statistics tables match originals',q1='54 rule settings and 1200/6000/10800 kWh initial-state checks executed; all initial-state fees match originals',figures='five Python plotting scripts executed successfully'),indent=2),encoding='utf-8')
# Public references already verified in the project; carry the bibliography without copying full books.
ref=(P/'paper/submission_support_v1/参考文献_核验版.tex').read_text('utf-8')
(D/'evidence/参考文献来源.tex').write_text(ref,encoding='utf-8')
s=(C/'AI工具使用详情.tex').read_text('utf-8')
s=s.replace('全队提交版本需合并其实际使用信息。','全队提交版本需合并其实际使用信息。DeepSeek的实际使用型号、日期、用途和交互内容仍需团队补充；当前官网型号不作为实际使用的证明。')
(C/'AI工具使用详情.tex').write_text(s,encoding='utf-8')
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name not in ['文件清单.md','SHA256SUMS.txt'])
listing='# 支撑材料文件清单\n\n以下为本目录的实际文件。路径均相对于支撑材料根目录。\n\n'
listing+='\n'.join(f'- `{p.relative_to(D).as_posix()}`' for p in files)+'\n- `文件清单.md`\n- `SHA256SUMS.txt`\n'
(D/'文件清单.md').write_text(listing,encoding='utf-8')
head=r'''\documentclass[UTF8,a4paper,11pt]{ctexart}
\usepackage[margin=2.5cm]{geometry}
\usepackage{fontspec,fvextra,longtable,booktabs,url}
\setmainfont{Times New Roman}
\setmonofont{Consolas}
\setCJKmainfont{SimSun}[BoldFont=SimHei]
\setCJKmonofont{SimSun}
\DefineVerbatimEnvironment{Code}{Verbatim}{breaklines=true,breakanywhere=true,fontsize=\scriptsize,numbers=left,numbersep=5pt,frame=single}
\begin{document}
\begin{center}\Large\bfseries 支撑材料文件清单与完整源程序\end{center}
本文件用于并入论文附录。正文仍以主论文为准，本文件不替代主论文。程序按支撑材料中的实际文件完整列出，运行方式见使用说明。
\section*{附录：支撑材料文件清单}
\small
\begin{longtable}{p{15cm}}
\toprule 文件（相对于支撑材料根目录）\\\midrule\endhead
'''
allpaths=[p.relative_to(D).as_posix() for p in files]+['文件清单.md','SHA256SUMS.txt']
body='\n'.join(r'\path{'+n+r'}\\' for n in allpaths)+r'\bottomrule\end{longtable}'+'\n'
body+=r'\normalsize\section*{附录：完整源程序}'+'\n'
for p in sorted((D/'code').iterdir()):
 if p.suffix not in ['.py','.tex']:continue
 body+=r'\subsection*{\texttt{\detokenize{'+p.name+'}}}'+'\n'
 body+=r'\VerbatimInput[breaklines=true,breakanywhere=true,fontsize=\scriptsize,numbers=left,numbersep=5pt,frame=single]{../../支撑材料/code/'+p.name+'}\n'
(C/'支撑材料附录.tex').write_text(head+body+'\n\\end{document}\n',encoding='utf-8')
print('source files',sum(p.suffix in ['.py','.tex'] for p in (D/'code').iterdir()),'file list',len(allpaths))
