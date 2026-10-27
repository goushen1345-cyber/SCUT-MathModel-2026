"""Independent final controls and saved XLSX XML validation; no authoring or solves."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from decimal import Decimal
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent
# Reuse only independent verifier definitions and immutable-source reconstruction.
# This stops before the original bulk checks; no research core is imported.
helper=(R/'verify_all.py').read_text(encoding='utf-8').split('\nbank=np.load(')[0]
exec(compile(helper,str(R/'verify_all.py'),'exec'),globals())
for rel,h in read(R/'supplement/output_hashes.json').items():assert sha(R/'supplement'/rel)==h,rel
feb=read(OLD/'outputs/initialization.json')['feb1_initial'];daily=pd.read_csv(R/'supplement/daily_metrics.csv',float_precision='round_trip');checks=[]
for cfg in read(R/'supplement/protocol.json')['configurations']:
 z=np.load(R/'supplement/schedules'/f'{cfg["name"]}.npz');days=z['days'];assert np.array_equal(days,np.arange(31,365));a=z['actual'];df=pd.DataFrame(a.reshape(-1,a.shape[-1]),columns=z['actual_columns']);df['day']=np.repeat(days,144)
 cost=check_actual(df,feb);close('fees',cost,daily[daily.variant==cfg['name']].total_cost.sum(),1e-5)
 for i,d in enumerate(days):
  pl=z['plan'][i];n=len(pl);lf=np.r_[mean('load',d,0,'week',4),mean('load',d,1,'week',4)];vf=np.r_[mean('pv',d,0,'recent',7),mean('pv',d,1,'recent',7)];m=margin(d,cfg['q'],28,4,cfg['decay'])
  close('forecast',pl[:,0],lf[:n],1e-7);close('forecast',pl[:,1],vf[:n],1e-7);close('margin',pl[:,2],m[:n],1e-7);ad=df[df.day==d];check_plan(pl,ad.storage_start_kwh.iloc[0],ad.order_kwh.to_numpy());counts['forecast_values']+=2*n
 checks.append({'variant':cfg['name'],'cost':cost})
logs=[json.loads(x) for x in (R/'supplement/solver_checks.jsonl').read_text().splitlines()];assert len(logs)==1670
assert all(x['status']==0 and x['simultaneous_slots']==0 and x['primal_dual_gap']<1e-4 for x in logs)

# Read the actual saved workbook, never the authoring payload, through OOXML.
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
file=R/'deliverables/result2.xlsx'
with zipfile.ZipFile(file) as archive:
 shared=[]
 if 'xl/sharedStrings.xml' in archive.namelist():
  shared=[''.join(x.itertext()) for x in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
 w=ET.fromstring(archive.read('xl/workbook.xml'));names=[s.attrib['name'] for s in w.find('m:sheets',NS)];assert names==['计划购电量','充放电量','紧急购电量']
 rels=ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'));targets={x.attrib['Id']:x.attrib['Target'] for x in rels}
 sheets=[]
 for s in w.find('m:sheets',NS):
  target=targets[s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
  root=ET.fromstring(archive.read(target));cells={}
  for c in root.findall('.//m:sheetData/m:row/m:c',NS):
   assert c.attrib.get('t')!='e';v=c.find('m:v',NS);t=c.attrib.get('t')
   if t=='s':value=shared[int(v.text)]
   elif t=='inlineStr':value=''.join(c.find('m:is',NS).itertext())
   elif v is None:value=None
   elif t=='str':value=v.text
   else:value=Decimal(v.text)
   cells[c.attrib['r']]=value
  sheets.append(cells)
q,s,e=sheets
def val(sheet,key):
 v=sheet.get(key);assert isinstance(v,Decimal),(key,v);return v
def near(a,b):assert abs(float(a)-float(b))<1e-6,(a,b)
def col(i):
 out=''
 while i:i,r=divmod(i-1,26);out=chr(65+r)+out
 return out
def clock(k):return '24:00' if k==144 else f'{k//6:02d}:{10*(k%6):02d}'
z=np.load(R/'refinement/schedules/sensitivity-error-decay70.npz');a=z['actual'];cols=list(z['actual_columns']);idx={x:i for i,x in enumerate(cols)}
events=[];totq=Decimal(0);totc=Decimal(0);totem=Decimal(0);seen=0
assert q['EO1']=='0:00-0:10';assert q['B1']=='0:10-0:20'
for i,d in enumerate(z['days']):
 serial=Decimal((base+timedelta(days=int(d))-datetime(1899,12,30)).days);row=i+2;near(val(q,f'A{row}'),serial);aa=a[i];order=aa[:,idx['order_kwh']];em=aa[:,idx['emergency_kwh']];vorder=[]
 for j,k in enumerate(list(range(1,144))+[0],start=2):
  v=val(q,f'{col(j)}{row}');near(v,order[k]);vorder.append((k,v));seen+=1
 qday=sum((v for k,v in vorder),Decimal(0));cday=sum((v*Decimal(str(price[k])) for k,v in vorder),Decimal(0));near(val(q,f'EP{row}'),qday);near(val(q,f'EQ{row}'),cday);totq+=qday;totc+=cday
 for j in range(6):
  r=2+6*i+j;part=aa[j*24:(j+1)*24];assert s[f'B{r}']==f'{clock(j*24)}-{clock((j+1)*24)}';near(val(s,f'C{r}'),np.sum(part[:,idx['grid_charge_kwh']]+part[:,idx['pv_charge_kwh']]));near(val(s,f'D{r}'),part[:,idx['discharge_kwh']].sum())
  if j==0:near(val(s,f'A{r}'),serial);near(val(s,f'F{r}'),aa[0,idx['storage_start_kwh']]);assert s[f'E{r}']=='0:00'
  elif j==1:near(val(s,f'F{r}'),aa[-1,idx['storage_end_kwh']]);assert s[f'E{r}']=='24:00'
  else:assert s.get(f'F{r}') is None
 start=0;found=False
 while start<144:
  if em[start]<=1e-6:start+=1;continue
  end=start+1
  while end<144 and em[end]>1e-6:end+=1
  events.append((serial,f'{clock(start)}-{clock(end)}',em[start:end].sum()));found=True;start=end
 if not found:events.append((serial,'无紧急购电',0.))
 totem+=sum((Decimal(5)*Decimal(str(price[k]))*Decimal(str(em[k])) for k in range(144)),Decimal(0))
for i,(serial,interval,amount) in enumerate(events,2):near(val(e,f'A{i}'),serial);assert e[f'B{i}']==interval;near(val(e,f'C{i}'),amount)
assert seen==48096 and len(events)==439
summary=read(R/'delivery_data/summary.json');near(totc,summary['ordinary_cost']);near(totem,summary['emergency_cost']);near(totc+totem,summary['total_official_cost'])
for rel,h in read(R/'delivery_data/source_hashes.json').items():assert sha(R/rel)==h
res={'status':'passed','supplement':{'lp_calls':1670,'actual_intervals':counts['actual'],'planned_intervals':counts['planned'],'forecast_values':counts['forecast_values'],'maximum_absolute_errors':maximum,'costs':checks},'saved_xlsx':{'sha256':sha(file),'plan_values':seen,'dates':334,'four_hour_charge_discharge_groups':2004,'endpoint_states':668,'emergency_rows':len(events),'positive_emergency_events':sum(x[2]>0 for x in events),'ordinary_fee_decimal':str(totc),'emergency_fee_decimal':str(totem),'total_fee_decimal':str(totc+totem),'midnight_same_civil_date':True,'source_previous_outputs_unchanged':True},'new_solves':0,'new_fits':0,'human_review':False}
(R/'delivery_verification.json').write_text(json.dumps(res,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding='utf-8');print(json.dumps(res,ensure_ascii=False,default=lambda x:x.item()),flush=True)
