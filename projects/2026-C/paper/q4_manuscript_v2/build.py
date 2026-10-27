"""Compile the revised standalone Q4 section and render all pages."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
NAME = "问题四的模型建立与求解_修订稿"
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
command = [str(POPPLER / "pdftoppm.exe"), "-r", "110", "-png", str(pdf), str(preview / "page")]
commands.append(command)
subprocess.run(command, cwd=HERE, check=True)

inputs = list(HERE.glob("*.tex")) + list((HERE / "figures").glob("*.pdf")) + [HERE / "build.py"]
record = {
    "commands": commands,
    "input_sha256": {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
    "scope": "Revised standalone Q4 writing only; numbering continues after supplied 25-page manuscript",
}
(build / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"pdf": str(pdf), "rendered_pages": len(list(preview.glob("page-*.png")))}, ensure_ascii=False))

