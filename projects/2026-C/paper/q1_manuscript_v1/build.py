"""Compile and render the current partial manuscript; no research execution."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
RUNTIME = Path("C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies")
LATEX = Path("C:/Program Files/Latex/miktex/bin/x64")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    subprocess.run([sys.executable, str(HERE / "prepare.py")], check=True)
    build, preview = HERE / "build", HERE / "preview"
    build.mkdir(exist_ok=True)
    preview.mkdir(exist_ok=True)
    commands = []
    for number in (1, 2):
        command = [str(LATEX / "xelatex.exe"), "--disable-installer", "-interaction=nonstopmode", "-halt-on-error", "-no-pdf", f"-output-directory={build}", "paper.tex"]
        commands.append(command)
        with (build / f"xelatex_pass_{number}.txt").open("w", encoding="utf-8") as log:
            subprocess.run(command, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, check=True)
    pdf = HERE / "paper.pdf"
    command = [str(LATEX / "xdvipdfmx.exe"), "-q", "-o", str(pdf), str(build / "paper.xdv")]
    commands.append(command)
    subprocess.run(command, cwd=HERE, check=True)
    command = [str(RUNTIME / "native/poppler/Library/bin/pdftoppm.exe"), "-r", str(args.dpi), "-png", str(pdf), str(preview / "page")]
    commands.append(command)
    subprocess.run(command, cwd=HERE, check=True)
    inputs = sorted(HERE.rglob("*.tex")) + [HERE / "prepare.py", HERE / "build.py"] + sorted((HERE / "figures").glob("*.pdf"))
    record = {"scope": "local_writing_only", "commands": commands, "input_sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}, "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "dpi": args.dpi}
    (build / "build_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdf": str(pdf), "sha256": record["pdf_sha256"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
