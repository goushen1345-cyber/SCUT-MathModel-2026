from pathlib import Path
from copy import copy,deepcopy
from datetime import datetime
import ast,shutil,json,hashlib
import openpyxl

P=Path(__file__).resolve().parents[2];D=P/'支撑材料'
T=Path(__file__).parent/'template_format_restore';T.mkdir(exist_ok=True)
B=T/'before';B.mkdir(exist_ok=True)
source=(D/'code/export_results.py').read_text('utf-8')
tree=ast.parse(source)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='format_workbook')
exec(compile(ast.Module(body=[fn],type_ignores=[]),'format_workbook','exec'))
def values(w):
 return [(s.title,s.max_row,s.max_column,str(s.merged_cells),tuple(tuple((c.value,c.data_type) for c in row) for row in s)) for s in w]

results=[]
for src in sorted(D.glob('result*.xlsx')):
 if not (B/src.name).exists():shutil.copy2(src,B/src.name)
 w=openpyxl.load_workbook(src);t=openpyxl.load_workbook(D/'templates'/src.name)
 before=values(w)
 format_workbook(w,t)
 out=T/src.name;w.save(out)
 check=openpyxl.load_workbook(out)
 assert values(check)==before,src.name
 for s in check:
  template=t[s.title]
  assert s.sheet_format==template.sheet_format
  assert list(s.column_dimensions)==list(template.column_dimensions)
  for key,dim in s.column_dimensions.items():
   ref=template.column_dimensions[key]
   assert (dim.width,dim.min,dim.max)==(ref.width,ref.min,ref.max)
  for c in s[1]:
   ref=template.cell(1,c.column)
   for attr in ['font','fill','alignment','border','number_format']:
    assert copy(getattr(c,attr))==copy(getattr(ref,attr)),(src.name,s.title,c.coordinate,attr)
  assert s.auto_filter==template.auto_filter
  assert s.freeze_panes==template.freeze_panes
 check.close();w.close();t.close()
 try:
  shutil.copy2(out,src)
  assert src.read_bytes()==out.read_bytes()
  status='updated'
 except PermissionError:status='locked; restored copy available in tmp/submission_package_review/template_format_restore'
 results.append(dict(file=src.name,status=status,cell_values_unchanged=True,template_dimensions_and_headers_verified=True))

manifest=D/'SHA256SUMS.txt'
paths=[l.split('  ',1)[1] for l in manifest.read_text('utf-8').splitlines() if '  ' in l]
manifest.write_text('\n'.join(hashlib.sha256((D/n).read_bytes()).hexdigest()+'  '+n for n in paths)+'\n',encoding='utf-8')
(T/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
entry='\n\n### 2026-09-13：result恢复官方模板格式\n\n用户要求支撑材料result格式与templates一致。本次恢复五份工作簿的模板字体、字号、边框、对齐、行高、列宽、数字显示与视图，撤回统一宋体11号及灰底方案。扩展数据按原模板每日分组样式延续：储能六行一组，紧急购电按实际记录数分组；保留所有原数据、日期和时段，不复制模板示例或省略号。逐单元格值与类型一致，标题样式及列尺寸核查通过。导出程序同步修改，SHA256清单已更新，原排版版本备份于tmp/submission_package_review/template_format_restore/before。不修改AI报告、模板原件、研究数据或研究状态。\n'+json.dumps(results,ensure_ascii=False)+'\n'
for name in ['decisions.md','ai_usage_log.md']:
 with (P/'state'/name).open('a',encoding='utf-8') as f:f.write(entry)
print(json.dumps(results,ensure_ascii=False,indent=2))
