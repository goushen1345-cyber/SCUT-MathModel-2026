"""Check the revised standalone Q4 manuscript without running research models."""
from pathlib import Path
import hashlib
import json
import pdfplumber

HERE = Path(__file__).resolve().parent
P = HERE.parents[1]
PDF = HERE / "问题四的模型建立与求解_修订稿.pdf"
TEX = HERE / "问题四的模型建立与求解_修订稿.tex"

with pdfplumber.open(PDF) as document:
    pages = [page.extract_text() or "" for page in document.pages]
text = "\n".join(pages)

assert len(pages) == 5
for required in [
    "8 问题四的模型建立与求解",
    "滚动提升树",
    "滚动岭回归",
    "14248570.87",
    "13822901.35",
    "波动电价下三种价格方法的比较",
    "问题四指定日期的购电与储电结果",
    "树复杂度与日内价格更新的费用检验",
]:
    assert required in text, required

for forbidden in ["G0", "Skill", "审批", "P2-full", "run_compare", "WAIT_D", "�"]:
    assert forbidden not in text, forbidden

log = (HERE / "build" / "pass2.txt").read_text(encoding="utf-8", errors="replace")
assert "Overfull" not in log
assert "Missing character" not in log
assert "undefined on input line" not in log
assert "There were undefined references" not in log

state = P / "state" / "state.json"
source_pdf = Path("E:/文档/xwechat_files/wxid_9cspft7j507912_dc1e/temp/RWTemp/2026-09/c3fdd19327d183da9a0ef2999900bf5e/9_12_2.pdf")
result = {
    "scope": "Q4 writing revision only",
    "pdf_pages": len(pages),
    "printed_page_range": "26-30",
    "continued_numbering": {"section": 8, "tables": "12-14", "figure": 15, "equations": "23-28"},
    "reference_manuscript_pages_read": 25,
    "reference_pdf_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
    "state_sha256": hashlib.sha256(state.read_bytes()).hexdigest(),
    "tex_sha256": hashlib.sha256(TEX.read_bytes()).hexdigest(),
    "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
    "new_model_fits": 0,
    "new_optimization_solves": 0,
    "visual_review": "All five rendered pages checked by the main assistant; not human approval",
}
(HERE / "qa.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
