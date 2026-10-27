"""Compile and render the standalone front/back sections."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
NAME = "摘要_问题分析_模型评价与参考文献"
LATEX = Path("C:/Program Files/Latex/miktex/bin/x64")
POPPLER = Path("C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin")
build = HERE / "build"
preview = HERE / "preview"
build.mkdir(exist_ok=True)
preview.mkdir(exist_ok=True)
commands = []

for number in (1, 2):
    command = [
        str(LATEX / "xelatex.exe"), "--disable-installer", "-interaction=nonstopmode",
        "-halt-on-error", "-no-pdf", f"-output-directory={build}", NAME + ".tex",
    ]
    commands.append(command)
    with (build / f"pass{number}.txt").open("w", encoding="utf-8") as log:
        subprocess.run(command, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, check=True)

pdf = HERE / (NAME + ".pdf")
command = [str(LATEX / "xdvipdfmx.exe"), "-q", "-o", str(pdf), str(build / (NAME + ".xdv"))]
commands.append(command)
subprocess.run(command, cwd=HERE, check=True)

for old in preview.glob("page-*.png"):
    old.unlink()
command = [str(POPPLER / "pdftoppm.exe"), "-r", "120", "-png", str(pdf), str(preview / "page")]
commands.append(command)
subprocess.run(command, cwd=HERE, check=True)

inputs = list(HERE.glob("*.tex")) + [HERE / "build.py"]
record = {
    "commands": commands,
    "input_sha256": {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
    "scope": "Standalone abstract, four-problem analysis, model evaluation, and consolidated references",
}
(build / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"pdf": str(pdf), "rendered_pages": len(list(preview.glob("page-*.png")))}, ensure_ascii=False))
