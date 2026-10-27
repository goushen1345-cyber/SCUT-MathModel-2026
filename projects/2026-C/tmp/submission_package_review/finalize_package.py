from pathlib import Path
import hashlib,json,shutil,zipfile,io,ast
from pypdf import PdfReader
from PIL import Image
P=Path(__file__).resolve().parents[2];D=P/'支撑材料';T=Path(__file__).resolve().parent;C=P/'paper/提交配套'
shutil.copy2(C/'AI工具使用详情.pdf',D/'AI工具使用详情.pdf')
bad=[]
terms=['SCUT','华南理工','Users/Rog','Users\\Rog','wxid_']
for p in D.rglob('*'):
 if not p.is_file():continue
 if p.suffix in ['.py','.tex','.json','.txt','.md','.csv']:
  s=p.read_text('utf-8-sig')
 elif p.suffix=='.xlsx':
  with zipfile.ZipFile(p) as z:s='\n'.join(z.read(n).decode('utf-8',errors='ignore') for n in z.namelist() if n.startswith('docProps/'))
 elif p.suffix=='.png':s=str(Image.open(p).info)
 elif p.suffix=='.pdf':s=str(PdfReader(p).metadata)
 else:continue
 for term in terms:
  if term.lower() in s.lower():bad.append((str(p.relative_to(D)),term))
 if p.suffix=='.py':ast.parse(s,filename=p.name)
assert not bad,bad
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
(D/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(D).as_posix() for p in files)+'\n',encoding='utf-8')
files=sorted(p for p in D.rglob('*') if p.is_file())
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in files:z.write(p,str(Path('支撑材料')/p.relative_to(D)))
size=len(buf.getbuffer());assert size<20_000_000
result=dict(files=len(files),source_files=sum(p.suffix in ['.py','.tex'] for p in (D/'code').iterdir()),estimated_zip_bytes=size,raw_bytes=sum(p.stat().st_size for p in files),identity_check='No configured identity strings found in text and checked image/PDF/workbook metadata.',archive_created=False,reason='User requested the folder first. Official rule specifies WinRAR; only an in-memory ZIP size estimate was made.',AI_report='Updated actual Codex usage through September 13; DeepSeek use details pending team confirmation.',paper_modified=False)
(T/'final_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
line='''\n\n## 2026-09-13：整理比赛支撑材料\n\n用户明确要求阅读第一次通知、论文格式规范及两个范例，先整理支撑材料文件夹并更新AI使用报告。已逐页读取11页通知、2页规范、46页范例论文及范例支撑包结构/AI报告。样例仅用于格式参考，不复制其题目或代码。\n\n交付路径：支撑材料/。导出五个完整result工作簿；Q2、Q3、Q4-2、Q4-3均为334天、48096时段。最终算法按原函数整理为可独立运行模块；在独立输出目录完整复算，所有订单、计划版本和实际轨迹与保存结果逐项一致，最大差0。数据数组逐值复核；工作簿独立回读日期、购电量、2004组充放电、668个端点及紧急电量；复算三类EDA作图统计与Q1三种初始库存检验。作图程序已运行；配套附录含文件清单和完整源程序，另存paper/提交配套/，未替换论文。\n\n整理时发现Q1验证入口误用了3000/9000边界，已更正为原研究1200/10800，重跑核对原费用一致；错误临时检查记录保存在tmp，未用于论文或最终结果。现有原始附件、研究模型及state.json不变，不生成冻结或人工通过状态。\n\nAI使用报告按真实Codex记录更新至9月13日。DeepSeek官网API页查得Flash入口对应V4.1-Flash，但团队实际版本/用途尚未收到确认，不能据此替代本聊天使用来源。异步问题已提出；全队AI披露仍需其补充。已有立体示意图为用户外部提供，制作工具/源工程未留存，图源说明已如实区分。文件夹未上传、未提交；压缩体积内存估算小于20MB，最终WinRAR压缩尚未执行。\n'''
for rel in ['state/decisions.md','state/ai_usage_log.md']:
 p=P/rel
 with p.open('a',encoding='utf-8') as f:f.write(line)
print(json.dumps(result,ensure_ascii=False,indent=2))
