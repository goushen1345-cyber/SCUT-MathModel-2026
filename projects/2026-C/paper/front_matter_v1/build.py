"""Compile the local manuscript and render every page; no research computation."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def find_tool(name, fallback):
    result = shutil.which(name)
    if result:
        return result
    if Path(fallback).is_file():
        return fallback
    raise FileNotFoundError(f"Required tool is not installed: {name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    build = HERE / "build"
    preview = HERE / "preview"
    build.mkdir(exist_ok=True)
    preview.mkdir(exist_ok=True)
    xelatex = find_tool("xelatex", "C:/Program Files/Latex/miktex/bin/x64/xelatex.exe")
    converter = find_tool("xdvipdfmx", "C:/Program Files/Latex/miktex/bin/x64/xdvipdfmx.exe")
    poppler = find_tool("pdftoppm", "C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe")
    commands = []
    for i in range(2):
        command = [xelatex, "--disable-installer", "-interaction=nonstopmode", "-halt-on-error", "-no-pdf", f"-output-directory={build}", "front_matter.tex"]
        commands.append(command)
        with (build / f"xelatex_pass_{i+1}.txt").open("w", encoding="utf-8") as log:
            subprocess.run(command, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, check=True)
    command = [converter, "-q", "-o", str(HERE / "front_matter.pdf"), str(build / "front_matter.xdv")]
    commands.append(command)
    subprocess.run(command, cwd=HERE, check=True)
    command = [poppler, "-r", str(args.dpi), "-png", str(HERE / "front_matter.pdf"), str(preview / "page")]
    commands.append(command)
    subprocess.run(command, cwd=HERE, check=True)
    source = HERE / "front_matter.tex"
    pdf = HERE / "front_matter.pdf"
    record = {
        "commands": commands,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "dpi": args.dpi,
        "scope": "typesetting_only",
    }
    (build / "build_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
