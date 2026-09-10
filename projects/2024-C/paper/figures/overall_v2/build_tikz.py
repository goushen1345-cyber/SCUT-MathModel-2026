"""Render confirmed structure with TikZ. Reads structure.json; never imports research code."""
import argparse
import json
import subprocess
import hashlib
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
PREAMBLE=r'''\documentclass[border=3mm]{standalone}
\usepackage{fontspec}
\usepackage{xeCJK}
\setmainfont{Times New Roman}
\setCJKmainfont[BoldFont=SimHei]{SimSun}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,calc,fit,backgrounds}
\definecolor{basefill}{HTML}{F1F3F5}
\definecolor{qone}{HTML}{EFF4F0}
\definecolor{qtwo}{HTML}{EDF2F6}
\definecolor{qthree}{HTML}{F5F1EA}
\tikzset{box/.style={draw=black!65,line width=.55pt,rounded corners=1.1pt,fill=white,align=center,inner xsep=3pt,inner ysep=4pt,text=black,font=\fontsize{8.6}{12}\selectfont},
 arrow/.style={-{Stealth[length=1.7mm,width=1.4mm]},line width=.55pt,draw=black!75},
 line/.style={line width=.55pt,draw=black!75},
 ext/.style={arrow,dashed},
 heading/.style={anchor=west,text=black,font=\fontsize{10}{12}\selectfont\bfseries},
 note/.style={text=black,font=\fontsize{7.3}{9}\selectfont,align=center,fill=white,inner sep=1.5pt}}
\begin{document}
\begin{tikzpicture}[x=1cm,y=1cm]
'''

def escape(t):
    return t.replace('%',r'\%').replace('&',r'\&').replace('_',r'\_').replace('≤',r'$\leq$').replace('→',r'$\rightarrow$').replace('−',r'$-$')

def text_lines(lines):
    body = r'\\'.join((r'\textbf{'+escape(line)+'}') if i==0 else escape(line) for i,line in enumerate(lines))
    return r'\shortstack[c]{'+body+'}'

def main_source(spec):
    pos={
      'I1':(3.95,0,7.5,1.45),'I2':(12.45,0,7.5,1.45),
      'D1':(2.65,-2.5,4.65,1.7),'D2':(8.2,-2.5,4.65,1.7),'D3':(13.75,-2.5,4.65,1.7),
      'UV':(2.65,-5.3,4.65,1.85),'UA':(8.2,-5.3,4.65,1.85),'UT':(13.75,-5.3,4.65,1.85),
      'Q1A':(2.65,-9.0,4.65,1.9),'Q2A':(8.2,-9.0,4.65,1.9),'Q3A':(13.75,-9.0,4.65,1.9),
      'Q1B':(2.65,-11.55,4.65,1.9),'Q2B':(8.2,-11.55,4.65,1.9),'Q3B':(13.75,-11.55,4.65,1.9),
      'Q1C':(2.65,-13.95,4.65,1.45),'Q2C':(8.2,-13.95,4.65,1.45),'Q3C':(13.75,-13.95,4.65,1.45),
      'R1':(8.2,-16.0,15.7,1.3),'R2':(8.2,-17.85,15.7,1.3)}
    out=[PREAMBLE]
    out += [r'\node[heading] at (0,1.2) {1\quad 输入与问题};',
            r'\node[heading] at (0,-1.25) {2\quad 数据与参数};',
            r'\node[heading] at (0,-3.75) {3\quad 统一混合整数规划骨架};',
            r'\node[heading] at (0,-7.02) {4\quad 三问扩展};']
    for n in spec['nodes']:
        x,y,w,h=pos[n['id']]
        fill='basefill' if n['scope']=='shared' else {'Q1':'qone','Q2':'qtwo','Q3':'qthree'}.get(n['scope'],'white')
        out.append(fr"\node[box,text width={w}cm,minimum height={h}cm,fill={fill}] ({n['id']}) at ({x},{y}) {{{text_lines(n['lines'])}}};")
    out += [r'\begin{scope}[on background layer]',
            r'\node[draw=black!70,line width=.65pt,rounded corners=2pt,fit=(UV)(UA)(UT),inner sep=5pt] (G) {};',
            r'\end{scope}']
    # Inputs: attachment 1/2 provide model parameters; attachment 3 is a format reference only.
    out += [r'\draw[line] (I1.south) -- (3.95,-1.02);',
            r'\draw[line] (I2.south) -- node[note,right]{附件1、2} (12.45,-1.02);',
            r'\draw[line] (2.65,-1.02) -- (13.75,-1.02);']
    for n in ['D1','D2','D3']:
        x=pos[n][0]
        out.append(fr'\draw[arrow] ({x},-1.02) -- ({n}.north);')
        out.append(fr'\draw[line] ({n}.south) -- ({x},-3.55);')
    out += [r'\draw[line] (2.65,-3.55) -- (13.75,-3.55);',r'\draw[arrow] (8.2,-3.55) -- (G.north);']
    # All three boxes together form the same core; no sequence among UV, UA, UT.
    out += [r'\draw[line] (G.south) -- (8.2,-6.55);',r'\draw[line] (2.65,-6.55) -- (13.75,-6.55);']
    for n in ['Q1A','Q2A','Q3A']:
        x=pos[n][0]
        out.append(fr'\draw[arrow] ({x},-6.55) -- ({n}.north);')
    # Dashes describe extension of factors, not a locking of area decisions.
    out += [r'\draw[ext] (4.2,-8.03) -- (4.2,-7.7) -- node[note,above]{增加参数不确定性} (6.65,-7.7) -- (6.65,-8.03);',
            r'\draw[ext] (9.75,-8.03) -- (9.75,-7.7) -- node[note,above]{增加作物关系\\并披露额外随机设定} (12.2,-7.7) -- (12.2,-8.03);']
    for q in [1,2,3]:
        out += [fr'\draw[arrow] (Q{q}A.south) -- (Q{q}B.north);',fr'\draw[arrow] (Q{q}B.south) -- (Q{q}C.north);']
    # Baseline-plan reference transfers are distinct from the dashed extensions.
    out += [r'\draw[arrow] (Q1C.east) -- (5.425,-13.95) -- node[note,rotate=90]{半价参考方案} (5.425,-11.55) -- (Q2B.west);',
            r'\draw[arrow] (Q2C.east) -- (10.975,-13.95) -- node[note,rotate=90]{问题二基准方案} (10.975,-11.55) -- (Q3B.west);']
    for q in [1,2,3]:
        x=pos[f'Q{q}C'][0]
        out.append(fr'\draw[line] (Q{q}C.south) -- ({x},-15.05);')
    out += [r'\draw[line] (2.65,-15.05) -- (13.75,-15.05);',r'\draw[arrow] (8.2,-15.05) -- (R1.north);',r'\draw[arrow] (R1.south) -- (R2.north);',
            r'\node[note,anchor=west] at (0,-18.85) {实线：输入、求解与结果传递\qquad 虚线：新增现实因素\qquad 侧向箭头：参考方案参与比较};',
            r'\end{tikzpicture}',r'\end{document}']
    return '\n'.join(out)+'\n'

