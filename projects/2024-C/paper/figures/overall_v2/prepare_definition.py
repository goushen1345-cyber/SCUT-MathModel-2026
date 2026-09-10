"""Build the content-review table from existing research references; no experiments."""
import json
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
spec = json.loads((HERE / 'structure.json').read_text(encoding='utf-8'))
ids = {n['id'] for n in spec['nodes']} | {'G'}
for node in spec['nodes']:
    assert 2 <= len(node['lines']) <= 4
    text = '\n'.join(node['lines'])
    assert not any(t in text.lower() for t in ['agent','skill','reviewer','freeze','state','wait','checkpoint','prompt'])
    assert not any(t in text for t in ['冻结','审批','确认点','内部文件','M0','M1','B0','N10'])
    for source in node['sources']:
        assert (PROJECT / source).is_file(), source
for e in spec['edges']:
    assert set((e['from'] + ',' + e['to']).split(',')) <= ids

parts = ['# 总体建模框架图内容审定与图文接口', '',
         '版本：FIG-OVERALL-02 / v2。此文件与structure.json共同保存节点、连线、来源和正文接口。节点及边先核对，再生成TikZ；AI逻辑核对不等于人工逐项核验。', '',
         '## 内容审定表', '',
         '| 节点ID | 节点名称 | 节点内容 | 上游 | 下游 | 这条关系表示什么 |',
         '|---|---|---|---|---|---|']
for n in spec['nodes']:
    up=[e for e in spec['edges'] if n['id'] in e['to'].split(',')]
    down=[e for e in spec['edges'] if n['id'] in e['from'].split(',')]
    if n['scope']=='shared':
        upstream='D1、D2、D3（经共享分组G）'; downstream='Q1A、Q2A、Q3A（经G）'
        meaning='共同定义变量、可行域及销售收益结构；三个框并列组成G，不互为处理步骤。'
    else:
        upstream='；'.join(e['from'].replace(',','、') for e in up) or '题目/原始附件'
        downstream='；'.join(e['to'].replace(',','、') for e in down) or '全文解释范围'
        meaning='；'.join(e['id']+'：'+e['meaning'] for e in down) or '限定所有结果的解释范围。'
    parts.append('| '+' | '.join([n['id'],n['name'],'<br>'.join(n['lines']),upstream,downstream,meaning])+' |')
parts += ['', 'G是UV、UA、UT三个并列模块的共同外框，不是另一项模型或计算。汇合线表示共享输入/骨架，虚线表示现实因素扩展，单独的“问题二方案”实线表示基准传入。', '',
          '## 总体结构与每条边', '',
          '四层依次是：目标和附件；土地、经济与销量代理参数；统一混合整数规划骨架；三问扩展及结果/边界。共享骨架是UV、UA、UT；Q1A—Q1C、Q2A—Q2C、Q3A—Q3C分别为各问专属。三问平行连接共同骨架，虚线体现因素递进；Q2C到Q3B另传入实际已选方案作基准。Q1的面积决策不锁定Q2。', '',
          '| 边ID | 起点→终点 | 类型 | 含义 |','|---|---|---|---|']
parts += [f"| {e['id']} | {e['from']}→{e['to']} | {e['kind']} | {e['meaning']} |" for e in spec['edges']]
parts += ['', '## 图题与正文接口', '', spec['caption'], '',
          '**建议位置：**替换当前论文第1节的旧图1，放在研究路线说明之后、第2节“数据整理、符号与基本假设”之前。图前、图后两段同步替换，不改变后续章节顺序。', '',
          '**图前引入段：**三问都要安排同一片土地在未来七年的种植，但对市场条件的假设逐步增加。为区分共同的农业约束、各问新增的因素以及方案比较的依据，图1将参数来源、统一模型、三问扩展和结果边界放在同一框架中。图中虚线表示研究因素的递进，不表示问题一的面积安排限制问题二的决策。', '',
          '**图后解释段：**框架的中心是共同的混合整数规划模型：同时决定种植面积、是否启用某项安排和水浇地种植模式，并以土地适配、季次、跨年重茬、豆类累计面积及管理约束限定可行方案。问题一在稳定参数下比较两种超额销售规则，并考察收益与管理复杂度的取舍；问题二引入未来参数变化，通过候选比较、留出评价和敏感性分析选择方案；问题三以问题二方案为基准，在共同情景中加入潜在因子相关和交叉价格需求响应。问题三实际还将成本和蔬菜价格的趋势档位随机化，因此图中的递进不构成纯相关效应的识别。最终结果连同销量代理、合成关系、验证层次及豆类空间覆盖等边界一并解释。依照这一结构，下一节先整理原始数据并说明模型所需参数及基本假设。', '',
          '## 没有放入图的内容与理由', '',
          '- 内部模型编号、工作状态、审批、文件路径：不属于论文研究机制，只保留在来源映射。',
          '- 所有地块/作物名单、完整公式和系数表：会挤占阅读空间，放在参数表与模型章节。图中管理阈值为实际模型设定，完整适用范围见UT边界。',
          '- 绝对利润及大量样本数：精确数值在结果表更清楚，也避免误比Q2与Q3不同随机集的绝对利润。',
          '- 真实需求预测、实证因果网络、动态逐年改种：项目未完成这些研究，不能画成已采用方法。',
          '- “复杂模型必胜”“严格全局最优”“所有位置已完成豆类轮作”：均未获证据支持。风险候选未完成精化及无效局部候选的细节留在Q3正文，图中只保留证据不足边界。',
          '- 历史严格轮作诊断的收益差：属于补强前比较，已按FG-C06在正文标明，不塞进总体图。', '',
          '## 节点来源及限制', '', '| 节点 | 当前材料 | 额外边界 |','|---|---|---|']
parts += ['| '+n['id']+' | '+'<br>'.join(n['sources'])+' | '+n.get('boundary','见对应报告及正文说明。')+' |' for n in spec['nodes']]
parts += ['', '## 生成前自检', '',
          '- 已含面积/启用/模式、正常及超额销售、目标、适配/季次/容量/重茬/豆类代理/管理约束；共同骨架不暗示所有候选目标完全相同。',
          '- 已区分Q1/Q2共同结构与Q2→Q3方案基准，没有锁定Q2面积或逐情景改种。',
          '- 相关/替代/互补均标为合成情景机制，未画为实证因果；Q3额外随机设定和训练潜在层验证边界显式披露。',
          '- 六项批准纠错的口径已用于节点和边；图内无内部流程词、路径或候选版本编号。',
          '- 来源文件存在检查和每框2—4行检查由本脚本执行；内容仍需主执行者逐项核对和成图视觉验收。', '']
(HERE/'content_review.md').write_text('\n'.join(parts),encoding='utf-8')
refs=sorted({p for n in spec['nodes'] for p in n['sources']})
(HERE/'source_manifest.json').write_text(json.dumps({'figure_id':spec['figure_id'],'sources':{p:hashlib.sha256((PROJECT/p).read_bytes()).hexdigest() for p in refs}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'nodes':len(spec['nodes']),'edge_types':len(spec['edges']),'sources':len(refs),'content_review_created':True}))
