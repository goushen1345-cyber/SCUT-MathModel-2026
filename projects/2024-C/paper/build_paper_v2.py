"""Rebuild the approved six corrections and replace two figures; research files are read-only."""
import importlib.util
import json
import re
from pathlib import Path
from copy import deepcopy

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.part import Part
from docx.opc.packuri import PackURI
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Pt

PAPER=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('paper_v1_builder',PAPER/'build_paper.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
changes=json.loads((PAPER/'corrections_v2.json').read_text(encoding='utf-8'))
base.SRC=PAPER/'manuscript_v2.md'
base.OUT=PAPER/'final_v2'/'2024-C-paper-v2.docx'
base.BLUE=base.GRAY='000000'
original_font=base.set_run_font
def black_font(run,*args,**kwargs):
    kwargs['color']='000000';return original_font(run,*args,**kwargs)
base.set_run_font=black_font
original_shading=base.set_cell_shading
base.set_cell_shading=lambda cell,fill: original_shading(cell,'FFFFFF')
base.TABLES['T6']=changes['table6']['rows']
base.TABLES['T3'][0][-1]='采用方案'
base.TABLES['T3'][2][1]='随机销量、亩产与菌价；成本和菜价固定主趋势'
base.TABLES['T3'][3][1]='相关与交叉价格响应；部分趋势档位另行随机化'
base.TABLES['T8'] += [
 ['实际设定与原方案概括有差异','不能识别纯相关收益','披露Q3额外随机化及Q2共享粮食增长','需要单独授权后才可按原设定重算'],
 ['相关验证仅为训练潜在层','不能证明最终参数相关目标','限定Pearson/Spearman证据对象','有数据与授权后检查最终参数层']]

def mr(text):
    r=OxmlElement('m:r');pr=OxmlElement('w:rPr');fonts=OxmlElement('w:rFonts');fonts.set(qn('w:ascii'),'Cambria Math');fonts.set(qn('w:hAnsi'),'Cambria Math');pr.append(fonts)
    color=OxmlElement('w:color');color.set(qn('w:val'),'000000');pr.append(color);r.append(pr)
    t=OxmlElement('m:t');t.text=text;r.append(t);return r
def group(tag,items):
    x=OxmlElement('m:'+tag)
    for item in items:x.append(mr(item) if isinstance(item,str) else item)
    return x
def sub(text,index):return group('sSub',[group('e',[text]),group('sub',[index])])
def ss(text,index,power):return group('sSubSup',[group('e',[text]),group('sub',[index]),group('sup',[power])])
def superscript(items,power):return group('sSup',[group('e',items),group('sup',[power])])
def fraction(top,bottom):return group('f',[group('num',[top]),group('den',[bottom])])
def summation(index,items,upper=None):
    x=OxmlElement('m:nary');pr=OxmlElement('m:naryPr')
    ch=OxmlElement('m:chr');ch.set(qn('m:val'),'∑');pr.append(ch)
    loc=OxmlElement('m:limLoc');loc.set(qn('m:val'),'subSup');pr.append(loc)
    if upper is None:
        h=OxmlElement('m:supHide');h.set(qn('m:val'),'1');pr.append(h)
    x.append(pr);x.append(group('sub',[index]));x.append(group('sup',[] if upper is None else [upper]));x.append(group('e',items));return x
def root(text):
    x=OxmlElement('m:rad');pr=OxmlElement('m:radPr');hide=OxmlElement('m:degHide');hide.set(qn('m:val'),'1');pr.append(hide);x.append(pr);x.append(group('deg',[]));x.append(group('e',[text]));return x

def add_actual_math(doc):
    x=lambda:sub('x','ijts');y=lambda:sub('y','ijts');a=lambda:sub('A','i')
    v=lambda:sub('v','ijts');q=lambda:sub('q','jts');e=lambda:sub('e','jts');Q=lambda:sub('Q','jts');L=lambda:sub('L','jts')
    formulas={
      '(1)':[summation('j',[x()]),'≤',a(),', ∀i,t,s.'],
      '(2)':['α',a(),y(),'≤',x(),'≤',a(),sub('a','ijs'),y(),'.'],
      '(3)':[sub('y','ij,k'),'+',sub('y','ij,k+1'),'≤1.'],
      '(4)':[summation('t∈W',[summation('s',[summation('j∈Jʙ',[x()])])]),'≥',a(),'.'],
      '(5)':[summation('i',[y()]),'≤7.'],
      '(6)':[group('eqArr',[group('e',[Q(),'=',summation('i',[v(),x()])]),group('e',[q(),'=min(',Q(),',',L(),')']),group('e',[e(),'=',Q(),'−',q()])])],
      '(7)':['max Π=',summation('j,t,s',[sub('p','jts'),'(',q(),'+β',e(),')']),'−',summation('i,j,t,s',[sub('c','ijts'),x()]),'.'],
      '(8)':['μ̂(x)=',fraction('1','N'),summation('ω=1',['Π(x,ω)'],'N'),'.'],
      '(9a)':[ss('Z','j','D'),'=',root('0.5'),sub('M','g(j)'),'+',root('0.5'),ss('ε','j','D')],
      '(9b)':[ss('Z','j','P'),'=0.495',sub('M','g(j)'),'+0.4F+',root('1−0.495²−0.4²'),ss('ε','j','P')],
      '(9c)':[ss('Z','j','Y'),'=',root('0.3'),sub('W','g(j)'),'+',root('0.7'),ss('ε','j','Y')]}
    for p in doc.paragraphs:
        label=next((k for k in formulas if p.text.rstrip().endswith(k)),None)
        if not label:continue
        for child in list(p._p):
            if child.tag!=qn('w:pPr'):p._p.remove(child)
        math=group('oMath',formulas[label]);p._p.append(math)
        run=p.add_run('    '+label);black_font(run,latin='Cambria Math',size=10.5)

def inline_math(doc):
    paragraphs=list(doc.paragraphs)
    seen=set()
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if id(cell._tc) not in seen:paragraphs.extend(cell.paragraphs);seen.add(id(cell._tc))
    pattern=re.compile(r'\(1\+r_t\)\^\(t−2023\)|([A-Za-zε])(?:\^([A-Za-z]))?_(?:\{([^}]+)\}|([A-Za-z0-9]+))')
    for paragraph in paragraphs:
        for run in list(paragraph.runs):
            matches=list(pattern.finditer(run.text))
            if not matches:continue
            parts=[];cursor=0
            def plain(text):
                if not text:return
                node=OxmlElement('w:r')
                if run._r.rPr is not None:node.append(deepcopy(run._r.rPr))
                t=OxmlElement('w:t');t.set(qn('xml:space'),'preserve');t.text=text;node.append(t);parts.append(node)
            for match in matches:
                plain(run.text[cursor:match.start()])
                if match.group(0).startswith('(1+'):
                    expr=superscript(['(1+',sub('r','t'),')'],'t−2023')
                elif match.group(2):expr=ss(match.group(1),match.group(3) or match.group(4),match.group(2))
                else:expr=sub(match.group(1),match.group(3) or match.group(4))
                parts.append(group('oMath',[expr]));cursor=match.end()
            plain(run.text[cursor:])
            for part in parts:run._r.addprevious(part)
            run._r.getparent().remove(run._r)

def pagination(doc):
    for p in doc.paragraphs:
        if p.text.startswith('框架的中心是共同的混合整数规划模型'):
            p.paragraph_format.keep_together=True
        if p.text.startswith(('2 数据整理','4 问题一')):
            prev=p._p.getprevious()
            if prev is not None and prev.tag==qn('w:p'):
                for br in list(prev.iter(qn('w:br'))):
                    if br.get(qn('w:type'))=='page':br.getparent().remove(br)
    for table in doc.tables:
        prev=table._tbl.getprevious()
        if prev is not None and prev.tag==qn('w:p'):
            from docx.text.paragraph import Paragraph
            Paragraph(prev,doc._body).paragraph_format.keep_with_next=True
        for row in table.rows[:-1]:
            for cell in row.cells:
                for p in cell.paragraphs:p.paragraph_format.keep_with_next=True

def svg_alternative(doc,index,path):
    shape=doc.inline_shapes[index]
    part=Part(PackURI('/word/media/figure_vector_'+str(index)+'.svg'),'image/svg+xml',path.read_bytes(),doc.part.package)
    rid=doc.part.relate_to(part,RT.IMAGE)
    blip=shape._inline.graphic.graphicData.pic.blipFill.blip
    extlst=OxmlElement('a:extLst');ext=OxmlElement('a:ext');ext.set('uri','{96DAC541-7B7A-43D3-8B79-37D633B846F1}')
    from lxml import etree
    svg=etree.Element('{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip',nsmap={'asvg':'http://schemas.microsoft.com/office/drawing/2016/SVG/main'})
    svg.set(qn('r:embed'),rid);ext.append(svg);extlst.append(ext);blip.append(extlst)
    shape._inline.docPr.set('descr','代码生成矢量图，附PNG兼容预览')

def main():
    base.build()
    doc=Document(base.OUT)
    add_actual_math(doc)
    inline_math(doc)
    pagination(doc)
    svg_alternative(doc,0,PAPER/'figures/overall_v2/render/overall_framework.svg')
    svg_alternative(doc,7,PAPER/'figures/overall_v2/render/q3_relationship.svg')
    # Black text and white table backgrounds throughout this revised copy.
    for table in doc.tables:
        pr=table._tbl.tblPr
        border=pr.find(qn('w:tblBorders'))
        if border is None:border=OxmlElement('w:tblBorders');pr.append(border)
        for side in ['top','left','bottom','right','insideH','insideV']:
            b=OxmlElement('w:'+side);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'000000');border.append(b)
    doc.core_properties.comments='六项证据修订与两张代码图更新；原研究结果未改；待最终人工确认。'
    doc.save(base.OUT)
    print(json.dumps({'output':str(base.OUT),'figures':len(doc.inline_shapes),'tables':len(doc.tables),'new_math_objects':len(doc._element.xpath('//m:oMath'))}))

if __name__=='__main__':main()