def relation_source():
    out=[PREAMBLE]
    nodes=[
      ('F',4,0,7.2,1.6,['市场、通胀与天气潜在因子','相关潜在量→离散参数档位','成本／菜价另采用随机趋势档位']),
      ('P',12.2,0,7.2,1.6,['同类、同季次作物的合成关系图','价格中点、亩产、成本的特征距离','邻作物相对当年参考价格→需求修正']),
      ('L',8.1,-2.6,15.4,1.65,['同一批相关底层参数，三个需求响应设定','无额外响应：乘子为1；替代：邻边系数＋0.15','替代与互补：系数＋0.15／−0.10；额外乘子限0.90—1.10']),
      ('O',8.1,-5.0,15.4,1.6,['在共同情景上评价同一候选种植方案','正常销售=min（产量，基准需求×额外关系乘子）','比较三世界收益、尾部表现及关系强度敏感性']),
      ('B',8.1,-7.1,15.4,1.4,['边界','关系图与系数为模拟设定；相关检查仅覆盖训练潜在层','不证明现实因果关系，也不识别问题二到问题三的纯相关收益'])]
    for nid,x,y,w,h,lines in nodes:
        out.append(fr'\node[box,text width={w}cm,minimum height={h}cm,fill=basefill] ({nid}) at ({x},{y}) {{{text_lines(lines)}}};')
    out += [r'\draw[arrow] (F.south) -- (4,-1.35) -| (L.north);',r'\draw[arrow] (P.south) -- (12.2,-1.35) -| (L.north);',r'\draw[arrow] (L.south) -- (O.north);',r'\draw[arrow] (O.south) -- (B.north);',r'\end{tikzpicture}',r'\end{document}']
    return '\n'.join(out)+'\n'

def run(cmd,cwd):
    result=subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:
        print(result.stdout[-5000:]);print(result.stderr[-3000:]);raise RuntimeError('Command failed: '+str(cmd[0]))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--out-dir',default=str(HERE/'render'));p.add_argument('--source-only',action='store_true')
    p.add_argument('--xelatex',default=r'C:\Program Files\Latex\miktex\bin\x64\xelatex.exe')
    p.add_argument('--pdftocairo',default=r'C:\Program Files\Latex\miktex\bin\x64\pdftocairo.exe')
    p.add_argument('--pdftoppm',default=r'C:\Users\Rog\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
    a=p.parse_args();out=Path(a.out_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    spec=json.loads((HERE/'structure.json').read_text(encoding='utf-8'))
    sources={'overall_framework':main_source(spec),'q3_relationship':relation_source()}
    for stem,content in sources.items():
        tex=out/(stem+'.tex');tex.write_text(content,encoding='utf-8')
        if a.source_only:continue
        run([a.xelatex,'--disable-installer','-interaction=nonstopmode','-halt-on-error','-no-pdf',tex.name],out)
        run([str(Path(a.xelatex).with_name('xdvipdfmx.exe')),'-q','-o',stem+'.pdf',stem+'.xdv'],out)
        run([a.pdftocairo,'-svg',stem+'.pdf',stem+'.svg'],out)
        run([a.pdftoppm,'-png','-r','180','-singlefile',stem+'.pdf',stem],out)
    if not a.source_only:
        artifacts={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.suffix in ['.tex','.pdf','.svg','.png']}
        (out/'render_manifest.json').write_text(json.dumps({'figure_id':spec['figure_id'],'structure_sha256':hashlib.sha256((HERE/'structure.json').read_bytes()).hexdigest(),'artifacts':artifacts,'commands':'XeLaTeX --disable-installer -no-pdf; xdvipdfmx; pdftocairo -svg; pdftoppm -r 180','engine':run([a.xelatex,'--version'],out).stdout.splitlines()[0]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'source_only':a.source_only,'figures':len(sources)}))

if __name__=='__main__':main()
