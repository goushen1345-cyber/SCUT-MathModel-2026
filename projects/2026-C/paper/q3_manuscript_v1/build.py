"""Compile and render the standalone Q3 chapter."""
from pathlib import Path
import hashlib, json, subprocess

HERE = Path(__file__).resolve().parent
NAME = "问题三的模型建立与求解"
LATEX = Path("C:/Program Files/Latex/miktex/bin/x64")
POPPLER = Path("C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin")
build = HERE / "build"
preview = HERE / "preview"
build.mkdir(exist_ok=True)
preview.mkdir(exist_ok=True)
commands = []
for number in (1, 2):
    command = [str(LATEX/"xelatex.exe"), "--disable-installer", "-interaction=nonstopmode", "-halt-on-error", "-no-pdf", f"-output-directory={build}", NAME+".tex"]
    commands.append(command)
    with (build/f"pass{number}.txt").open("w", encoding="utf-8") as log:
        subprocess.run(command, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, check=True)
pdf = HERE / (NAME+".pdf")
command = [str(LATEX/"xdvipdfmx.exe"), "-q", "-o", str(pdf), str(build/(NAME+".xdv"))]
commands.append(command)
subprocess.run(command, cwd=HERE, check=True)
command = [str(POPPLER/"pdftoppm.exe"), "-r", "120", "-png", str(pdf), str(preview/"page")]
commands.append(command)
subprocess.run(command, cwd=HERE, check=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


inputs = list(HERE.glob("*.tex")) + list((HERE/"tables").glob("*.tex")) + list((HERE/"figures").glob("*.pdf")) + [HERE/"prepare.py", HERE/"build.py", HERE/"paper_findings.json"]
(build/"record.json").write_text(json.dumps({"commands": commands, "input_sha256": {str(path.relative_to(HERE)): sha(path) for path in inputs}, "pdf_sha256": sha(pdf), "scope": "local Q3 writing only"}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"pdf": str(pdf), "rendered_pages": len(list(preview.glob("page-*.png")))}, ensure_ascii=False))
