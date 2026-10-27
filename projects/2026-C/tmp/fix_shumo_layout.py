from pathlib import Path
base=Path('E:/Projects/SCUT-MathModel-2026/projects/2026-C/shumo_1/shumo/sections')
for name in ['sec_5_q1.tex','sec_6_q2.tex','sec_7_q3.tex','sec_8_q4.tex']:
    p=base/name
    raw=p.read_bytes(); t=raw.decode('utf-8').replace('\r\n','\n')
    t=t.replace(r'\mathrm{元/kWh}',r'\text{元}/\mathrm{kWh}').replace(r'\mathrm{元}',r'\text{元}')
    if name=='sec_5_q1.tex':
        t=t.replace(r'下限，而线性规划仍保留',r'下限。此时，线性规划仍保留')
    if name=='sec_6_q2.tex':
        a=t.index('由此形成\n'); b=t.index('的连续调度过程。',a)+len('的连续调度过程。')
        t=t[:a]+'由此形成从零点制定计划、日内储能吸收偏差、必要时紧急补购，到日末库存传递至下一天的连续调度过程。'+t[b:]
    for label in [r'\label{tab:q2_emergency_purchase}',r'\label{tab:q3_emergency}',r'\label{tab:q3_candidate}']:
        if label in t:
            t=t.replace(label,label+'\n\\small\n\\setlength{\\tabcolsep}{4pt}',1)
    if name=='sec_8_q4.tex':
        cap=r'\caption{波动电价下不同价格预测模型的比较}'
        t=t.replace(cap,cap+'\n    \\small',1)
    p.write_bytes(t.replace('\n','\r\n' if b'\r\n' in raw else '\n').encode('utf-8'))
print('Fixed currency font and local table/line widths in four question files.')
