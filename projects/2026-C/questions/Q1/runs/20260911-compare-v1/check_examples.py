"""Three small analytic checks of the implemented LP; not new model candidates."""
from pathlib import Path
import json
from compare import solve_lp, schedule, metrics

root=Path(__file__).resolve().parent
cfg=json.loads((root/'protocol.json').read_text(encoding='utf-8')); cfg['dt_hours']=1.
examples=[('single_slot_no_free_initial',[1.],[100.],100.),
          ('equal_prices_no_profitable_cycle',[1.,1.],[0.,100.],100.),
          ('two_price_cycle_with_81_percent',[1.,2.],[0.,100.],100/.81)]
answers=[]
for name,prices,loads,expected in examples:
    inputs=[dict(price=p,load_kw=l,pv_kw=0.) for p,l in zip(prices,loads)]
    actions,cert=solve_lp(inputs,cfg); result=metrics(schedule(inputs,cfg,actions))
    # The small examples use one-hour intervals, unlike the 10-minute main experiment.
    result['max_charge_kw']=max((a['grid_charge']+a['pv_charge'])/cfg['dt_hours'] for a in actions)
    result['max_discharge_kw']=max(a['discharge']/cfg['dt_hours'] for a in actions)
    passed=abs(result['cost_yuan']-expected)<1e-5 and abs(result['end_kwh']-6000)<1e-5
    answers.append(dict(name=name,expected_cost=expected,actual=result,passed=passed))
    assert passed,name
(root/'outputs/analytic_checks.json').write_text(json.dumps(answers,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(answers,ensure_ascii=False,indent=2))
