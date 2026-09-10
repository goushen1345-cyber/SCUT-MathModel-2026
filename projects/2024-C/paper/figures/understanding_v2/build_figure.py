"""Render a topic-supported planting model sketch; no data or model execution."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
POSITIONS = {
    "q2": (5.0, 10.25, 4.0, 1.0),
    "q3": (12.0, 10.25, 4.0, 1.0),
    "constraints": (2.5, 8.25, 3.7, 1.2),
    "decision": (6.65, 8.25, 3.7, 1.2),
    "production": (6.65, 6.55, 3.5, 1.1),
    "sales": (6.65, 4.85, 3.5, 0.9),
    "revenue": (6.65, 1.45, 3.5, 0.9),
    "cost": (2.5, 3.15, 3.3, 0.9),
    "value": (6.65, -0.35, 3.5, 1.0),
    "yield": (12.0, 6.55, 3.0, 0.7),
    "demand": (12.0, 4.85, 3.0, 0.7),
    "unitcost": (12.0, 3.15, 3.0, 0.7),
    "pricing": (12.0, 1.45, 3.0, 0.7),
    "q1": (12.0, -0.35, 3.4, 1.0),
}

PREAMBLE = r'''\documentclass[border=2mm]{standalone}
\usepackage{fontspec}
\usepackage{xeCJK}
\setmainfont{Times New Roman}
\setCJKmainfont[BoldFont=SimHei]{SimSun}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,calc,backgrounds}
\tikzset{
 box/.style={draw=black,fill=white,text=black,line width=.65pt,align=center,inner sep=4pt,font=\fontsize{10}{13}\selectfont},
 delta/.style={box,rounded corners=2pt,line width=.85pt},
 arrow/.style={-{Stealth[length=1.8mm,width=1.4mm]},line width=.7pt,draw=black},
 ext/.style={arrow,dashed},
 label/.style={fill=white,text=black,inner sep=2pt,font=\fontsize{8.8}{11}\selectfont,align=center},
 group/.style={draw=black,dashed,line width=.55pt,rounded corners=2pt},
}
\begin{document}
\begin{tikzpicture}[x=1cm,y=1cm]
'''

def esc(s):
    return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("−", r"$-$").replace("×", r"$\times$")

def source(spec):
    out = [PREAMBLE]
    # The groups are rendering devices for already defined edges, not new model nodes.
    out.extend([
        r'\draw[group] (9.7,.78) rectangle (14.35,7.35);',
        r'\draw[group] (10.0,.98) rectangle (14.0,5.6);',
        r'\node[label,anchor=south] at (12,7.35) {四类参数};',
        r'\node[label,anchor=south] at (12,5.6) {销售、价格与成本关系};',
    ])
    for n in spec["nodes"]:
        x, y, w, h = POSITIONS[n["id"]]
        lines = n["label"].split("\n")
        if n["id"] == "constraints":
            lines = ["农业与管理约束", "面积·适种·季次", "重茬·豆类覆盖", "适度集中"]
        if n["id"] == "q1":
            lines = ["Q1：稳定条件", "超额滞销／基年半价"]
        body = r"\\".join((r"\textbf{" + esc(line) + "}") if i == 0 else esc(line) for i, line in enumerate(lines))
        style = "delta" if n["layer"] == "delta" else "box"
        if n["id"] == "decision":
            style += ",line width=1.1pt"
        out.append(fr'\node[{style},text width={w}cm,minimum height={h}cm] ({n["id"]}) at ({x},{y}) {{{body}}};')
    out.extend([
        r'\draw[arrow] (constraints.east) -- (decision.west);',
        r'\draw[arrow] (decision.south) -- (production.north);',
        r'\draw[arrow] (yield.west) -- (production.east);',
        r'\draw[arrow] (production.south) -- (sales.north);',
        r'\draw[arrow] (demand.west) -- (sales.east);',
        r'\draw[arrow] (sales.south) -- (revenue.north);',
        # A white bridge preserves the vertical quantity line at the one crossing.
        r'\draw[arrow,preaction={draw=white,line width=3pt}] (unitcost.west) -- (cost.east);',
        r'\draw[arrow] (decision.south west) -- (4.55,7.38) -- (4.55,3.62) -- (cost.north east);',
        r'\node[label,rotate=90] at (4.55,5.5) {种植面积};',
        r'\draw[arrow] (pricing.west) -- (revenue.east);',
        r'\draw[arrow] (revenue.south) -- (value.north);',
        r'\draw[arrow] (cost.south) -- (2.5,-.35) -- node[label,above] {扣除} (value.west);',
        r'\draw[ext] (q1.north) -- (pricing.south);',
        # Q2 -> all four parameter nodes, collapsed to an enclosing-group endpoint.
        r'\draw[ext] (q2.south) -- (5,9.35) -- (12,9.35) -- (12,7.65);',
        r'\node[label,above] at (8.4,9.35) {参数随未来变化};',
        # Q3 -> demand, pricing, unitcost, collapsed to the nested group endpoint.
        r'\draw[ext] (q3.east) -- (15,10.25) -- (15,5.6) -- (14.0,5.6);',
        r'\node[label,rotate=90] at (15,7.75) {替代互补与联合变化};',
        # Risk is a distinct evaluation requirement, not a declared objective term.
        r'\draw[ext] (q2.west) -- (.3,10.25) -- (.3,-1.45) -- (6.65,-1.45) -- (value.south);',
        r'\node[label,above] at (3.45,-1.45) {Q2 另增种植风险评价};',
        r'\node[label,anchor=west] at (.6,-2.05) {实线：约束与核算关系\qquad 虚线：各问新增条件或评价要求};',
        r'\node[label,anchor=west,font=\fontsize{9}{11}\selectfont] at (.6,-2.55) {*销售上限来源、价格取值及Q2/Q3超额处置口径待定。};',
        r'\node[label,anchor=west,font=\fontsize{9}{11}\selectfont] at (.6,-3.02) {题意要素草图，数学形式未定；基年为2023年。};',
        r'\end{tikzpicture}', r'\end{document}',
    ])
    return "\n".join(out) + "\n"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(args, cwd):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stdout[-7000:])
        print(r.stderr[-5000:])
        raise RuntimeError("Command failed: " + str(args[0]))
    return r.stdout

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--source-only", action="store_true")
    p.add_argument("--xelatex", default=r"C:\Program Files\Latex\miktex\bin\x64\xelatex.exe")
    p.add_argument("--pdftoppm", default=r"C:\Users\Rog\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe")
    a = p.parse_args()
    out = Path(a.out_dir).resolve()
    out.relative_to(HERE)
    if out.exists():
        raise FileExistsError("Use a new output directory; prior figures are preserved.")
    out.mkdir(parents=True)
    spec = json.loads((HERE / "structure.json").read_text(encoding="utf-8"))
    tex = out / "framework.tex"
    tex.write_text(source(spec), encoding="utf-8")
    if a.source_only:
        print(tex)
        return
    commands = [
        [a.xelatex,"--disable-installer","-interaction=nonstopmode","-halt-on-error","-no-pdf",tex.name],
        [str(Path(a.xelatex).with_name("xdvipdfmx.exe")),"-q","-o","framework.pdf","framework.xdv"],
        [a.pdftoppm,"-png","-r","220","-singlefile","framework.pdf","framework"],
    ]
    logs = []
    for cmd in commands:
        logs.append({"command": cmd, "stdout": run(cmd, out)})
    (out / "commands.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {x.name:sha(x) for x in out.iterdir() if x.suffix in (".tex",".pdf",".png")}
    metadata = {
        "figure_id":spec["figure_id"], "structure_sha256":sha(HERE/"structure.json"),
        "builder_sha256":sha(Path(__file__)), "artifacts":artifacts,
        "python":sys.version,"engine":run([a.xelatex,"--version"],out).splitlines()[0],
        "fonts":["SimSun","SimHei","Times New Roman"],
        "data_processing_or_experiments":False,
        "collapsed_edges":{"Q2_parameter_group":[["q2",x] for x in ("yield","demand","pricing","unitcost")],
            "Q3_joint_group":[["q3",x] for x in ("demand","pricing","unitcost")]},
        "Q2_risk":"Separate dashed arrow to seven-year evaluation; no risk metric or objective selected.",
    }
    (out/"manifest.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(out),"artifacts":artifacts},ensure_ascii=False))

if __name__ == "__main__":
    main()
