from pathlib import Path
import json

project=Path(__file__).resolve().parents[2]
state=json.loads((project/'state/state.json').read_text(encoding='utf-8'))
assert state['revision']==23 and state['stage']=='TRIAL' and state['active_question']=='Q2'
assert any(a['id']=='U013' for a in state['authorizations'])
state['revision']=24;state['stage']='WAIT_B';state['execution_status']='WAITING'
state['pending_gate']={
  'id':'B','plan_version':'Q2-B-v1','scope':'Q2',
  'summary':'选择Q2初始主模型。AI推荐M0确定性中间路径，B0后备，M1作为深化对照；M2/M3本轮未显示相对M1的增益。',
  'allowed_actions':'只读查看、解释和审查Q2-B-v1；等待用户明确选择主模型。不得深化、生成result2.xlsx、冻结Q2或进入Q3。',
  'budget':'Q2-TRIAL-v1已在55分钟内完成；下一阶段预算需在C点方案中另行提出。',
  'stop_condition':'收到用户对Q2-B-v1的明确模型选择后，才进入深化方案设计并停C。'
}
state['q2_protocol'].update({'status':'WAITING_FOR_B_SELECTION','trial_result':'Q2-B-v1','experiments_run':9,'recommended_initial_model':'M0','fallback_model':'B0','deepen_comparator':'M1','future_holdout_opened':False})
state['history'].append({
 'date':'2026-09-07','from_stage':'TRIAL','to_stage':'WAIT_B','authorization_id':'U013',
 'reason':'完成Q2-TRIAL-v1：R0识别1%容差无法区分并保留失败证据，R1在原范围内以0.1%公平复跑；5份方案独立核验0违规，端到端51.15分钟未超55分钟。推荐M0主模型、B0后备、M1深化对照，停B。',
 'artifacts':['questions/Q2/generate_scenarios.py','questions/Q2/run_trials.py','questions/Q2/refine_trials_gap.py','questions/Q2/verify_trials.py','questions/Q2/runs/validation.json','questions/Q2/runs/primary_summary.csv','questions/Q2/runs/pairwise_comparison.csv','questions/Q2/runs/comparison.csv','questions/Q2/runs/completion.json','questions/Q2/runs/manifest.json','questions/Q2/report.md','questions/Q2/experiments.md','paper_evidence/Q2.md','state/decisions.md','state/ai_usage_log.md']
})
(project/'state/proposed.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
