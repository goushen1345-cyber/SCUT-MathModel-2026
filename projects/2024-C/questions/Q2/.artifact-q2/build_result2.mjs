import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const repo = "E:/Projects/SCUT-MathModel-2026";
const sourcePath = `${repo}/培训作业/第四次培训作业/附件3/result2.xlsx`;
const solutionPath = `${repo}/projects/2024-C/questions/Q2/deep_runs/M0-DEEP-v1/solution.csv`;
const outputDir = `${repo}/projects/2024-C/questions/Q2/.artifact-q2/generated`;
const outputPath = `${outputDir}/result2_Q2-DRAFT-v1.xlsx`;

function parseCsv(text) {
  const lines = text.replace(/^\uFEFF/, "").trim().split(/\r?\n/);
  const head = lines[0].split(",");
  return lines.slice(1).map(line => {
    const values = line.split(",");
    return Object.fromEntries(head.map((key, i) => [key, values[i] ?? ""]));
  });
}

const rows = parseCsv(await fs.readFile(solutionPath, "utf8"));
const landsText = await fs.readFile(`${repo}/projects/2024-C/data/frozen/G1-v1-base/lands.csv`, "utf8");
const lands = parseCsv(landsText).map(x => x.land_id);
const secondLands = lands.filter(x => /^[DEF]/.test(x));
const firstIndex = new Map(lands.map((x, i) => [x, i]));
const secondIndex = new Map(secondLands.map((x, i) => [x, i]));
const mapping = {
  protocol: "Q2-DEEPEN-v1",
  source: "培训作业/第四次培训作业/附件3/result2.xlsx",
  source_sha256: "6a1ba9fc28d14d0a4a795e5f0b7261fb6e32165517afee62bcd1931aba5bee8a",
  years: [2024, 2025, 2026, 2027, 2028, 2029, 2030],
  crop_columns: "crop_id 1..41 maps to C..AQ",
  first_block: "all 54 lands in B2:B55; 单季 and 第一季",
  second_block: "D1..F4 in B56:B83; 第二季",
};

const input = await FileBlob.load(sourcePath);
const workbook = await SpreadsheetFile.importXlsx(input);
for (const year of mapping.years) {
  const matrix = Array.from({ length: 82 }, () => Array(41).fill(null));
  for (const row of rows.filter(x => Number(x.year) === year)) {
    const column = Number(row.crop_id) - 1;
    const sheetRow = row.season === "第二季" ? 54 + secondIndex.get(row.land_id) : firstIndex.get(row.land_id);
    if (!Number.isInteger(sheetRow) || sheetRow < 0 || column < 0 || column >= 41) throw new Error(`Bad mapping ${JSON.stringify(row)}`);
    matrix[sheetRow][column] = Number(row.area_mu);
  }
  const sheet = workbook.worksheets.getItem(String(year));
  sheet.getRange("C2:AQ83").values = matrix;
}
await workbook.recalculate();
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "Q2 final formula error scan",
});
await fs.mkdir(outputDir, { recursive: true });
const renders = [];
for (const year of mapping.years) {
  const image = await workbook.render({ sheetName: String(year), range: "A1:AQ87", scale: 1 });
  const renderPath = `${outputDir}/render_${year}.png`;
  await fs.writeFile(renderPath, new Uint8Array(await image.arrayBuffer()));
  renders.push(renderPath);
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
await fs.writeFile(`${outputDir}/template_mapping_q2.json`, JSON.stringify(mapping, null, 2), "utf8");
await fs.writeFile(`${outputDir}/artifact_tool_audit.json`, JSON.stringify({
  protocol: "Q2-DEEPEN-v1",
  source: sourcePath,
  solution: solutionPath,
  formula_error_scan: errors.ndjson,
  renders,
  sheets_rendered: renders.length,
}, null, 2), "utf8");
console.log(JSON.stringify({ outputPath, sheets: 7, renders: 7, formulaErrors: errors.ndjson }));
