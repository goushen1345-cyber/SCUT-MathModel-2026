import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const run=path.dirname(fileURLToPath(import.meta.url));
const project=path.resolve(run,'../../../..');
const template=path.join(project,'data/raw/C题/附件/附件5/result1.xlsx');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(template));
const mode=process.argv[2]??'inspect';
await fs.mkdir(path.join(run,'previews'),{recursive:true});
const render=async(sheet,range,name)=>{
  const blob=await wb.render({sheetName:sheet,range,scale:1.5,format:'png'});
  await fs.writeFile(path.join(run,'previews',name+'.png'),new Uint8Array(await blob.arrayBuffer()));
};
if(mode==='inspect'){
  console.log((await wb.inspect({kind:'workbook,sheet,table',maxChars:3500,tableMaxRows:3,tableMaxCols:5})).ndjson);
  await render('计划购电量','A1:B8','source_purchase');
  await render('充放电量','A1:E7','source_storage');
}else if(mode==='export'){
  const payload=JSON.parse(await fs.readFile(path.join(run,'outputs/export_payload.json'),'utf8'));
  const purchase=wb.worksheets.getItem('计划购电量'), storage=wb.worksheets.getItem('充放电量');
  purchase.getRange('B2:B145').values=payload.purchase;
  storage.getRange('B2:C7').values=payload.charge_discharge;
  storage.getRange('E2:E3').values=payload.states;
  // Template structure and all labels remain intact. Display only, retain numeric precision.
  purchase.getRange('B2:B145').setNumberFormat('0.00');
  storage.getRange('B2:C7').setNumberFormat('0.00');
  storage.getRange('E2:E3').setNumberFormat('0.00');
  wb.recalculate();
  const inspect=await wb.inspect({kind:'table',range:'充放电量!A1:E7',include:'values,formulas',tableMaxRows:7,tableMaxCols:5,maxChars:4000});
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30}});
  await fs.writeFile(path.join(run,'outputs/workbook_inspection.json'),JSON.stringify({inspection:inspect.ndjson,errors:errors.ndjson},null,2));
  await render('计划购电量','A1:B8','result_purchase');
  await render('计划购电量','A139:B145','result_midnight');
  await render('充放电量','A1:E7','result_storage');
  await fs.mkdir(path.join(run,'deliverables'),{recursive:true});
  const output=await SpreadsheetFile.exportXlsx(wb);
  await output.save(path.join(run,'deliverables/result1.xlsx'));
  console.log(inspect.ndjson);console.log(errors.ndjson);console.log('Exported result1.xlsx');
}else throw new Error('Unknown mode');
