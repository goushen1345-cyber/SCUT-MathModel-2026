"""Compile PDF: try xelatex, fallback to reportlab."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEX_DIR = ROOT / "latex"
OUT_PDF = ROOT / "output" / "report.pdf"


def try_xelatex() -> bool:
    if not shutil.which("xelatex"):
        return False
    for _ in range(2):
        r = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "main.tex"],
            cwd=LATEX_DIR,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0 and not (LATEX_DIR / "main.pdf").exists():
            return False
    src = LATEX_DIR / "main.pdf"
    if src.exists():
        for dst in [OUT_PDF, OUT_PDF.with_name("report_national.pdf")]:
            try:
                shutil.copy(src, dst)
            except PermissionError:
                alt = dst.with_name(dst.stem + "_new.pdf")
                shutil.copy(src, alt)
                print("Permission denied for", dst, "; wrote", alt)
        return True
    return False


def build_reportlab_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, PageBreak

    import pandas as pd

    # register Chinese font if available
    font_paths = [
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    cn_font = "Helvetica"
    for fp in font_paths:
        if Path(fp).exists():
            try:
                pdfmetrics.registerFont(TTFont("CN", fp))
                cn_font = "CN"
                break
            except Exception:
                pass

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CN", fontName=cn_font, fontSize=11, leading=16))
    styles.add(ParagraphStyle(name="CNTitle", fontName=cn_font, fontSize=16, leading=22, spaceAfter=12))
    styles.add(ParagraphStyle(name="CNH", fontName=cn_font, fontSize=13, leading=18, spaceBefore=10, spaceAfter=6))

    q1 = pd.read_csv(ROOT / "output/tables/q1_top50_suppliers.csv")
    q2 = pd.read_csv(ROOT / "output/tables/q2_summary.csv").iloc[0]
    q3 = pd.read_csv(ROOT / "output/tables/q3_summary.csv").iloc[0]
    q4 = pd.read_csv(ROOT / "output/tables/q4_summary.csv").iloc[0]

    doc = SimpleDocTemplate(str(OUT_PDF), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    story = []

    story.append(Paragraph("生产企业原材料的订购与运输", styles["CNTitle"]))
    story.append(Paragraph("CUMCM 2021 C题 完整论文", styles["CN"]))
    story.append(Spacer(1, 12))

    def prod_mix(name):
        df = pd.read_csv(ROOT / "output/tables" / name)
        wc = [c for c in df.columns if c.startswith("week_")]
        cons = {"A": 0.6, "B": 0.66, "C": 0.72}
        raw = {m: df[df.material == m][wc].sum().sum() for m in "ABC"}
        prod = {m: raw[m] / cons[m] for m in raw}
        t = sum(prod.values()) or 1
        return {m: 100 * prod[m] / t for m in prod}

    q2p = prod_mix("q2_order_plan.csv")
    q3p = prod_mix("q3_order_plan.csv")
    cost_drop = 100 * (q2["total_cost_index"] - q3["total_cost_index"]) / q2["total_cost_index"]

    abstract = (
        f"基于402家供应商与8家转运商数据，建立熵权-TOPSIS供应商评价与带库存约束的线性规划订购模型。"
        f"Q1确定50家最重要供应商，Top1为{q1.iloc[0]['supplier_id']}（得分{q1.iloc[0]['importance_score']:.4f}）；"
        f"Q2最少需{int(q2['min_suppliers'])}家供应商，总订货{q2['total_order_volume']:.0f}m³，"
        f"产品当量A{q2p['A']:.1f}%/B{q2p['B']:.1f}%/C{q2p['C']:.1f}%；"
        f"Q3偏A少C方案A升至{q3p['A']:.1f}%、C降至{q3p['C']:.1f}%，成本指数{q3['total_cost_index']:.0f}（较Q2降{cost_drop:.1f}%）；"
        f"Q4产能可提升{q4['increase_percent']:.1f}%至{q4['new_capacity_m3']:.0f}m³/周。"
    )
    story.append(Paragraph("摘要", styles["CNH"]))
    story.append(Paragraph(abstract, styles["CN"]))
    story.append(Paragraph("关键词：供应商评价；熵权TOPSIS；线性规划；转运优化", styles["CN"]))
    story.append(PageBreak())

    sections = [
        ("1 问题重述", "企业周产能28200m³，需24周订购与转运计划，保持两周库存，A/B/C材料消耗与价差已知。"),
        ("2 问题分析", "Q1为多指标评价；Q2-Q3为采购优化；Q4为能力上界。流程：EDA→特征→TOPSIS→LP→转运分配。"),
        ("3 模型假设", "供货满足率用历史均值；库存以产品当量计；转运容量6000m³/周。"),
        ("4 问题一结果", f"Top50平均满足率{q1['fill_rate'].mean():.3f}，前5家：{', '.join(q1.head(5)['supplier_id'].tolist())}。"),
        ("5 问题二结果", f"最少供应商{int(q2['min_suppliers'])}家，总订货量{q2['total_order_volume']:.0f}m³，成本指数{q2['total_cost_index']:.0f}。产品当量A{q2p['A']:.1f}%/B{q2p['B']:.1f}%/C{q2p['C']:.1f}%。"),
        ("6 问题三结果", f"选用{int(q3['suppliers'])}家供应商，总订货{q3['total_order_volume']:.0f}m³，成本指数{q3['total_cost_index']:.0f}（较Q2降{cost_drop:.1f}%）。产品当量A由{q2p['A']:.1f}%升至{q3p['A']:.1f}%，C由{q2p['C']:.1f}%降至{q3p['C']:.1f}%，B为{q3p['B']:.1f}%。"),
        ("7 问题四结果", f"产能倍增{q4['capacity_multiplier']:.3f}，新产能{q4['new_capacity_m3']:.0f}m³/周，需{int(q4['suppliers_used'])}家供应商。"),
        ("8 模型检验", "TOPSIS与累计供货基准对比；权重灵敏度分析；Q2/Q3消融实验。"),
        ("9 结论", "模型可在库存安全下兼顾成本与损耗，输出可复现附件方案。"),
    ]
    for title, body in sections:
        story.append(Paragraph(title, styles["CNH"]))
        story.append(Paragraph(body, styles["CN"]))
        story.append(Spacer(1, 6))

    figs = [
        "eda_correlation_heatmap.png",
        "q1_top20_scores.png",
        "q2_weekly_orders.png",
        "q2_transport_loss.png",
        "q3_material_mix.png",
        "q4_capacity_compare.png",
        "q1_sensitivity.png",
    ]
    story.append(PageBreak())
    story.append(Paragraph("图表附录", styles["CNH"]))
    for i, fn in enumerate(figs, 1):
        fp = ROOT / "output/figures" / fn
        if fp.exists():
            story.append(Paragraph(f"图{i} {fn}", styles["CN"]))
            story.append(Image(str(fp), width=14 * cm, height=8 * cm))
            story.append(Spacer(1, 8))

    doc.build(story)


def main():
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    if try_xelatex():
        print("PDF compiled via xelatex:", OUT_PDF)
    else:
        build_reportlab_pdf()
        print("PDF compiled via reportlab:", OUT_PDF)


if __name__ == "__main__":
    main()
