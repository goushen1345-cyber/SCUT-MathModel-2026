import copy
import json
from pathlib import Path


project = Path(__file__).resolve().parents[1]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
if state["revision"] != 41 or state["stage"] != "PAPER":
    raise SystemExit("Expected revision 41 at PAPER")
validation = json.loads((project / "paper/final/validation.json").read_text(encoding="utf-8"))
workbooks = json.loads((project / "paper/final/results/workbook_validation.json").read_text(encoding="utf-8"))
if not validation.get("passed") or not workbooks.get("passed"):
    raise SystemExit("Final paper or workbook validation failed")
if validation.get("experiments_added") != 0 or validation.get("frozen_conclusions_modified") is not False:
    raise SystemExit("Paper boundary violated")

candidate = copy.deepcopy(state)
candidate["revision"] = 42
candidate["stage"] = "WAIT_FINAL"
candidate["execution_status"] = "WAITING"
candidate["pending_gate"] = {
    "id": "FINAL",
    "plan_version": "PAPER-FINAL-v1",
    "scope": "PAPER",
    "summary": "已完成17页DOCX/PDF、9图8表及三本最终命名结果表；冻结哈希、数值、文档结构、工作簿和逐页版面核验全部通过，等待最终人工确认。",
    "allowed_actions": "只读查看、解释和审查PAPER-FINAL-v1；可按用户明确意见修订论文展示。未经明确授权不得重开模型、补实验、修改冻结结论、上传或提交。",
    "budget": "全文执行已完成；FINAL点前无实验预算。",
    "stop_condition": "收到用户最终确认或具体修订意见前停止。",
}
candidate["data_scope"]["modeling_authorized"] = "Q1、Q2、Q3均已冻结；U023授权的论文制作已完成并停在FINAL。"
candidate["q3_protocol"]["paper_stage_authorized"] = True
candidate["paper_protocol"].update({
    "status": "WAITING_FOR_FINAL_CONFIRMATION",
    "final_version": "PAPER-FINAL-v1",
    "paper_validation": "PASSED",
    "workbook_validation": "PASSED",
    "docx": "paper/final/2024-C-paper.docx",
    "pdf": "paper/final/2024-C-paper.pdf",
    "page_count": 17,
    "figures": 9,
    "tables": 8,
    "result_workbooks": [
        "paper/final/results/result1_1.xlsx",
        "paper/final/results/result1_2.xlsx",
        "paper/final/results/result2.xlsx",
    ],
    "frozen_files_revalidated": 288,
    "new_experiments_run": 0,
    "frozen_conclusions_modified": False,
    "external_submission_authorized": False,
})
candidate["history"].append({
    "date": "2026-09-08",
    "from_stage": "PAPER",
    "to_stage": "WAIT_FINAL",
    "authorization_id": "U023",
    "reason": "完成PAPER-FINAL-v1：形成17页DOCX/PDF、9图8表和三本最终命名结果表；288项冻结哈希、文档结构、关键数值、工作簿和17页版面独立核验全部通过。新实验0、冻结结论未修改，停FINAL等待人工确认。",
    "artifacts": [
        "paper/manuscript_v1.md", "paper/build_figures.py", "paper/build_paper.py",
        "paper/figures/manifest.json", "paper/final/2024-C-paper.docx", "paper/final/2024-C-paper.pdf",
        "paper/final/results/result1_1.xlsx", "paper/final/results/result1_2.xlsx", "paper/final/results/result2.xlsx",
        "paper/final/results/workbook_validation.json", "paper/final/validation.json", "paper/final/validation_report.md",
        "state/decisions.md", "state/ai_usage_log.md"
    ],
})
(project / "state/proposed.json").write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
