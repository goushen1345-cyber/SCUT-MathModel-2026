from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "paper" / "manuscript_v1.md"
FIG = ROOT / "paper" / "figures"
OUT = ROOT / "paper" / "final" / "2024-C-paper.docx"

BLUE = "1F4E78"
LIGHT_BLUE = "D9EAF7"
PALE = "F3F7FA"
GRAY = "5B6573"


TABLES = {
    "T1": [
        ["数据对象", "规模/单位", "用途与说明"],
        ["地块", "54 个；面积/亩", "确定地类、面积和可用季次"],
        ["作物", "41 种", "区分粮食、蔬菜、食用菌及豆类"],
        ["2023 年种植", "87 条", "提供基期种植结构与生产量代理"],
        ["原始参数", "107 条", "含亩产、成本及价格区间"],
        ["有效参数键", "125 个", "按地类—作物—季次展开"],
        ["销售上限", "59 个未知", "基础表保持未知；D0/D05/D10 为条件情形"],
    ],
    "T2": [
        ["符号", "含义"],
        ["i,j,t,s", "地块、作物、年份和季次索引"],
        ["x_{ijts}", "种植面积，连续变量"],
        ["y_{ijts}", "是否启用某项种植安排，0-1变量"],
        ["A_i", "地块面积"],
        ["v,c,p", "亩产、亩成本、正常销售价"],
        ["q,e", "正常价格销售量、超额产量"],
        ["Π(x,ω)", "方案 x 在情形 ω 下的七年累计利润"],
        ["共同约束", "适种性、地块容量、水浇地模式、重茬、三年豆类、最小面积和分散度"],
    ],
    "T3": [
        ["问题", "主要新增因素", "比较方式", "冻结选择"],
        ["Q1", "两种超额销售规则；三种销量代理", "M0 热启动与 M1R3；管理权衡", "S1、S2 各一套 D0 结果表"],
        ["Q2", "销量、亩产、成本、价格波动", "B0/M0/M1 等；500 留出与 36 组敏感性", "M0-R1"],
        ["Q3", "相关、替代、互补关系", "三个关系世界；局部候选与 1500 次评价", "保留 B0"],
    ],
    "T4": [
        ["销售规则", "销量口径", "七年利润/万元", "启用项", "最优性边界", "结果表"],
        ["S1 超额滞销", "D0", "3967.80", "738", "gap 约3.36%—3.66%", "result1_1.xlsx"],
        ["S2 超额半价", "D0", "6168.31", "662", "gap 约0.60%—0.66%", "result1_2.xlsx"],
    ],
    "T5": [
        ["方案", "平均利润/万元", "最差10%/万元", "相对比较", "结论"],
        ["B0", "6695.18", "6539.18", "参考", "后备"],
        ["M0", "6717.33", "6561.90", "较B0平均+22.14万元；500/500为正", "冻结"],
        ["M1", "6720.08", "6564.57", "较M0平均+2.75万元；121/500下降", "未过替换门槛"],
    ],
    "T6": [
        ["项目", "结果", "解释边界"],
        ["R0", "平均约6727.36万元", "仅相关扰动"],
        ["RS", "平均约6727.17万元", "较R0约-2463.845元"],
        ["RSC", "平均约6727.30万元", "较R0约-1290.945元"],
        ["N10", "平均增益0.064%", "低于0.1%替换门槛"],
        ["N30", "排除", "相对B0改动40项，超过30项限制"],
        ["最终B0", "平均6727.28万元；最差10%为6537.59万元", "500底层情形×3世界"],
    ],
    "T7": [
        ["核验对象", "方法", "结果"],
        ["冻结证据", "按 state.json 快照逐文件校验哈希", "Q1/Q2/Q3 均有效"],
        ["农业约束", "独立读取面积表复算", "获批代理口径下0硬约束违规"],
        ["收益", "由面积、亩产、价格、销售量和成本重新记账", "冻结报告误差阈值内"],
        ["Q1/S1 工作簿", "逐格回读", "7页；738个非零面积值一致"],
        ["Q1/S2 工作簿", "逐格回读", "7页；662个非零面积值一致"],
        ["Q2 工作簿", "逐格回读", "7页；666个非零面积值一致"],
        ["样本隔离", "固定种子与一次性留出", "Q2 500次；Q3 1500次评价"],
    ],
    "T8": [
        ["假设或限制", "可能影响", "当前处理", "后续改进"],
        ["无独立销量", "收益和作物结构", "D0/D05/D10 条件分析", "收集订单和实际销量"],
        ["价格采用区间中点", "绝对利润", "保留原区间并明确中点是候选", "使用成交价时间序列"],
        ["概率为设定", "Q2排序", "留出与36组敏感性", "用多年数据估计分布"],
        ["关系系数为合成", "Q3结论", "三个关系世界和强度检验", "估计交叉价格弹性"],
        ["求解存在gap", "最优性", "只称限时可行方案", "增加算力并给出更紧界"],
        ["豆类为累计面积代理", "空间轮作", "报告23个严格诊断违规窗口", "细分固定小区建模"],
        ["N30违反邻域定义", "候选排名", "排除且不在留出后补跑", "需重新预注册后再研究"],
    ],
}


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=70, start=80, bottom=70, end=80) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def keep_row(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def set_run_font(run, east="宋体", latin="Times New Roman", size=10.5, bold=None, color=None) -> None:
    run.font.name = latin
    run._element.rPr.rFonts.set(qn("w:eastAsia"), east)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_begin, instr, fld_end])
    set_run_font(run, size=9, color=GRAY)


