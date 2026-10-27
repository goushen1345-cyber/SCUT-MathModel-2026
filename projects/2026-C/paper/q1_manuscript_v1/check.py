"""Check manuscript provenance, numbers and PDF structure without rerunning research."""
from pathlib import Path
import hashlib
import json
import re
import sys

import pdfplumber
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
STATE_HASH = "3216d997f1bf13725d1ae346b754900ea1fe8cfab2993cfe56c45ecce91c68f5"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    sources = {name: sha(PROJECT / name) == expected for name, expected in manifest["source_sha256"].items()}
    assert all(sources.values()), sources
    assert sha(PROJECT / "state/state.json") == STATE_HASH
    reader = PdfReader(HERE / "paper.pdf")
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages)
    (HERE / "build/paper_text.txt").write_text(text, encoding="utf-8")
    compact = re.sub(r"\s+", "", text)
    sections = ["模型假设", "符号说明", "数据预处理与探索性分析", "模型的建立与求解", "问题一的建立与求解", "模型比较与方案选择", "模型检验与初始储电量敏感性分析"]
    assert all(s in compact for s in sections)
    qtext = (HERE / "sections/question1.tex").read_text(encoding="utf-8")
    keys = set(re.findall(r"\\([A-Z][A-Za-z]+)\b", qtext)) & set(manifest["result_macros_full_precision"])
    numeric = {key: f"{manifest['result_macros_full_precision'][key]:.2f}" in compact for key in keys}
    assert all(numeric.values()), numeric
    log = (HERE / "build/paper.log").read_text(encoding="utf-8", errors="replace")
    bad_log = re.findall(r".*(?:Overfull|Underfull|undefined|Missing character|multiply defined).*", log)
    assert not bad_log, bad_log
    forbidden = [word for word in ("WAIT_D", "G0", "Skill", "审批", "run_id", "冻结", "此处待补", "TODO", "???") if word in compact]
    assert not forbidden, forbidden
    for i, page in enumerate(reader.pages):
        assert len(pages[i].strip()) > 100
        assert abs(float(page.mediabox.width) - 595.276) < 1
        assert abs(float(page.mediabox.height) - 841.89) < 1
    geometry = []
    nonblack = []
    with pdfplumber.open(HERE / "paper.pdf") as pdf:
        for number, page in enumerate(pdf.pages, 1):
            chars = [c for c in page.chars if c.get("text", "").strip()]
            outside = [c.get("text") for c in chars if c["x0"] < 0 or c["x1"] > page.width + .5 or c["top"] < 0 or c["bottom"] > page.height + .5]
            assert not outside, (number, outside)
            geometry.append({"page": number, "characters": len(chars), "min_x": min(c["x0"] for c in chars), "max_x": max(c["x1"] for c in chars), "min_top": min(c["top"] for c in chars), "max_bottom": max(c["bottom"] for c in chars)})
            for c in chars:
                color = c.get("non_stroking_color")
                if color is None:
                    continue
                if isinstance(color, (int, float)):
                    black = abs(color) < 1e-8
                elif len(color) in (1, 3):
                    black = all(abs(x) < 1e-8 for x in color)
                elif len(color) == 4:
                    black = abs(color[3]-1) < 1e-8
                else:
                    black = False
                if not black:
                    nonblack.append({"page": number, "text": c["text"], "color": color})
    assert not nonblack, nonblack[:20]
    report = PROJECT / "paper_evidence/问题一模型详细讲解报告.md"
    report_text = report.read_text(encoding="utf-8")
    assert not [c for c in report_text if ord(c)<32 and c not in "\n\r\t"]
    links = re.findall(r"\]\(([^)]+)\)", report_text)
    missing = [p for p in links if not Path(p).is_file()]
    assert not missing, missing
    expected_report_numbers = ["35126.85", "38276.64", "37944.35", "8.23%", "7.43%", "59482.70", "0.2063%", "0.8054%"]
    assert all(n in report_text for n in expected_report_numbers)
    result = {
        "scope": "manuscript_consistency_checks_not_new_scientific_validation",
        "page_count": len(pages), "source_matches": sources, "numbers_from_saved_results": numeric,
        "state_unchanged": True, "state_sha256": STATE_HASH,
        "research_stage": "WAIT_D", "model_frozen": False, "new_research_runs": 0,
        "page_geometry": geometry, "nonblack_text": nonblack, "latex_layout_errors": bad_log,
        "report_link_count": len(links), "report_character_count": len(report_text),
        "pdf_sha256": sha(HERE / "paper.pdf"), "report_sha256": sha(report),
        "visual_review": "AI inspected rendered pages 1-14; corrected energy labels/routes and reduced avoidable result-page whitespace; rechecked affected pages 9-14. Not human review.",
        "known_build_warnings": "Local LaTeX requested/newer release messages and CJK font redefinition warnings; successful build, no missing characters or unresolved references.",
        "limits": "Current manuscript ends at Q1; no abstract, later-question models/results, whole-paper conclusion or submission-ready claim. Last page partial because authorized content ends here.",
        "python": sys.version,
    }
    (HERE / "build/qa.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(pages), "matched_result_values": len(numeric), "report_links": len(links), "state_unchanged": True, "all_text_black": not nonblack}, ensure_ascii=False))

if __name__ == "__main__":
    main()
