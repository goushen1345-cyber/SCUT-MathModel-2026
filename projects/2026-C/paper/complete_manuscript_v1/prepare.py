"""Assemble the current confirmed paper sections into one reproducible source tree."""
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
Q1 = PAPER / "q1_manuscript_v1"
Q2 = PAPER / "q2_manuscript_v3"
Q3 = PAPER / "q3_manuscript_v2"
Q4 = PAPER / "q4_manuscript_v3"
FB = PAPER / "front_back_sections_v1"
SOURCE_IMAGE = Path(r"C:/Users/Rog/AppData/Local/Temp/codex-clipboard-a3000c17-99b7-4875-b7e6-3433ef7f5276.png")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def write(name: str, value: str) -> None:
    (HERE / name).write_text(value.strip() + "\n", encoding="utf-8")


def between(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end)]


for src, dst in [
    (Q1 / "figures", HERE / "q1_figures"),
    (Q2 / "figures", HERE / "q2_figures"),
    (Q2 / "tables", HERE / "q2_tables"),
    (Q3 / "figures", HERE / "q3_figures"),
    (Q3 / "tables", HERE / "q3_tables"),
    (Q4 / "figures", HERE / "q4_figures"),
]:
    shutil.copytree(src, dst, dirs_exist_ok=True)

(HERE / "figures").mkdir(exist_ok=True)
target_image = HERE / "figures" / "微网系统示意图.png"
if SOURCE_IMAGE.exists():
    shutil.copy2(SOURCE_IMAGE, target_image)
elif not target_image.exists():
    raise FileNotFoundError("The supplied microgrid illustration is unavailable.")
shutil.copy2(Q1 / "result_values.tex", HERE / "result_values.tex")

front_old = read(Q1 / "sections" / "front.tex")
background = between(front_old, "\\section{问题背景}", "\\section{问题重述}")
background = background.replace("\\section{问题背景}", "", 1).strip()
restatement = between(front_old, "\\section{问题重述}", "\\section{问题分析}")
restatement = restatement.replace("\\section{问题重述}", "", 1).strip()
overall = front_old[front_old.index("\\section{总体思路}"):]
overall = overall.replace("\\section{总体思路}", "\\subsection{四问之间的联系}", 1).strip()

front_back = read(FB / "摘要_问题分析_模型评价与参考文献.tex")
abstract = between(front_back, "\\section*{摘\\quad 要}", "\\newpage\n\\section{问题分析}")
analysis = between(front_back, "\\section{问题分析}", "\\section{模型评价与推广}")
back = front_back[front_back.index("\\section{模型评价与推广}"):front_back.rindex("\\end{document}")]

figure = r"""
\begin{figure}[htbp]
  \centering
  \includegraphics[width=\linewidth,trim=8 8 8 8,clip]{微网系统示意图.png}
  \caption{微网系统的供电关系}
  \label{fig:microgrid-system}
\end{figure}
"""
front = "\\section{问题重述}\n\\subsection{问题背景}\n" + background + "\n" + figure + "\n" + restatement + "\n\n" + analysis + "\n" + overall
write("abstract.tex", abstract)
write("front.tex", front)
write("back.tex", back)

assumptions = read(Q1 / "sections" / "assumptions.tex")
assumptions = assumptions.replace("\\section{模型假设}", "\\subsection{模型假设}", 1)
symbols = read(Q1 / "sections" / "symbols.tex")
symbols = symbols.replace("\\section{符号说明}", "\\subsection{符号说明}", 1)
write("assumptions_symbols.tex", "\\section{模型假设与符号说明}\n" + assumptions + "\n" + symbols)

write("data.tex", read(Q1 / "sections" / "data.tex"))

q1 = read(Q1 / "sections" / "question1.tex")
q1 = q1.replace("\\section{模型的建立与求解}", "\\section{问题一的模型建立与求解}", 1)
q1 = q1.replace("\\subsection{问题一的建立与求解}", "\\subsection{求解思路与模型选择}", 1)
q1 = q1.replace("附件1给出了", "\\textbf{全时段电量流线性规划模型。}\n\n附件1给出了", 1)
q1 = q1.replace("\\input{figures/energy_paths.tex}", "\\input{q1_figures/energy_paths.tex}")
write("q1.tex", q1)

q2 = read(Q2 / "chapter.tex")
q2 = re.sub(r"\\subsection\*\{\d+\\quad\s*([^}]*)\}", r"\\subsection{\1}", q2)
q2 = "\\section{问题二的模型建立与求解}\n" + q2
for old in ["forecast", "error", "weight", "margin", "order", "objective", "storage", "bounds", "emergency", "bill"]:
    q2 = q2.replace(f"eq:{old}", f"eq:q2-{old}")
for old in ["compare", "purchase", "storage", "emergency"]:
    q2 = q2.replace(f"tab:{old}", f"tab:q2-{old}")
for old in ["monthly", "days", "sensitivity"]:
    q2 = q2.replace(f"fig:{old}", f"fig:q2-{old}")
q2 = q2.replace("tables/", "q2_tables/")
write("q2.tex", q2)

q3 = read(Q3 / "chapter.tex")
q3 = re.sub(r"\\subsection\*\{\d+\\quad\s*([^}]*)\}", r"\\subsection{\1}", q3)
q3 = "\\section{问题三的模型建立与求解}\n" + q3
q3 = q3.replace("tables/", "q3_tables/")
write("q3.tex", q3)

q4_full = read(Q4 / "问题四的模型建立与求解_修订稿.tex")
q4_body = between(q4_full, "\\begin{document}", "\\begin{thebibliography}")
q4_body = q4_body.replace("\\begin{document}", "", 1)
write("q4.tex", q4_body)

print("Prepared complete manuscript sources and copied all required assets.")
