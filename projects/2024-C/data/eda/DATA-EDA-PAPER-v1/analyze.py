"""Descriptive EDA using frozen, source-backed fields only. No models or forecasts."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,hashlib,platform,re,argparse
import numpy as np

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]
BASE=PROJECT/'data/frozen/G1-v1-base'
TYPES=['平旱地','梯田','山坡地','水浇地','普通大棚','智慧大棚']
CATS=['粮食（豆类）','粮食','蔬菜（豆类）','蔬菜','食用菌']
def read(n):
    with (BASE/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=HERE/'results');args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    lands=read('lands.csv');crops=read('crops.csv');hist=read('planting_2023.csv');pars=read('parameters_original.csv')
    cdict={int(x['crop_id']):x for x in crops};ldict={x['land_id']:x for x in lands}
    land=[{k:x[k] for k in ['land_id','land_type','source_file','source_sheet','source_row']}|{'area':float(x['area_mu'])} for x in lands]
    h=[{'land':x['land_id'],'crop':int(x['crop_id']),'category':cdict[int(x['crop_id'])]['crop_type'],'land_type':ldict[x['land_id']]['land_type'],'season':x['season'],'area':float(x['area_mu']),'source_row':x['source_row']} for x in hist]
    p=[]
    for x in pars:
        lo,hi=map(float,re.split(r'\s*-\s*',x['price_interval_raw']))
        p.append({'crop':int(x['crop_id']),'name':x['crop_name'],'category':cdict[int(x['crop_id'])]['crop_type'],'land_type':x['land_type'],'season':x['season'],'yield':float(x['yield_jin_per_mu']),'cost':float(x['cost_yuan_per_mu']),'price_low':lo,'price_high':hi,'source_row':x['source_row']})
    mapping=json.loads((BASE/'template_mapping.json').read_text(encoding='utf-8-sig'))
    legal={(x['crop_id'],x['land_type'],x['season']) for x in mapping['allowed_parameter_keys']}
    observed={(x['crop'],x['land_type'],x['season']) for x in h}
    cols=[('平旱地','单季'),('梯田','单季'),('山坡地','单季'),('水浇地','单季'),('水浇地','第一季'),('水浇地','第二季'),('普通大棚','第一季'),('普通大棚','第二季'),('智慧大棚','第一季'),('智慧大棚','第二季')]
    matrix=[[2 if (c,*t) in observed else 1 if (c,*t) in legal else 0 for t in cols] for c in range(1,42)]
    assert observed<=legal and len(p)==107 and len(h)==87
    groups=defaultdict(list)
    for x in h:groups[(x['land'],x['season'])].append(x)
    land_stats=[]
    total=sum(x['area'] for x in land)
    for t in TYPES:
        xs=[x['area'] for x in land if x['land_type']==t]
        land_stats.append({'type':t,'count':len(xs),'area':sum(xs),'share_percent':sum(xs)/total*100,'min':min(xs),'median':float(np.median(xs)),'max':max(xs)})
    history_by_type=[{'type':t,'areas':{c:sum(x['area'] for x in h if x['land_type']==t and x['category']==c) for c in CATS}} for t in TYPES]
    crop_history=[]
    for c in range(1,42):
        xs=[x for x in h if x['crop']==c]
        crop_history.append({'crop':c,'name':cdict[c]['crop_name'],'category':cdict[c]['crop_type'],'area':sum(x['area'] for x in xs),'plots':len({x['land'] for x in xs}),'records':len(xs)})
    param_stats=[]
    for cat in CATS:
        xs=[x for x in p if x['category']==cat]
        param_stats.append({'category':cat,'records':len(xs),'yield_min':min(x['yield'] for x in xs),'yield_max':max(x['yield'] for x in xs),'cost_min':min(x['cost'] for x in xs),'cost_max':max(x['cost'] for x in xs),'price_min':min(x['price_low'] for x in xs),'price_max':max(x['price_high'] for x in xs)})
    price_intervals=[]
    for c in range(1,42):
        grouped=defaultdict(list)
        for x in p:
            if x['crop']==c:grouped[(x['price_low'],x['price_high'])].append({'land_type':x['land_type'],'season':x['season'],'source_row':x['source_row']})
        price_intervals.append({'crop':c,'name':cdict[c]['crop_name'],'category':cdict[c]['crop_type'],'intervals':[{'low':k[0],'high':k[1],'sources':v} for k,v in sorted(grouped.items())]})
    bean_land=defaultdict(float)
    for x in h:
        if '豆类' in x['category']:bean_land[x['land']]+=x['area']
    paired=[]
    for c in range(1,16):
        xs={x['land_type']:x for x in p if x['crop']==c}
        paired.append({'crop':c,'name':cdict[c]['crop_name'],'yield_dry':xs['平旱地']['yield'],'yield_terrace':xs['梯田']['yield'],'yield_slope':xs['山坡地']['yield'],'cost_equal':len({x['cost'] for x in xs.values()})==1,'price_equal':len({(x['price_low'],x['price_high']) for x in xs.values()})==1})
    result={'data_version':'G1-v1-base','land_types':TYPES,'categories':CATS,'lands':land,'land_stats':land_stats,'history':h,'history_by_type':history_by_type,'crop_history':crop_history,'parameters':p,'parameter_stats':param_stats,'price_intervals':price_intervals,'paired_grain':paired,'coverage_columns':cols,'coverage_matrix':matrix,'crop_names':[cdict[c]['crop_name'] for c in range(1,42)],'summary':{'land_total':total,'history_area_mu_times':sum(x['area'] for x in h),'land_season_groups':len(groups),'mixed_groups':sum(len(v)>1 for v in groups.values()),'max_crops_per_land_season':max(map(len,groups.values())),'bean_plots':len(bean_land),'bean_area_mu_times':sum(bean_land.values()),'legal_parameter_combinations':len(legal),'observed_parameter_combinations':len(observed),'unobserved_legal_combinations':len(legal-observed),'distinct_price_intervals':sum(len(x['intervals']) for x in price_intervals)},'definitions':{'coverage':'0=ineligible by source rules;1=eligible but no2023 record;2=eligible and observed. Not a demand matrix.','price':'Each line is an original interval; identical intervals within crop grouped for display, all source rows retained. No midpoint.','history_area':'Sum of historical planted area over crop/season records, mu-times across seasons; unique plots count physical IDs.','parameters':'107 source statistical rows, not independent empirical samples; no18 referenced duplicates in distribution.','preprocessing':'Reuse confirmed normalization, merged-anchor provenance and explicit rule references. No numerical edits.'},'input_sha256':{n:sha(BASE/n) for n in ['lands.csv','crops.csv','planting_2023.csv','parameters_original.csv','template_mapping.json']},'code_sha256':sha(Path(__file__)),'environment':{'python':platform.python_version(),'numpy':np.__version__}}
    (out/'eda.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,rows in [('land_summary',land_stats),('crop_history',crop_history),('parameter_ranges',param_stats),('paired_grain',paired)]:
        with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({'summary':result['summary'],'lands':land_stats,'parameter_ranges':param_stats,'history_by_type':history_by_type,'top_area':sorted(crop_history,key=lambda x:-x['area'])[:5]},ensure_ascii=False))
if __name__=='__main__':main()
