"""Independent OOXML verification for the Q2 result2 project draft."""
from pathlib import Path
import csv
import hashlib
import json
import re
import zipfile
from xml.etree import ElementTree as ET


Q = Path(__file__).resolve().parent
ROOT = Q.parents[1]
REPO = Q.parents[3]
SOURCE = REPO / "培训作业/第四次培训作业/附件3/result2.xlsx"
OUT = Q / "outputs/Q2-DRAFT-v1"
OUTPUT = OUT / "result2_Q2-DRAFT-v1.xlsx"
SOLUTION = Q / "deep_runs/M0-DEEP-v1/solution.csv"
LANDS = ROOT / "data/frozen/G1-v1-base/lands.csv"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def colnum(ref):
    n = 0
    for char in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(char) - 64
    return n


def rownum(ref):
    return int(re.search(r"\d+", ref).group())


def sheets(path):
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {x.attrib["Id"]: x.attrib["Target"].lstrip("/") for x in rels}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in ss.findall("m:si", NS)]
        out = {}
        for sheet in wb.find("m:sheets", NS):
            target = targets[sheet.attrib["{" + NS["r"] + "}id"]]
            target = target if target.startswith("xl/") else "xl/" + target
            out[sheet.attrib["name"]] = ET.fromstring(z.read(target))
        return out, shared


def display(xml, shared, keep):
    out = {}
    for cell in xml.findall(".//m:c", NS):
        ref = cell.attrib["r"]
        if not keep(ref):
            continue
        value = cell.find("m:v", NS)
        inline = cell.find("m:is", NS)
        if cell.attrib.get("t") == "s" and value is not None:
            out[ref] = shared[int(value.text)]
        elif inline is not None:
            out[ref] = "".join(t.text or "" for t in inline.findall(".//m:t", NS))
        elif value is not None:
            out[ref] = value.text
    return out


source_sheets, source_shared = sheets(SOURCE)
output_sheets, output_shared = sheets(OUTPUT)
years = [str(y) for y in range(2024, 2031)]
assert list(source_sheets) == list(output_sheets) == years
land_ids = [x["land_id"] for x in rows(LANDS)]
second_ids = [x for x in land_ids if x[0] in "DEF"]
first = {x: i + 2 for i, x in enumerate(land_ids)}
second = {x: i + 56 for i, x in enumerate(second_ids)}
expected = {year: {} for year in years}
for row in rows(SOLUTION):
    sheet = row["year"]
    column = int(row["crop_id"]) + 2
    letters = ""
    n = column
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    target_row = second[row["land_id"]] if row["season"] == "第二季" else first[row["land_id"]]
    expected[sheet][f"{letters}{target_row}"] = float(row["area_mu"])

checked = 0
for year in years:
    outside = lambda ref: not (3 <= colnum(ref) <= 43 and 2 <= rownum(ref) <= 83)
    assert display(source_sheets[year], source_shared, outside) == display(output_sheets[year], output_shared, outside)
    actual_text = display(output_sheets[year], output_shared, lambda ref: 3 <= colnum(ref) <= 43 and 2 <= rownum(ref) <= 83)
    actual = {key: float(value) for key, value in actual_text.items() if abs(float(value)) > 1e-12}
    assert set(actual) == set(expected[year]), (year, set(actual) ^ set(expected[year]))
    for ref, value in expected[year].items():
        assert abs(actual[ref] - value) <= 1e-7, (year, ref, actual[ref], value)
    checked += len(actual)

audit = json.loads((OUT / "artifact_tool_audit.json").read_text(encoding="utf-8"))
assert "matched 0 entries" in audit["formula_error_scan"]
renders = sorted(OUT.glob("render_*.png"))
assert len(renders) == 7 and all(x.stat().st_size > 0 for x in renders)
assert sha(SOURCE) == "6a1ba9fc28d14d0a4a795e5f0b7261fb6e32165517afee62bcd1931aba5bee8a"
result = {
    "protocol": "Q2-DEEPEN-v1",
    "method": "independent zipfile/XML; imports neither artifact builder nor solver",
    "source_sha256": sha(SOURCE),
    "output_sha256": sha(OUTPUT),
    "sheets": 7,
    "nonzero_cells_checked": checked,
    "labels_and_notes_preserved": True,
    "csv_values_exact": True,
    "formula_error_scan_passed": True,
    "render_files": [x.name for x in renders],
    "passed": True,
    "human_verification": "pending",
}
(OUT / "workbook_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
