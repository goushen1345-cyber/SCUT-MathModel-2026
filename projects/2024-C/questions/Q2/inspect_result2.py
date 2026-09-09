from pathlib import Path
import json
import re
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
path = ROOT / "培训作业/第四次培训作业/附件3/result2.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
with zipfile.ZipFile(path) as z:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    targets = {x.attrib["Id"]: x.attrib["Target"].lstrip("/") for x in rels}
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
        shared = ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in ss.findall("m:si", NS)]
    result = {}
    for sheet in wb.find("m:sheets", NS):
        target = targets[sheet.attrib["{" + NS["r"] + "}id"]]
        target = target if target.startswith("xl/") else "xl/" + target
        xml = ET.fromstring(z.read(target))
        cells = []
        for cell in xml.findall(".//m:c", NS):
            ref = cell.attrib["r"]
            value = cell.find("m:v", NS)
            inline = cell.find("m:is", NS)
            if cell.attrib.get("t") == "s" and value is not None:
                display = shared[int(value.text)]
            elif inline is not None:
                display = "".join(t.text or "" for t in inline.findall(".//m:t", NS))
            else:
                display = value.text if value is not None else ""
            if display:
                cells.append([ref, display])
        result[sheet.attrib["name"]] = cells
print(json.dumps(result, ensure_ascii=False, indent=2))
