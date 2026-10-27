"""Two authorized sensitivity solves; baseline is read, never solved again."""
from pathlib import Path
import csv, importlib.util, json, sys, platform

RUN=Path(__file__).resolve().parent
BASE=RUN.parent/'20260911-compare-v1'
spec=importlib.util.spec_from_file_location('q1baseline',BASE/'compare.py')
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)

def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    for r in rows:
        for k,v in list(r.items()):
            try: r[k]=float(v)
            except ValueError: pass
    return rows

def main():
    cfg=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    plan=json.loads((RUN/'protocol.json').read_text(encoding='utf-8'))
    manifest=json.loads((BASE/'delivery_manifest.json').read_text(encoding='utf-8'))
    # Input hashes are independently checked by the original loader.
    inputs=base.load_input()
    out=RUN/'outputs'; out.mkdir(exist_ok=False); (out/'schedules').mkdir()
    base.write_csv(out/'input_mapping.csv',inputs)
    baseline=read(BASE/'outputs/schedules/C04.csv')
    all_rows={6000:baseline}; records=[]
    for initial in plan['new_initial_kwh']:
        scenario=dict(cfg,initial_kwh=initial,terminal_kwh=initial)
        actions,cert=base.solve_lp(inputs,scenario)
        rows=base.schedule(inputs,scenario,actions)
        base.write_csv(out/'schedules'/f'initial_{initial}.csv',rows)
        base.dump(out/f'certificate_{initial}.json',cert)
        all_rows[initial]=rows
    reference=base.metrics(baseline)
    for initial,rows in sorted(all_rows.items()):
        m=base.metrics(rows)
        records.append(dict(initial_kwh=initial,**m,
            cost_difference_yuan=m['cost_yuan']-reference['cost_yuan'],
            cost_difference_pct=100*(m['cost_yuan']/reference['cost_yuan']-1),
            state_at_20h_kwh=rows[120]['state_start'],
            purchase_at_price_peak_kwh=rows[124]['purchase_kwh'],
            changed_purchase_slots=sum(abs(r['purchase_kwh']-b['purchase_kwh'])>1e-5 for r,b in zip(rows,baseline)),
            purchase_l1_difference_kwh=sum(abs(r['purchase_kwh']-b['purchase_kwh']) for r,b in zip(rows,baseline))))
    base.write_csv(out/'sensitivity.csv',records)
    tables1=[]
    for hour in [10,12,14,16,18,20]:
        r=baseline[hour*6]
        tables1.append(dict(start=f'{hour:02d}:00',end=f'{hour:02d}:10',purchase_kwh=r['purchase_kwh']))
    blocks=[]
    for i in range(6):
        rs=baseline[24*i:24*(i+1)]
        blocks.append(dict(start=f'{4*i:02d}:00',end=f'{4*(i+1):02d}:00',
            charge_kwh=sum(r['charge_kwh'] for r in rs),discharge_kwh=sum(r['discharge'] for r in rs),
            purchase_kwh=sum(r['purchase_kwh'] for r in rs),cost_yuan=sum(r['cost_yuan'] for r in rs),
            pv_charge_kwh=sum(r['pv_charge'] for r in rs),grid_charge_kwh=sum(r['grid_charge'] for r in rs),
            state_start=rs[0]['state_start'],state_end=rs[-1]['state_end']))
    base.write_csv(out/'table1_selected_purchase.csv',tables1)
    base.write_csv(out/'table2_four_hour.csv',blocks)
    ordered=sorted(baseline,key=lambda r:int(r['template_result1_row']))
    payload=dict(purchase=[[r['purchase_kwh']] for r in ordered],
        charge_discharge=[[r['charge_kwh'],r['discharge_kwh']] for r in blocks],states=[[6000],[6000]],
        source_rows=[int(r['template_result1_row']) for r in ordered],
        table1=tables1,table2=blocks,totals=reference)
    base.dump(out/'export_payload.json',payload)
    base.dump(out/'summary.json',dict(plan=plan['version'],new_lp_solves=2,baseline_reused=True,
        sensitivity=records,table1=tables1,table2=blocks,main_totals=reference,
        environment=dict(python=sys.version,platform=platform.platform(),numpy=base.np.__version__,scipy=base.scipy.__version__),
        source_hashes={str(p.relative_to(base.PROJECT)):base.sha(p) for p in [BASE/'compare.py',BASE/'protocol.json',BASE/'outputs/schedules/C04.csv',BASE/'outputs/verification.json',RUN/'protocol.json',Path(__file__)]}))
    print(json.dumps(dict(sensitivity=records,table1=tables1,table2=blocks),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
