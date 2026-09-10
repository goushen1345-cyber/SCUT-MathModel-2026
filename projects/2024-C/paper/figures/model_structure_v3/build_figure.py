"""TikZ rendering of the approved shared crop-model structure. No research runs.

Run with a new --out-dir; existing render directories are never overwritten.
The three economic inputs are distributed ports of the approved P3 component.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
TEXBIN = Path(r'C:\Program Files\Latex\miktex\bin\x64')
POPPLER = Path(r'C:\Users\Rog\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin')

PREAMBLE = r'''\documentclass[border=2mm]{standalone}
\usepackage{fontspec,xeCJK,amsmath}
\setmainfont{Times New Roman}
\setCJKmainfont[BoldFont=SimHei]{SimSun}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,calc,backgrounds,fit}
\definecolor{inputfill}{HTML}{F2F3F3}
\definecolor{corefill}{HTML}{F8FAFC}
\definecolor{qone}{HTML}{EEF2EC}
\definecolor{qtwo}{HTML}{EDF2F7}
\definecolor{qthree}{HTML}{F5F0E8}
\tikzset{
 box/.style={draw=black!65,line width=.55pt,fill=white,text=black,align=center,inner sep=3pt,font=\fontsize{9.3}{12.8}\selectfont},
 input/.style={box,fill=inputfill},
 arr/.style={-{Stealth[length=1.7mm,width=1.3mm]},line width=.6pt,draw=black!80},
 wire/.style={line width=.6pt,draw=black!80},
 delta/.style={arr,dashed},
 note/.style={text=black,font=\fontsize{8.2}{10.5}\selectfont,align=center,fill=white,inner sep=1.2pt},
 small/.style={text=black,font=\fontsize{8.2}{10.5}\selectfont,align=left,inner sep=0pt},
 heading/.style={text=black,font=\fontsize{11}{14}\selectfont\bfseries,align=center},
 bridge/.style={preaction={draw=white,line width=2.4pt}}
}
\begin{document}
\begin{tikzpicture}[x=1cm,y=1cm]
'''


def node(name, x, y, w, h, lines, style='box'):
    assert len(lines) <= 3
    body = r'\\'.join((r'\textbf{'+line+'}') if i == 0 else line for i, line in enumerate(lines))
    return fr'\node[{style},text width={w}cm,minimum height={h}cm] ({name}) at ({x},{y}) {{\shortstack[c]{{{body}}}}};'


def figure_source():
    t = [PREAMBLE,
         r'\filldraw[fill=corefill,draw=black!75,line width=.85pt] (0,-1.25) rectangle (13.25,-12.1);',
         r'\node[heading] at (6.6,-1.75) {2024—2030年农作物种植优化：共享混合整数规划};']
    # External inputs and three independent constraint components.
    specs = [
      ('land',2.2,0,3.7,1.0,['土地与适种条件','面积／地类／设施季次'],'input'),
      ('history',7.0,0,3.7,1.0,['2023年种植记录','历史面积／轮作起点'],'input'),
      ('agri',2.2,-2.9,3.6,1.4,['土地与季次约束','适种／季次／水浇模式','启用季满额种植*'],'box'),
      ('rotation',6.65,-2.9,3.6,1.4,['跨年轮作','相邻茬不重种','三年豆类面积代理*'],'box'),
      ('manage',11.05,-2.9,3.6,1.4,['管理约束*',r'单项面积$\geq$地块50\%',r'每作物同期$\leq$7块'],'box'),
      ('decision',2.2,-6.2,3.6,1.65,['种植决策',r'面积 $x\geq0$',r'启用 $y$、模式 $z\in\{0,1\}$'],'box'),
      ('yieldparam',6.5,-4.95,2.8,.6,['亩产 $v$（斤/亩）'],'input'),
      ('quota',10.9,-4.9,3.8,1.0,['正常销售额度 $L$*',r'2023面积$\times$基期亩产','按作物与季次汇总'],'input'),
      ('production',6.5,-6.2,3.35,1.05,['作物产量 $Q$',r'$\displaystyle Q=\sum_i vx$'],'box'),
      ('sales',10.9,-6.2,3.8,1.05,[r'正常销售 $q=\min(Q,L)$','超额部分 $e=Q-q$'],'box'),
      ('costparam',6.5,-7.45,2.8,.6,['亩成本 $c$（元/亩）'],'input'),
      ('cost',6.5,-8.5,3.35,1.0,['种植支出',r'$\displaystyle C=\sum cx$'],'box'),
      ('revenue',10.9,-8.5,3.8,1.0,['销售收入',r'$\displaystyle R=\sum p(q+\beta e)$'],'box'),
      ('priceparam',15.15,-8.5,3.1,1.0,['价格 $p$（元/斤）','基期取区间中点'],'input'),
      ('plan',2.2,-11.0,3.6,1.35,['七年种植方案','地块—作物—年季面积','问题三沿用问题二方案'],'box'),
      ('results',15.35,-11.0,3.5,1.35,['方案表现与建议','收益／尾部风险／管理','参数更新／轮作台账'],'box'),
    ]
    for spec in specs:
        t.append(node(*spec))
    # Income and cost compose one benefit function, with explicit use ports.
    t += [r'\filldraw[fill=white,draw=black!70,line width=.7pt] (4.35,-9.65) rectangle (13.0,-11.95);',
          r'\node[heading,font=\fontsize{10.5}{13}\selectfont\bfseries] at (8.675,-10.12) {七年净收益 $\Pi=R-C$};',
          node('opt',6.5,-11.0,3.7,1.0,[r'优化：$\max\Pi$','选择种植面积'], 'box'),
          node('eval',10.9,-11.0,3.7,1.0,[r'评价：$\Pi(x,\omega)$','固定面积，按情景计价'],'box'),
          r'\node[note] at (11.05,-3.82) {收益相近时少启用};']
    # Algebraic edges, not steps of research.
    t += [
      r'\draw[arr] (land.south) -- (agri.north);',
      r'\draw[arr] (history.south) -- (7,-.85) -- (12.85,-.85) -- (12.85,-2.05) -| (rotation.north);',
      r'\draw[arr] (history.east) -- (13.65,0) -- (13.65,-4.9) -- (quota.east);',
      r'\node[note,rotate=90] at (13.65,-2.0) {定义基期额度};',
      r'\draw[wire] (agri.south) -- (2.2,-4.08) -- (11.05,-4.08) -- (manage.south);',
      r'\draw[wire] (rotation.south) -- (6.65,-4.08);',
      r'\draw[arr] (2.2,-4.08) -- node[note]{限定} (decision.north);',
      r'\draw[arr] (decision.east) -- node[note]{$x$} (production.west);',
      r'\draw[arr] (yieldparam.south) -- (production.north);',
      r'\draw[arr] (production.east) -- (sales.west);',
      r'\draw[arr] (quota.south) -- (sales.north);',
      r'\draw[arr] (decision.south) -- (2.2,-8.5) -- node[note]{$x$} (cost.west);',
      r'\draw[arr] (costparam.south) -- (cost.north);',
      r'\draw[arr] (sales.south) -- node[note]{销售数量} (revenue.north);',
      r'\draw[arr] (priceparam.west) -- (revenue.east);',
      r'\draw[arr] (cost.south) -- node[note]{$-C$} (6.5,-9.65);',
      r'\draw[arr] (revenue.south) -- node[note]{$+R$} (10.9,-9.65);',
      r'\draw[arr] (opt.west) -- (plan.east);',
      r'\draw[arr] (eval.east) -- (results.west);',
      r'\draw[arr] (2.2,-8.5) -- node[note]{面积表} (plan.north);',
      r'\draw[arr] (plan.south) -- (2.2,-12.5) -- node[note,pos=.85]{固定面积} (10.9,-12.5) -- (eval.south);',
    ]
    # Two typed parameter interfaces prevent a scenario path entering max Pi.
    t += [node('planning',4.4,-13.75,7.4,.72,[r'确定方案参数：$L,v,c,p,\beta$'],'input'),
          node('scenario',13.05,-13.75,7.4,.72,[r'固定方案评价参数：$L^\omega,v^\omega,c^\omega,p^\omega$'],'input'),
          r'\draw[delta,bridge] (planning.north) -- (4.4,-12.85) -| (opt.south);',
          r'\draw[delta,bridge] (scenario.north) -- (13.05,-12.82) -- (12.4,-12.82) -- (12.4,-11.8) -- (eval.south east);',
          r'\node[small,anchor=west] at (.1,-13.1) {虚线：参数增量};']
    # Model deltas: no candidate labels or sequential Q1 -> Q2 -> Q3 arrows.
    delta_specs = [
      ('qone',2.65,-15.25,4.7,1.15,['问题一：稳定条件','$L,v,c,p$ 保持基期',r'超额计价 $\beta=0$／$0.5$'],'box,fill=qone'),
      ('qtwoplan',8.0,-15.25,4.7,1.15,['问题二：年度趋势','$L,c,p$ 用中间趋势定方案','亩产取基期'],'box,fill=qtwo'),
      ('qtwoeval',8.0,-17.05,4.7,1.15,['问题二：参数波动','销量／亩产／部分菌价','固定面积评价收益与风险'],'box,fill=qtwo'),
      ('qthreecorr',14.2,-15.25,5.3,1.15,['问题三：参数关联*','市场／通胀／天气因子','成本／菜价另增随机趋势'],'box,fill=qthree'),
      ('qthreeresponse',14.2,-17.05,5.3,1.15,['问题三：替代与互补*',r'邻作物相对价格 $\to L^\omega$','只修正销售额度'],'box,fill=qthree')]
    for spec in delta_specs:
        t.append(node(*spec))
    t += [
      r'\draw[delta] (qone.north) -- (2.65,-14.1);',
      r'\draw[delta] (qtwoplan.north) -- (8,-14.1);',
      r'\draw[delta] (qtwoeval.east) -- (10.65,-17.05) -- (10.65,-14.1);',
      r'\draw[delta] (qthreecorr.north) -- (14.2,-14.1);',
      r'\draw[delta] (qthreeresponse.east) -- (17.3,-17.05) -- (17.3,-13.75) -- (scenario.east);',
      r'\node[small,anchor=north west,text width=5.1cm] at (.1,-16.3) {问题二、三主销售规则：$\beta=0.5$。\\经济参数按地类、作物及季次匹配；\\正常销售额度按全村作物—年—季共享。};',
      r'\node[small,anchor=north west,text width=17cm] at (.1,-18.05) {* 销售额度为历史产量代理，真实销量未知；豆类采用累计面积代理。\\* 满种、50\%及7块为模型约定（同期指同年同季）；关系和概率为模拟设定。\\* 问题三另改变成本、菜价趋势设定，不能解释为纯相关效应；相关核验范围见正文。};',
      r'\end{tikzpicture}',r'\end{document}']
    return '\n'.join(t)+'\n'


def run(cmd, cwd):
    r = subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if r.returncode:
        raise RuntimeError(r.stdout[-4000:]+'\n'+r.stderr[-1500:])
    return r


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out-dir',required=True)
    p.add_argument('--tex-bin',type=Path,default=TEXBIN)
    p.add_argument('--poppler',type=Path,default=POPPLER)
    p.add_argument('--source-only',action='store_true')
    a=p.parse_args();out=Path(a.out_dir).resolve()
    out.mkdir(parents=True,exist_ok=False)
    tex=out/'model_framework.tex';tex.write_text(figure_source(),encoding='utf-8')
    commands=[]
    if not a.source_only:
        commands=[
          [a.tex_bin/'xelatex.exe','--disable-installer','-interaction=nonstopmode','-halt-on-error','-no-pdf',tex.name],
          [a.tex_bin/'xdvipdfmx.exe','-q','-o','model_framework.pdf','model_framework.xdv'],
          [a.tex_bin/'pdftocairo.exe','-svg','model_framework.pdf','model_framework.svg'],
          [a.poppler/'pdftoppm.exe','-png','-r','180','-singlefile','model_framework.pdf','model_framework']]
        for c in commands:run(c,out)
    manifest={'figure_id':'FIG-MODEL-03','approved_structure':'FIG-MODEL-03-STRUCTURE-v1',
              'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'approval_structure_sha256':hashlib.sha256((HERE/'content_review.md').read_bytes()).hexdigest(),
              'commands':[[str(x) for x in c] for c in commands],
              'fonts':['SimSun','SimHei','Times New Roman'],
              'artifacts':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.suffix in ['.tex','.pdf','.svg','.png']}}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'source_only':a.source_only}))


if __name__=='__main__':main()
