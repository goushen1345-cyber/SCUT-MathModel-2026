import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(".");
const q = path.join(root, "projects/2024-C/questions/Q1");
const sourcePath = path.join(root, "培训作业/第四次培训作业/附件3/result1_1.xlsx");
const solutionPath = path.join(q, "boost_runs/BOOST-D0-S1/solution.csv");
const outputDir = path.join(q, "outputs/Q1-DRAFT-v2");
const outputPath = path.join(outputDir, "result1_1_Q1-DRAFT-v2.xlsx");
const previewDir = path.join(q, "tmp/workbook_previews_v2");
const mapping = JSON.parse(await fs.readFile(path.join(root, "projects/2024-C/data/frozen/G1-v1-base/template_mapping.json"), "utf8"));
await fs.mkdir(outputDir, {recursive: true});
await fs.mkdir(previewDir, {recursive: true});

function parseCsv(text) {
  const lines = text.replace(/^\uFEFF/, "").trim().split(/\r?\n/);
  const head = lines[0].split(",");
  return lines.slice(1).map(line => Object.fromEntries(head.map((h, i) => [h, line.split(",")[i]])));
}

const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));
const audit = [];
audit.push({phase: "source_sheets", ndjson: (await wb.inspect({kind: "sheet", include: "id,name", maxChars: 3000})).ndjson});
for (const year of mapping.years) {
  const blob = await wb.render({sheetName: String(year), range: "A1:AQ83", scale: 0.6, format: "png"});
  await fs.writeFile(path.join(previewDir, `result1_1.xlsx-${year}-before.png`), new Uint8Array(await blob.arrayBuffer()));
}
const rows = parseCsv(await fs.readFile(solutionPath, "utf8"));
for (const year of mapping.years) {
  const matrix = Array.from({length: 82}, () => Array(41).fill(null));
  const map = mapping.templates["result1_1.xlsx"][String(year)];
  for (const row of rows.filter(r => Number(r.year) === year)) {
    const season = mapping.source_season_to_template_season[row.season];
    const excelRow = map.land_rows_by_template_season[season][row.land_id];
    const colLetters = map.crop_columns[row.crop_id];
    const col = Object.values(map.crop_columns).indexOf(colLetters);
    matrix[excelRow - 2][col] = Number(row.area_mu);
  }
  const sheet = wb.worksheets.getItem(String(year));
  sheet.getRange("C2:AQ83").values = matrix;
  sheet.getRange("C2:AQ83").format.numberFormat = "0.000";
}
const out = await SpreadsheetFile.exportXlsx(wb);
await out.save(outputPath);
const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
for (const year of mapping.years) {
  const check = await saved.inspect({kind: "table", range: `${year}!A1:AQ83`, include: "values,formulas", tableMaxRows: 83, tableMaxCols: 41, maxChars: 12000});
  audit.push({phase: "saved_table", year, ndjson: check.ndjson});
  const blob = await saved.render({sheetName: String(year), range: "A1:AQ83", scale: 0.8, format: "png"});
  await fs.writeFile(path.join(previewDir, `result1_1_Q1-DRAFT-v2.xlsx-${year}-after.png`), new Uint8Array(await blob.arrayBuffer()));
}
const errors = await saved.inspect({kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: {useRegex: true, maxResults: 300}, summary: "final formula error scan", maxChars: 6000});
audit.push({phase: "formula_error_scan", ndjson: errors.ndjson});
await fs.writeFile(path.join(outputDir, "artifact_tool_audit.json"), JSON.stringify(audit, null, 2), "utf8");
console.log(JSON.stringify({output: outputPath, renders: 14, audit_records: audit.length}));
