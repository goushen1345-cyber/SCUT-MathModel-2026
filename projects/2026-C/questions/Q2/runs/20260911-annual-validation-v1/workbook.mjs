import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const R=path.dirname(fileURLToPath(import.meta.url)),P=path.resolve(R,'../../../..');
const mode=process.argv[2]??'inspect';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(P,'data/raw/C题/附件/附件5/result2.xlsx')));
await fs.mkdir(path.join(R,'previews'),{recursive:true});
const render=async(sheet,range,name)=>{const b=await wb.render({sheetName:sheet,range,scale:1.5,format:'png'});await fs.writeFile(path.join(R,'previews',name+'.png'),new Uint8Array(await b.arrayBuffer()));};
if(mode==='inspect'){
 console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:1200})).ndjson);
 await render('计划购电量','A1:F5','source_purchase');await render('计划购电量','EK1:EQ4','source_midnight');await render('充放电量','A1:F8','source_storage');await render('紧急购电量','A1:C8','source_emergency');
}else if(mode==='export'){
 const p=JSON.parse(await fs.readFile(path.join(R,'delivery_data/workbook_payload.json'),'utf8'));
 const q=wb.worksheets.getItem('计划购电量'),s=wb.worksheets.getItem('充放电量'),e=wb.worksheets.getItem('紧急购电量');
 q.getRange('A2:EQ335').values=p.purchase;q.getRange('EO1').values=[['0:00-0:10']];
 q.getRange('A2:A335').setNumberFormat('yyyy-mm-dd');q.getRange('B2:EQ335').setNumberFormat('0.00');
 q.getRange('A1:EQ335').format.font={name:'SimSun',size:11,color:'#000000'};q.getRange('A1:A335').format.columnWidth=14;q.getRange('B1:EO335').format.columnWidth=17;q.getRange('EP1:EQ335').format.columnWidth=20;q.getRange('A1:EQ1').format.rowHeight=30;q.getRange('A1:EQ1').format.wrapText=true;
 s.getUsedRange().unmerge();s.getUsedRange().clear({applyTo:'contents'});s.getRange('A1:F1').values=[['日期','时间段','充电量','放电量','时刻','储电量']];s.getRange(`A2:F${p.storage.length+1}`).values=p.storage;
 s.getRange(`A2:A${p.storage.length+1}`).setNumberFormat('yyyy-mm-dd');s.getRange(`C2:D${p.storage.length+1}`).setNumberFormat('0.00');s.getRange(`F2:F${p.storage.length+1}`).setNumberFormat('0.00');s.getRange(`A1:F${p.storage.length+1}`).format.font={name:'SimSun',size:11,color:'#000000'};s.getRange(`A1:A${p.storage.length+1}`).format.columnWidth=14;s.getRange(`B1:B${p.storage.length+1}`).format.columnWidth=19;s.getRange(`C1:F${p.storage.length+1}`).format.columnWidth=16;s.getRange(`A1:F${p.storage.length+1}`).format.rowHeight=24;
 e.getUsedRange().unmerge();e.getUsedRange().clear({applyTo:'contents'});e.getRange('A1:C1').values=[['日期','购电时间段','购电量']];e.getRange(`A2:C${p.emergency.length+1}`).values=p.emergency;e.getRange(`A2:A${p.emergency.length+1}`).setNumberFormat('yyyy-mm-dd');e.getRange(`C2:C${p.emergency.length+1}`).setNumberFormat('0.00');e.getRange(`A1:C${p.emergency.length+1}`).format.font={name:'SimSun',size:11,color:'#000000'};e.getRange(`A1:A${p.emergency.length+1}`).format.columnWidth=15;e.getRange(`B1:B${p.emergency.length+1}`).format.columnWidth=24;e.getRange(`C1:C${p.emergency.length+1}`).format.columnWidth=18;e.getRange(`A1:C${p.emergency.length+1}`).format.rowHeight=24;
 e.getUsedRange().format.horizontalAlignment='center';
 s.getRange(`A2:B${p.storage.length+1}`).format.horizontalAlignment='center';s.getRange(`E2:E${p.storage.length+1}`).format.horizontalAlignment='center';
 for(const sh of[q,s,e]){sh.freezePanes.freezeRows(1);sh.getUsedRange().format.verticalAlignment='center';}
 wb.recalculate();const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},maxChars:1000});
 await fs.writeFile(path.join(R,'delivery_data/workbook_inspection.json'),JSON.stringify({errors:errors.ndjson,payloadSource:p.source_selected_npz_sha256},null,2));
 await render('计划购电量','A1:F6','result_purchase');await render('计划购电量','EK1:EQ6','result_midnight');await render('计划购电量','EK331:EQ335','result_last_dates');await render('充放电量','A1:F13','result_storage');await render('紧急购电量','A1:C14','result_emergency');
 await fs.mkdir(path.join(R,'deliverables'),{recursive:true});const out=await SpreadsheetFile.exportXlsx(wb);await out.save(path.join(R,'deliverables/result2.xlsx'));console.log('result2.xlsx exported');console.log(errors.ndjson);
}else throw Error('Unsupported mode');
