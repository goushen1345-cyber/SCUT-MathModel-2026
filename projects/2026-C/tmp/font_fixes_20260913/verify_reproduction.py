from pathlib import Path
import json,hashlib,pypdf

R=Path(__file__).resolve().parent
P=R.parents[1]
PACK=R/'reproduction_package'
PAPER=P/'shumo_1/shumo_backup_20260913_003434/图像压缩版/fig'
GENERATED=PACK/'reproduced/plots/fig'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=json.loads((PACK/'input_manifest.json').read_text(encoding='utf-8'))
assert all(sha(Path(r['source']))==sha(Path(r['copy']))==r['sha256'] for r in sources)
pairs=[('03_Q1_daily_dispatch','q1_daily_dispatch'),('q3_final_days','q3_final_days'),('q3_final_quantile','q3_final_quantile')]
records=[]
for gen,name in pairs:
    record={'figure':name,'outputs':[]}
    for ext in ('pdf','png'):
        a,b=GENERATED/f'{gen}.{ext}',PAPER/f'{name}.{ext}'
        row={'extension':ext,'generated':str(a),'paper':str(b),'generated_sha256':sha(a),'paper_sha256':sha(b)}
        row['byte_identical']=row['generated_sha256']==row['paper_sha256']
        if ext=='pdf':
            pa,pb=pypdf.PdfReader(a).pages[0],pypdf.PdfReader(b).pages[0]
            row['mediabox_generated']=[float(v) for v in pa.mediabox]
            row['mediabox_paper']=[float(v) for v in pb.mediabox]
            row['same_mediabox']=row['mediabox_generated']==row['mediabox_paper']
            row['same_page_content']=pa.get_contents().get_data()==pb.get_contents().get_data()
            assert row['same_mediabox'] and row['same_page_content']
        assert row['byte_identical']
        record['outputs'].append(row)
    records.append(record)
result={'status':'passed','copied_files':len(sources),'input_and_code_hashes_unchanged':True,
        'all_six_outputs_byte_identical':True,'pdf_page_content_and_dimensions_identical':True,
        'scope':'Three drawing scripts executed in an independent minimal package. No fitting, optimization, or formal file changes.',
        'figures':records}
(R/'independent_reproduction_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
