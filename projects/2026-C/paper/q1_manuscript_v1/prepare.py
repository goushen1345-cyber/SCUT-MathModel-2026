"""Assemble already authorized text/figures and saved result values; never solve."""
from pathlib import Path
import hashlib
import json
import re
import shutil

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    front_source = HERE.parent / "front_matter_v1/front_matter.tex"
    data_source = HERE.parent / "data_chapter_v3/data_chapter.tex"
    front = front_source.read_text(encoding="utf-8")
    front = front.split(r"\begin{document}", 1)[1].split(r"\section*{5 ", 1)[0]
    front = re.sub(r"\\(subsection|section)\*\{\d+(?:\.\d+)? ([^}]+)\}", r"\\\1{\2}", front)
    front = front.replace(r"\newpage", "").replace("初步总体思路", "总体思路")
    start = front.index("完整购电结果按10分钟间隔提交")
    end = front.index("论文按题目指定格式展示", start)
    front = front[:start] + (
        "完整购电结果按10分钟间隔提交。问题一至问题三分别填写\\texttt{result1.xlsx}、"
        "\\texttt{result2.xlsx}和\\texttt{result3.xlsx}；问题四的两条分支分别填写"
        "\\texttt{result4-2.xlsx}和\\texttt{result4-3.xlsx}。问题二至问题四的完整结果覆盖"
        "2025年2月1日至12月31日，除计划购电和储能记录外，分别保留紧急购电及题目要求的调整记录。\n\n"
    ) + front[end:]
    (HERE / "sections/front.tex").write_text(front.strip() + "\n", encoding="utf-8")
    data = data_source.read_text(encoding="utf-8").split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    data = re.sub(r"\\(subsection|section)\*\{\d+(?:\.\d+)? ([^}]+)\}", r"\\\1{\2}", data)
    data = data.replace("以下日均、月均功率均由相应采样值取平均得到。", "以下日均、月均功率按原表日期与采样标签分组取平均；原表末尾的次日零点仍随原标签参与这些描述统计。调度计算则按实际区间建立时间映射，问题一的周期零点单独对应到首段。")
    (HERE / "sections/data.tex").write_text(data.strip() + "\n", encoding="utf-8")
    close = PROJECT / "questions/Q1/runs/20260911-close-v1/outputs/summary.json"
    compare = PROJECT / "questions/Q1/runs/20260911-compare-v1/outputs/summary.json"
    interpretation = PROJECT / "questions/Q1/runs/20260911-compare-v1/outputs/interpretation.json"
    c, b, info = read_json(close), read_json(compare), read_json(interpretation)
    m = c["main_totals"]
    base = {r["candidate"]: r for r in b["comparison"]}
    macros = {
        "MainCost": m["cost_yuan"], "MainPurchase": m["purchase_kwh"],
        "MainCharge": m["charge_kwh"], "MainDischarge": m["discharge"],
        "MainLoss": m["loss_kwh"], "PvCharge": m["pv_charge"],
        "RuleCost": base["03"]["cost_yuan"], "ReserveCost": base["10"]["cost_yuan"],
        "RulePurchase": base["03"]["purchase_kwh"], "ReservePurchase": base["10"]["purchase_kwh"],
        "RuleSaving": info["savings"]["03_to_04"]["yuan"],
        "ReserveSaving": info["savings"]["10_to_04"]["yuan"],
        "RuleSavingPct": info["savings"]["03_to_04"]["percent"],
        "ReserveSavingPct": info["savings"]["10_to_04"]["percent"],
        "ExtraPurchase": info["extra_grid_04_vs03_kwh"],
        "EveningState": info["events"]["04"]["state_at_20"],
        "PeakRulePurchase": info["events"]["03"]["peak_purchase_kwh"],
        "LowInitialCost": c["sensitivity"][0]["cost_yuan"],
        "HighInitialCost": c["sensitivity"][2]["cost_yuan"],
        "LowInitialDelta": c["sensitivity"][0]["cost_difference_yuan"],
        "HighInitialDelta": c["sensitivity"][2]["cost_difference_yuan"],
        "LowInitialPct": c["sensitivity"][0]["cost_difference_pct"],
        "HighInitialPct": c["sensitivity"][2]["cost_difference_pct"],
    }
    for label, row in zip(("Ten", "Twelve", "Fourteen", "Sixteen", "Eighteen", "Twenty"), c["table1"]):
        macros["Buy" + label] = row["purchase_kwh"]
    for label, row in zip(("A", "B", "C", "D", "E", "F"), c["table2"]):
        macros["Charge" + label] = row["charge_kwh"]
        macros["Discharge" + label] = row["discharge_kwh"]
    (HERE / "result_values.tex").write_text(
        "% Generated only from saved research outputs; units defined in text.\n" +
        "\n".join("\\newcommand{\\" + key + "}{" + f"{value:.2f}" + "}" for key, value in macros.items()) + "\n", encoding="utf-8")
    sources = [front_source, data_source, close, compare, interpretation]
    figure_mapping = {}
    for stem in ("01_reference_day", "02_year_and_month", "06_prices_and_weekdays", "07_forecast_accuracy"):
        figure_mapping[HERE.parent / f"figures/eda-v2/{stem}.pdf"] = HERE / f"figures/{stem}.pdf"
    figure_mapping[PROJECT / "questions/Q1/runs/20260911-compare-v1/figures-v4/01_daily_dispatch.pdf"] = HERE / "figures/q1_daily_dispatch.pdf"
    for source, destination in figure_mapping.items():
        shutil.copyfile(source, destination)
        assert digest(source) == digest(destination)
        sources.append(source)
    record = {
        "scope": "paper_text_and_saved_results_only_no_new_solves",
        "research_state_sha256": digest(PROJECT / "state/state.json"),
        "source_sha256": {str(p.relative_to(PROJECT)): digest(p) for p in sources},
        "result_macros_full_precision": macros,
        "figure_copies": {str(v.relative_to(HERE)): str(k.relative_to(PROJECT)) for k, v in figure_mapping.items()},
    }
    (HERE / "source_manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Prepared current manuscript sources and saved numerical values.")

if __name__ == "__main__":
    main()
