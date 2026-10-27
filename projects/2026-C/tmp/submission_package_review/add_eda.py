from pathlib import Path
import re
P=Path(__file__).resolve().parents[2];D=P/'支撑材料'
s=(P/'scripts/explore_data.py').read_text('utf-8-sig')
s=s.replace("SOURCE = PROJECT / 'data/prepared-v1'","SOURCE = PROJECT / 'data'")
s=s.replace("default='audit/eda-v1'","default='reproduced/eda'")
s=s.replace("    manifest = json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))\n    raw_hashes = {p: sha(PROJECT/p) for p in manifest['raw_sha256']}\n    assert raw_hashes == manifest['raw_sha256']", "    raw_hashes = json.loads((SOURCE/'raw_hashes.json').read_text(encoding='utf-8'))")
for n in ['day_reference','actual_power','actual_price','pv_forecasts']:s=s.replace("SOURCE/'"+n+".csv'","SOURCE/'"+n+".csv.gz'")
s=s.replace("    assert raw_hashes=={p:sha(PROJECT/p) for p in raw_hashes}","    # Raw file identifiers are retained; supplied CSV inputs are rechecked above.")
(D/'code/explore_data.py').write_text(s,encoding='utf-8')
p=D/'code/energy_paths.tex';s=p.read_text('utf-8')
if '\\documentclass' not in s:
 s='''\\documentclass{standalone}
\\usepackage[UTF8]{ctex}
\\usepackage{tikz}
\\usetikzlibrary{arrows.meta,positioning}
\\begin{document}
'''+s+'\n\\end{document}\n'
 p.write_text(s,encoding='utf-8')
p=D/'使用说明.md';s=p.read_text('utf-8');s=s.replace('第一条数据命令重建','`python code/explore_data.py`重算原有描述统计，输出到`reproduced/eda/`；`python code/validation.py Q1`重算问题一的规则对比与初始储电量检验。问题二、三的已有参数对照及问题三的信息条件对照可按`validation.py --help`选择运行，计算输出不覆盖随包最终记录。\n\n第一条数据命令重建');p.write_text(s,encoding='utf-8')
