"""Read-only research checks and deterministic figure reproduction checks.

Writes only this figure's validation/source manifest. Never runs a research module.
"""
from pathlib import Path
import hashlib
import json
import platform
import re
from PIL import Image, ImageChops
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    state=json.loads((PROJECT/'state/state.json').read_text(encoding='utf-8'))
    snapshots={}
    for snap in state['data_snapshots'].values():snapshots.update(snap)
    for q in state['questions'].values():
        assert q['status']=='FROZEN' and q['validity']=='VALID'
        snapshots.update(q['snapshots'][q['frozen_version']])
    errors=[p for p,h in snapshots.items() if sha(PROJECT/p)!=h]
    assert not errors,errors
    original_paper={
        'paper/final_v2/2024-C-paper-v2.pdf':'ab5a28110cd85c3d0f866847c02f9b0bfcdd4724636b92a76e64fe758f2620c7',
        'paper/final_v2/2024-C-paper-v2.docx':'d8b00f3cb717781016bd050e1977a6da31d2e7f1e8771d26888e9e8a0e6ecb1f'}
    for p,h in original_paper.items():assert sha(PROJECT/p)==h,p
    final=HERE/'final_v2';other=HERE/'reproduction_v2'
    equality={ext:sha(final/f'model_framework.{ext}')==sha(other/f'model_framework.{ext}') for ext in ['tex','svg','png']}
    assert all(equality.values()),equality
    a=Image.open(final/'model_framework.png').convert('RGB')
    b=Image.open(other/'model_framework.png').convert('RGB')
    pixels_equal=a.size==b.size and ImageChops.difference(a,b).getbbox() is None
    assert pixels_equal
    meta=json.loads((final/'manifest.json').read_text(encoding='utf-8'))
    assert sha(HERE/'content_review.md')==meta['approval_structure_sha256']
    assert sha(HERE/'build_figure.py')==meta['builder_sha256']
    for name,h in meta['artifacts'].items():assert sha(final/name)==h
    reader=PdfReader(final/'model_framework.pdf');assert len(reader.pages)==1
    page=reader.pages[0];public=page.extract_text()
    banned=['Agent','Skill','Reviewer','Freeze','state','WAIT','Checkpoint','Workflow','run id',
            '热启动','留出','挑战者','替换门槛','审批','候选编号','用户确认','M0','M1','B0','N10']
    hits=[s for s in banned if s.lower() in public.lower()]
    assert not hits,hits
    tex=(final/'model_framework.tex').read_text(encoding='utf-8')
    assert not [c for c in tex if ord(c)<32 and c not in '\n\r\t']
    shortstacks=[line for line in tex.splitlines() if '\\shortstack[c]' in line]
    row_counts=[line.split('\\shortstack[c]',1)[1].count('\\\\')+1 for line in shortstacks]
    assert max(row_counts)<=3
    assert not list(page.images)
    for p in [final/'model_framework.log',HERE/'placement_check.log']:
        log=p.read_text(encoding='utf-8',errors='replace')
        assert not re.search(r'Overfull|Missing character|Undefined control sequence',log),str(p)
    proof=PdfReader(HERE/'placement_check.pdf');assert len(proof.pages)==1
    old=json.loads((HERE.parent/'overall_v2/source_manifest.json').read_text(encoding='utf-8'))['sources']
    paths=set(old)
    paths.update(original_paper)
    paths.update(['state/state.json','state/decisions.md','paper_evidence/Q1.md','paper_evidence/Q2.md','paper_evidence/Q3.md',
                  'paper/corrections_v2.json','questions/Q1/run_deepen.py','questions/Q1/run_s1_boost.py',
                  'questions/Q2/runs/comparison.csv','questions/Q3/runs/comparison.csv',
                  'paper/figures/model_structure_v3/content_review.md'])
    for p in (PROJECT.parent.parent/'培训作业/第四次培训作业').rglob('*'):
        if p.is_file():paths.add('../../'+p.relative_to(PROJECT.parent.parent).as_posix())
    sources={p:sha(PROJECT/p) for p in sorted(paths)}
    source_manifest={'figure_id':'FIG-MODEL-03','structure_version':'FIG-MODEL-03-STRUCTURE-v1',
                     'context_revision':state['revision'],'paper_version':state['paper_protocol']['final_version'],
                     'source_role_mapping':'content_review.md / 来源映射与读取范围','sources':sources}
    (HERE/'source_manifest.json').write_text(json.dumps(source_manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    width_cm=float(page.mediabox.width)*2.54/72
    result={
        'status':'PASSED','kind':'figure_rendering_and_read_only_integrity_checks_not_new_research',
        'python':platform.python_version(),'state_revision':state['revision'],'source_files':len(sources),
        'frozen_files_checked':len(snapshots),'frozen_hash_mismatches':errors,'existing_paper_unchanged':True,
        'approved_structure_unchanged':True,'new_research_experiments':0,'frozen_conclusions_modified':False,
        'reproduction_byte_equality':equality,'png_pixels_equal':pixels_equal,'png_size':a.size,
        'pdf_pages':len(reader.pages),'pdf_raster_images':0,'pdf_width_cm':width_cm,
        'placement_width_cm':17,'normal_text_pt_at_placement':9.3*17/width_cm,
        'placement_proof_pages':len(proof.pages),'full_paper_replaced_or_reexported':False,
        'short_box_count':len(row_counts),'max_box_lines':max(row_counts),'public_workflow_terms_found':hits,
        'visual_check':{'method':'AI visual inspection of final PNG and actual A4 placement proof',
                        'inspected':['model center','parameter directions','optimization versus fixed-plan evaluation',
                                     'model deltas','Chinese and equations','line crossing','cropping','local boundaries'],
                        'human_timed_reading_test':False,'human_final_approval_claimed':False},
        'limitations':['PDF byte identity not required because metadata can differ',
                       'The full paper embedding/pagination is not changed or revalidated',
                       'No scientific model claim is newly validated by this figure check'],
        'final_artifacts':meta['artifacts']}
    (HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','frozen_files_checked','source_files','reproduction_byte_equality','short_box_count','normal_text_pt_at_placement']},ensure_ascii=False))

if __name__=='__main__':main()
