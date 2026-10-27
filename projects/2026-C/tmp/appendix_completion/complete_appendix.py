from pathlib import Path
import hashlib,json,re

P=Path(__file__).resolve().parents[2]
S=P/'shumo_1/shumo_backup_20260913_003434/图像压缩版'
D=P/'支撑材料'
files=sorted(p for p in D.rglob('*') if p.is_file() and not p.name.startswith('~$') and '__pycache__' not in p.parts)
names=[p.relative_to(D).as_posix() for p in files]
assert len(names)==len(set(names))

content=r'''% !TEX root = ../main.tex
\clearpage
\section*{附录B\quad 支撑材料文件清单}
支撑材料与论文分别提交。以下文件路径均相对于支撑材料根目录；根目录中的五个result工作簿为已填写的结果，templates目录中的同名文件为空白模板。

\begingroup
\small\setstretch{1.08}
\setlength{\LTpre}{6pt}\setlength{\LTpost}{6pt}
\begin{longtable}{@{}r p{13.7cm}@{}}
\toprule 序号 & 文件路径\\\midrule
\endfirsthead
\multicolumn{2}{l}{支撑材料文件清单（续）}\\
\toprule 序号 & 文件路径\\\midrule
\endhead
\midrule\multicolumn{2}{r}{续下页}\\\endfoot
\bottomrule\endlastfoot
'''
for i,name in enumerate(names,1):content+=str(i)+r' & \path{'+name+r'}\\'+'\n'
content+=r'''\end{longtable}
\endgroup

\clearpage
\section*{附录C\quad 程序运行与结果文件说明}
\subsection*{C.1\quad 运行环境与入口}
计算程序使用Python 3.13，所需软件包及版本见支撑材料中的requirements.txt。程序使用相对路径读取文件，在支撑材料根目录依次执行以下命令：
\begin{Verbatim}[fontsize=\small,frame=single,xleftmargin=8pt,xrightmargin=8pt]
python -m pip install -r requirements.txt
python code/prepare_inputs.py
python code/reproduce.py
python code/export_results.py
\end{Verbatim}
第一条命令安装依赖；第二条根据随包数据重建计算输入并逐值核对；第三条重新计算问题一、衔接1月份储电量，再分别计算后续四条年度方案。复算输出写入reproduced目录，并与results目录的保存结果比较。最后一条命令依据results中的完整精度记录填写五份结果模板，核对费用和储能约束。

如需从赛题原始Excel重新整理数据，可将附件按原目录结构置于\path{data/raw/C题/附件/}，将题面置于\path{data/raw/C题/C题.pdf}，再运行\path{code/prepare_source_tables.py}。原始附件由赛题提供，不在支撑材料中重复保存。

\subsection*{C.2\quad 结果与图表的对应关系}
result1.xlsx给出问题一完整一天的安排；result2.xlsx、result3.xlsx、result4-2.xlsx与result4-3.xlsx分别给出对应方案2025年2月1日至12月31日的结果。工作簿沿用赛题模板样式，单元格保留完整精度，费用以未舍入值计算。results目录保存逐时段记录和逐日费用，问题三及问题四日内分支的历次调整另存于相应的压缩CSV文件。

\path{code/explore_data.py}生成描述统计，\path{code/validation.py}提供已有对照检验的运行入口。五个以fig开头的Python程序根据figure\_inputs中的数据生成图表；两份TikZ源文件可使用XeLaTeX编译。具体命令见支撑材料的使用说明。本文结果表由Python写入Excel，不依赖Excel宏或SPSS交互命令。

\clearpage
\section*{附录D\quad 完整源程序}
以下按数据整理、模型计算、检验与结果导出、图表绘制的顺序列出支撑材料中的全部程序。程序内容直接读取同名源文件，不以片段或省略号代替。
\begingroup
\setstretch{1.0}
\setmonofont{Consolas}
\setCJKmonofont{SimSun}
'''
groups=[('数据整理',[('prepare_source_tables.py','原始附件读取与整理'),('prepare_inputs.py','计算输入重建'),('explore_data.py','数据探索性分析')]),('预测与调度计算',[('q1.py','问题一线性规划'),('q2.py','问题二预测与跨日调度'),('q3_base.py','运行回放与共享计算'),('q3.py','问题三日内滚动调度'),('q4.py','电价预测与调度基础'),('q4_tree.py','问题四零点分支'),('q4_update.py','问题四日内分支'),('reproduce.py','四问完整复算入口')]),('检验与结果导出',[('validation.py','已有参数与信息对照'),('export_results.py','结果表填写与约束核验')]),('图表绘制',[('fig_data.py','数据分析图'),('fig_q1.py','问题一结果图'),('fig_q2_sensitivity.py','问题二灵敏度图'),('fig_q3_days.py','问题三指定日期图'),('fig_q3_quantile.py','问题三参数比较图'),('energy_paths.tex','电量关系示意图'),('framework.tex','四问总体框架图')])]
listed=[];i=0
for group,entries in groups:
 for name,description in entries:
  i+=1;listed.append('code/'+name)
  content+=f'\n\\subsection*{{D.{i}\\quad {description}}}\n'
  content+=r'\noindent 文件：\path{code/'+name+'}\\par\n\\smallskip\n'
  content+=r'\VerbatimInput[breaklines=true,breakanywhere=true,fontsize=\footnotesize,baselinestretch=1,numbers=left,numbersep=4pt,xleftmargin=18pt,xrightmargin=6pt,frame=single,framesep=3pt]{../../../支撑材料/code/'+name+'}\n'
content+='\\endgroup\n'
actual=[p.relative_to(D).as_posix() for p in (D/'code').iterdir() if p.suffix in ['.py','.tex']]
assert set(actual)==set(listed),(set(actual)-set(listed))
target=S/'sections/appendix_support.tex';target.write_text(content,encoding='utf-8')
main=S/'main.tex';text=main.read_text('utf-8')
text=text.replace('\\usepackage{longtable}', '\\usepackage{longtable}\n\\usepackage{fvextra}\n\\usepackage{url}')
text=text.replace('\\input{sections/appendix_q4_details.tex}', '\\input{sections/appendix_q4_details.tex}\n\\input{sections/appendix_support.tex}')
main.write_text(text,encoding='utf-8')
build=S/'build_appendix';build.mkdir(exist_ok=True)
(Path(__file__).parent/'manifest.json').write_text(json.dumps({'file_count':len(files),'source_count':len(listed),'source_files':listed,'file_hashes':{p.relative_to(D).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},ensure_ascii=False,indent=2),encoding='utf-8')
print('files',len(files),'source programs',len(listed))
