"""Render the first-stage prose only; no workbook/experiment reads or calculations."""
from pathlib import Path
import argparse
import re
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'front_matter_understanding_v2.md'

def inline(s):
    saved = []
    def keep(v):
        saved.append(v)
        return f'ZZTOKEN{len(saved)-1}ZZ'
    s = re.sub(r'\$([^$]+)\$', lambda m: keep('$'+m[1]+'$'), s)
    s = re.sub(r'`([^`]+)`', lambda m: keep(r'\texttt{'+m[1].replace('_',r'\_')+'}'), s)
    s = re.sub(r'\*\*([^*]+)\*\*', lambda m: keep(r'\textbf{'+inline(m[1])+'}'), s)
    for a,b in [('&',r'\&'),('%',r'\%'),('#',r'\#'),('_',r'\_')]:
        s=s.replace(a,b)
    for n,v in enumerate(saved): s=s.replace(f'ZZTOKEN{n}ZZ',v)
    return s

def make_tex():
    lines=SOURCE.read_text(encoding='utf-8').splitlines()
    body=[]; k=0; table_no=0; pending_caption=None
    while k<len(lines):
        line=lines[k].strip();k+=1
        if not line or line.startswith('# '): continue
        if line.startswith('### '):
            body.append(r'\subsection*{'+inline(line[4:])+'}');continue
        if line.startswith('## '):
            if line.startswith('## 5 '):body.append(r'\par\vspace{8pt}\noindent\begin{minipage}{\linewidth}')
            body.append(r'\section*{'+inline(line[3:])+'}');continue
        if line.startswith('|'):
            rows=[line]
            while k<len(lines) and lines[k].strip().startswith('|'):
                rows.append(lines[k].strip());k+=1
            cells=[[c.strip() for c in row.strip('|').split('|')] for row in rows]
            cells=[r for r in cells if not all(re.fullmatch(r':?-+:?',c) for c in r)]
            table_no+=1
            cols={1:r'>{\raggedright\arraybackslash}p{2.7cm}>{\raggedright\arraybackslash}p{2.4cm}>{\raggedright\arraybackslash}X',
                  2:r'>{\raggedright\arraybackslash}p{4.3cm}>{\raggedright\arraybackslash}X',
                  3:r'>{\raggedright\arraybackslash}p{2.2cm}>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}p{4.6cm}'}[table_no]
            body.append(r'\par\smallskip\noindent\begin{minipage}{\linewidth}')
            if pending_caption:
                body.append(r'{\centering\small '+inline(pending_caption)+r'\par}\smallskip')
                pending_caption=None
            body.append(r'{\fontsize{10.5}{14}\selectfont\renewcommand{\arraystretch}{1.22}\begin{tabularx}{\linewidth}{'+cols+r'}\toprule')
            for n,r in enumerate(cells):
                body.append(' & '.join(inline(c) for c in r)+r' \\')
                if n==0:body.append(r'\midrule')
            body.append(r'\bottomrule\end{tabularx}}\end{minipage}\par\smallskip')
            if table_no==3:body.append(r'\end{minipage}')
            continue
        if line.startswith('!['):
            body.append(r'\par\noindent\hfil\includegraphics[width=0.96\linewidth]{../figures/understanding_v2/render_v2/framework.pdf}\hfil\par\nopagebreak');continue
        if re.match(r'^表[12] ',line):
            pending_caption=line;continue
        if line.startswith('图1 '):
            body.append(r'{\centering\small '+inline(line)+r'\par}\medskip');continue
        if line.startswith('注：'):
            body.append(r'{\small\noindent '+inline(line)+r'\par}\medskip');continue
        body.append(inline(line)+r'\par')
    pre=r'''\documentclass[11pt,a4paper]{article}
\usepackage[UTF8]{ctex}
\usepackage[a4paper,left=25mm,right=25mm,top=22mm,bottom=22mm]{geometry}
\usepackage{fontspec,xeCJK,graphicx,booktabs,tabularx,array,amsmath,amssymb}
\usepackage[hidelinks]{hyperref}
\setmainfont{Times New Roman}
\setCJKmainfont{SimSun}[BoldFont=SimHei]
\setCJKsansfont{SimHei}
\setlength{\parindent}{2em}
\setlength{\parskip}{3pt}
\linespread{1.18}
\setlength{\tabcolsep}{5pt}
\emergencystretch=1em
\pagestyle{plain}
\begin{document}
'''
    return pre+'\n'.join(body)+'\n'+r'\end{document}'+'\n'

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--source-only',action='store_true')
    args=a.parse_args()
    tex=HERE/'front_matter_understanding_v2.tex'
    tex.write_text(make_tex(),encoding='utf-8')
    if args.source_only:return
    exe=Path(r'C:\Program Files\Latex\miktex\bin\x64')
    for _ in range(2):
        subprocess.run([str(exe/'xelatex.exe'),'--disable-installer','-interaction=nonstopmode','-halt-on-error','-no-pdf',tex.name],cwd=HERE,check=True)
    subprocess.run([str(exe/'xdvipdfmx.exe'),'-q','-o','front_matter_understanding_v2.pdf','front_matter_understanding_v2.xdv'],cwd=HERE,check=True)
    poppler=Path(r'C:\Users\Rog\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
    previews=HERE/'preview';previews.mkdir(exist_ok=True)
    subprocess.run([str(poppler),'-r','120','-png','front_matter_understanding_v2.pdf',str(previews/'page')],cwd=HERE,check=True)

if __name__=='__main__':main()
