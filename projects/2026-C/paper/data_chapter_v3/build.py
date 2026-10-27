"""Typeset the local data chapter and render its actual PDF pages."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def find_tool(name, fallback):
    found = shutil.which(name)
    if found:
        return found
    if Path(fallback).is_file():
        return fallback
    raise FileNotFoundError(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    build = HERE / "build"
    preview = HERE / "preview"
    build.mkdir(exist_ok=True)
    preview.mkdir(exist_ok=True)
    latex = find_tool("xelatex", "C:/Program Files/Latex/miktex/bin/x64/xelatex.exe")
    converter = find_tool("xdvipdfmx", "C:/Program Files/Latex/miktex/bin/x64/xdvipdfmx.exe")
    poppler = find_tool("pdftoppm", "C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe")
    commands = []
    for number in (1, 2):
        command = [latex, "--disable-installer", "-interaction=nonstopmode", "-halt-on-error", "-no-pdf", f"-output-directory={build}", "data_chapter.tex"]
        commands.append(command)
        with (build / f"xelatex_pass_{number}.txt").open("w", encoding="utf-8") as log:
            subprocess.run(command, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, check=True)
    pdf = HERE / "data_chapter.pdf"
    command = [converter, "-q", "-o", str(pdf), str(build / "data_chapter.xdv")]
    commands.append(command)
    subprocess.run(command, cwd=HERE, check=True)
    command = [poppler, "-r", str(args.dpi), "-png", str(pdf), str(preview / "page")]
    commands.append(command)
    subprocess.run(command, cwd=HERE, check=True)
    figures = HERE.parent / "figures" / "eda-v2"
    inputs = [HERE / "data_chapter.tex", HERE / "build.py"] + [figures / f"{stem}.pdf" for stem in (
        "01_reference_day", "02_year_and_month", "06_prices_and_weekdays", "07_forecast_accuracy")]
    record = {
        "scope": "local_manuscript_typesetting_only",
        "commands": commands,
        "input_sha256": {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "dpi": args.dpi,
    }
    (build / "build_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdf": str(pdf), "pdf_sha256": record["pdf_sha256"], "dpi": args.dpi}, ensure_ascii=False))


if __name__ == "__main__":
    main()
