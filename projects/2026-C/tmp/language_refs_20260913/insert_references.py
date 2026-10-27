from pathlib import Path
import re,json
root=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C')
base=root/'shumo_1/shumo_backup_20260913_003434/图像压缩版'
def sub(file,a,b):
    p=base/file;s=p.read_text('utf-8')
    assert s.count(a)==1,(file,a[:50])
    p.write_text(s.replace(a,b),encoding='utf-8')
sub('sections/sec_5_q1.tex',r'本文采用\textbf{电量流线性规划}，',r'本文采用\textbf{电量流线性规划}\cite{dantzig}，')
sub('sections/sec_5_q1.tex',r'采用SciPy的\texttt{linprog}接口调用HiGHS求解。',r'采用SciPy\cite{virtanen}的\texttt{linprog}接口调用HiGHS求解，其所含双单纯形算法的原理见文献\cite{huangfu}。')
sub('sections/sec_6_q2.tex','候选包括历史分项预测、岭回归和提升树。历史分项预测能够直接利用负载的星期规律和光伏的近期变化，便于解释供需判断的来源；',r'候选包括历史分项预测、岭回归\cite{hoerl}和提升树\cite{friedman}。历史参照预测方法\cite{hyndman}便于利用负载的星期规律和光伏的近期变化，解释供需判断的来源；')
sub('sections/sec_6_q2.tex',r'\subsection{模型求解与实际运行}',r'\subsection{模型求解与实际运行}'+'\n'+r'岭回归与提升树候选由scikit-learn实现\cite{pedregosa}，各策略按以下步骤连续运行。')
sub('sections/sec_8_q4.tex','将多棵较小的回归树逐步相加：',r'将多棵较小的回归树逐步相加\cite{friedman}：')
sub('sections/sec_8_q4.tex','岭回归在拟合误差之外加入系数惩罚，使价格判断更加平稳：',r'岭回归在拟合误差之外加入系数惩罚\cite{hoerl}，使价格判断更加平稳：')
sub('sections/sec_9_create.tex','协调本地发电与外网购电，兼顾用能经济性和可再生能源利用。',r'协调本地发电与外网购电，兼顾用能经济性和可再生能源利用，与我国新能源配套储能及微电网发展的政策方向相衔接\cite{carbonplan,energyplan}。')

source=(root/'paper/submission_support_v1/参考文献_核验版.tex').read_text('utf-8')
items={m.group(1):m.group(0) for m in re.finditer(r'\\bibitem\{([^}]+)\}[^\n]+',source)}
order=['dantzig','virtanen','huangfu','hoerl','friedman','hyndman','pedregosa','carbonplan','energyplan']
out='% !TEX root = ../main.tex\n\\begingroup\n\\small\n\\setstretch{1.10}\n\\begin{thebibliography}{99}\n\\setlength{\\itemsep}{2pt}\n\\setlength{\\parskip}{0pt}\n'+ '\n'.join(items[k] for k in order)+'\n\\end{thebibliography}\n\\endgroup\n'
(base/'sections/references.tex').write_text(out,encoding='utf-8')
(base/'sections/ai_statement.tex').write_text((root/'paper/submission_support_v1/AI工具使用声明.tex').read_text('utf-8'),encoding='utf-8')
sub('main.tex',r'\input{sections/sec_9_create.tex}',r'\input{sections/sec_9_create.tex}'+'\n'+r'\input{sections/ai_statement.tex}'+'\n'+r'\input{sections/references.tex}')

# Keep the body type size, line spacing and margins. Compact only spacing around elements.
sub('main.tex','beforeskip = 1.15em,','beforeskip = 0.95em,')
sub('main.tex','afterskip = 0.75em,','afterskip = 0.60em,')
sub('main.tex','beforeskip = 0.85em,','beforeskip = 0.65em,')
sub('main.tex','afterskip = 0.45em,','afterskip = 0.35em,')
sub('main.tex','beforeskip = 0.6em,','beforeskip = 0.45em,')
# Only subsubsection afterskip, not subsection.
sub('main.tex','beforeskip = 0.45em,\n    afterskip = 0.35em,','beforeskip = 0.45em,\n    afterskip = 0.25em,')
display=r'''\setlength{\abovedisplayskip}{7pt plus 2pt minus 2pt}
\setlength{\belowdisplayskip}{7pt plus 2pt minus 2pt}
\setlength{\abovedisplayshortskip}{3pt plus 1pt minus 1pt}
\setlength{\belowdisplayshortskip}{6pt plus 2pt minus 2pt}'''
sub('main.tex',r'\input{sections/sec_1_problem_review.tex}',display+'\n'+r'\input{sections/sec_1_problem_review.tex}')
sub('sections/sec_3_model_assumption.tex',r'\begin{longtable}{ccl}',r'\begingroup'+'\n'+r'\small\setstretch{1.10}'+'\n'+r'\begin{longtable}{ccl}')
sub('sections/sec_3_model_assumption.tex',r'\end{longtable}',r'\end{longtable}'+'\n'+r'\endgroup')
print('Added 9 references, in-text citations and the brief AI declaration; adjusted element spacing.')