def add_table(doc: Document, data: list[list[str]], caption: str) -> None:
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(6)
    cap.paragraph_format.space_after = Pt(4)
    run = cap.add_run(caption)
    set_run_font(run, east="黑体", size=9.5, bold=True, color=BLUE)

    table = doc.add_table(rows=len(data), cols=len(data[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = True
    for r, row_data in enumerate(data):
        row = table.rows[r]
        keep_row(row)
        if r == 0:
            set_repeat_table_header(row)
        for c, text in enumerate(row_data):
            cell = row.cells[c]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            set_cell_shading(cell, BLUE if r == 0 else (PALE if r % 2 == 0 else "FFFFFF"))
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if r == 0 or c < 2 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            run = p.add_run(str(text))
            set_run_font(run, east="黑体" if r == 0 else "宋体", size=8.2, bold=(r == 0), color="FFFFFF" if r == 0 else "1F2937")
    after = doc.add_paragraph()
    after.paragraph_format.space_after = Pt(2)


def add_paragraph_with_bold(doc: Document, text: str, style=None) -> None:
    p = doc.add_paragraph(style=style)
    p.paragraph_format.first_line_indent = Cm(0.74)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.35
    p.paragraph_format.space_after = Pt(4)
    parts = re.split(r"(\*\*.*?\*\*)", text)
    for part in parts:
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**")
        clean = part[2:-2] if bold else part
        run = p.add_run(clean)
        set_run_font(run, east="黑体" if bold else "宋体", size=10.5, bold=bold)


def setup_styles(doc: Document) -> None:
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(10.5)
    for name, size, before, after in (("Title", 22, 0, 12), ("Heading 1", 16, 14, 8), ("Heading 2", 12.5, 10, 5)):
        st = styles[name]
        st.font.name = "Arial"
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor.from_string(BLUE)
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True
    if "Figure Caption" not in styles:
        st = styles.add_style("Figure Caption", WD_STYLE_TYPE.PARAGRAPH)
    else:
        st = styles["Figure Caption"]
    st.font.name = "Times New Roman"
    st._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    st.font.size = Pt(9)
    st.font.color.rgb = RGBColor.from_string(GRAY)


def add_cover(doc: Document) -> None:
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("2024 年全国大学生数学建模竞赛 C 题练习论文")
    set_run_font(r, east="黑体", size=15, bold=True, color=GRAY)
    p.paragraph_format.space_after = Pt(34)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("基于混合整数规划、情景模拟与\n关系敏感性分析的农作物种植策略")
    set_run_font(r, east="黑体", size=24, bold=True, color=BLUE)
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.space_after = Pt(60)
    for label in ("参赛队号：________________", "练习日期：2026 年 9 月"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(label)
        set_run_font(r, east="宋体", size=12, color=GRAY)
        p.paragraph_format.space_after = Pt(14)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(50)
    r = p.add_run("冻结证据版本：G1-v1-base / Q1-D-v2-candidate / Q2-D-v1-candidate / Q3-D-v1-candidate")
    set_run_font(r, east="宋体", size=8.5, color=GRAY)
    doc.add_page_break()


def build() -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Mm(210)
    sec.page_height = Mm(297)
    sec.top_margin = Mm(22)
    sec.bottom_margin = Mm(20)
    sec.left_margin = Mm(23)
    sec.right_margin = Mm(23)
    sec.header_distance = Mm(9)
    sec.footer_distance = Mm(9)
    setup_styles(doc)
    header = sec.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hr = header.add_run("2024 年全国大学生数学建模竞赛 C 题练习论文")
    set_run_font(hr, east="宋体", size=8.5, color=GRAY)
    add_page_number(sec.footer.paragraphs[0])
    add_cover(doc)

    lines = SRC.read_text(encoding="utf-8").splitlines()
    buffer: list[str] = []
    first_h1 = True

    def flush() -> None:
        nonlocal buffer
        text = " ".join(x.strip() for x in buffer).strip()
        if text:
            add_paragraph_with_bold(doc, text)
        buffer = []

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("# "):
            flush()
            title = line[2:].strip()
            if title == "基于混合整数规划、情景模拟与关系敏感性分析的农作物种植策略":
                continue
            if not first_h1:
                doc.add_page_break()
            first_h1 = False
            doc.add_paragraph(title, style="Heading 1")
            continue
        if line.startswith("## "):
            flush()
            doc.add_paragraph(line[3:].strip(), style="Heading 2")
            continue
        m = re.fullmatch(r"\[\[FIG:([^|]+)\|(.+)\]\]", line)
        if m:
            flush()
            path = FIG / m.group(1)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(path), width=Cm(15.2))
            cap = doc.add_paragraph(style="Figure Caption")
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.paragraph_format.space_after = Pt(6)
            cap.paragraph_format.keep_with_next = False
            cr = cap.add_run(m.group(2))
            set_run_font(cr, east="宋体", size=9, color=GRAY)
            continue
        m = re.fullmatch(r"\[\[TABLE:([^|]+)\|(.+)\]\]", line)
        if m:
            flush()
            add_table(doc, TABLES[m.group(1)], m.group(2))
            continue
        m = re.fullmatch(r"\[\[EQ:(.+)\|(.+)\]\]", line)
        if m:
            flush()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(5)
            p.paragraph_format.keep_together = True
            r = p.add_run(f"{m.group(1)}    {m.group(2)}")
            set_run_font(r, east="宋体", latin="Cambria Math", size=10.5)
            continue
        buffer.append(line)
    flush()

    props = doc.core_properties
    props.title = "基于混合整数规划、情景模拟与关系敏感性分析的农作物种植策略"
    props.subject = "2024年全国大学生数学建模竞赛C题练习论文"
    props.author = "参赛队"
    props.keywords = "农作物种植; 混合整数规划; 情景模拟; 高斯copula"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
