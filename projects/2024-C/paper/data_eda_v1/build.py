"""Render the authored Markdown chapter with native LaTeX, no research execution."""
from pathlib import Path
import re,subprocess,argparse
HERE=Path(__file__).resolve().parent
def esc(s):
    return ''.join({'&':r'\&','%':r'\%','_':r'\_','#':r'\#','$':r'\$'}.get(c,c) for c in s)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-only',action='store_true');args=ap.parse_args()
    lines=(HERE/'chapter.md').read_text(encoding='utf-8').splitlines();body=[];i=0
    while i<len(lines):
        l=lines[i].strip();i+=1
        if not l:continue
        if l=='<!-- page -->':body.append(r'\newpage');continue
        if l.startswith('# '):body.append(r'\section*{'+esc(l[2:])+'}');continue
        if l.startswith('## '):body.append(r'\subsection*{'+esc(l[3:])+'}');continue
        if l.startswith('|'):
            rows=[l]
            while i<len(lines) and lines[i].startswith('|'):rows.append(lines[i]);i+=1
            parsed=[[esc(v.strip()) for v in r.strip('|').split('|')] for r in rows if not re.fullmatch(r'[|\-: ]+',r)]
            n=len(parsed[0]);spec=''.join([r'>{\raggedright\arraybackslash}X']*n)
            body.append(r'\par\noindent{\small\renewcommand{\arraystretch}{1.22}\begin{tabularx}{\linewidth}{'+spec+r'}\toprule')
            for j,row in enumerate(parsed):body.append(' & '.join(row)+r' \\'+(r'\midrule' if j==0 else ''))
            body.append(r'\bottomrule\end{tabularx}}\par\medskip');continue
        if l.startswith('!['):
            ref=re.search(r'\]\((.*)\)',l).group(1);pdf=ref.replace('.png','.pdf')
            tall=any(n in ref for n in ['02_coverage','05_crop_history','06_price_intervals'])
            width='.98' if tall else '1.0'
            body.append(r'\par\noindent\hfil\includegraphics[width='+width+r'\linewidth]{'+pdf+r'}\hfil\par\nopagebreak');continue
        if re.match(r'^(图\d+|附图A\d+) ',l):body.append(r'{\centering\small '+esc(l)+r'\par}\medskip');continue
        if re.match(r'^表\d+ ',l):body.append(r'{\centering\small '+esc(l)+r'\par}\nopagebreak\smallskip');continue
        body.append(esc(l)+r'\par')
    pre=r'''\documentclass[11pt,a4paper]{article}
\usepackage[UTF8]{ctex}
\usepackage[a4paper,left=23mm,right=23mm,top=19mm,bottom=20mm]{geometry}
\usepackage{fontspec,xeCJK,graphicx,booktabs,tabularx,array,amsmath}
\usepackage[hidelinks]{hyperref}
\setmainfont{Times New Roman}
\setCJKmainfont{SimSun}[BoldFont=SimHei]
\setCJKsansfont{SimHei}
\setlength{\parindent}{2em}
\setlength{\parskip}{3pt}
\linespread{1.08}
\setlength{\tabcolsep}{5pt}
\emergencystretch=1em
\pagestyle{plain}
\begin{document}
'''
    (HERE/'chapter.tex').write_text(pre+'\n'.join(body)+'\n'+r'\end{document}',encoding='utf-8')
    if args.source_only:return
    bin=Path('C:/Program Files/Latex/miktex/bin/x64')
    for _ in range(2):subprocess.run([str(bin/'xelatex.exe'),'--disable-installer','-interaction=nonstopmode','-halt-on-error','-no-pdf','chapter.tex'],cwd=HERE,check=True)
    subprocess.run([str(bin/'xdvipdfmx.exe'),'-q','-o','chapter.pdf','chapter.xdv'],cwd=HERE,check=True)
    (HERE/'preview').mkdir(exist_ok=True)
    subprocess.run(['C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe','-r','110','-png','chapter.pdf','preview/page'],cwd=HERE,check=True)
if __name__=='__main__':main()
