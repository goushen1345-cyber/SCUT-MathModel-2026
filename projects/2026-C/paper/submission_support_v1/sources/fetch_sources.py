"""Read public bibliographic records and official rules; no user data uploaded."""
from pathlib import Path
import urllib.request, json, concurrent.futures, datetime
HERE=Path(__file__).resolve().parent
urls={
 'dantzig':'https://api.crossref.org/works/10.1515/9781400884179',
 'hoerl':'https://api.crossref.org/works/10.1080/00401706.1970.10488634',
 'friedman':'https://api.crossref.org/works/10.1214/aos/1013203451',
 'huangfu':'https://api.crossref.org/works/10.1007/s12532-017-0130-5',
 'virtanen':'https://api.crossref.org/works/10.1038/s41592-019-0686-2',
 'hyndman':'https://otexts.com/fpp3/',
 'pedregosa':'https://jmlr.org/papers/v12/pedregosa11a.html',
 'carbonplan':'https://www.gov.cn/zhengce/content/2021-10/26/content_5644984.htm',
 'energyplan':'https://www.ndrc.gov.cn/xxgk/zcfb/ghwb/202203/t20220322_1320016.html',
 'official_ai':'https://www.mcm.edu.cn/html_cn/node/fef94648f2836ab6cc81586f4c38512b.html',
 'official_rules':'https://www.mcm.edu.cn/html_cn/node/9d8e511fe7a1447b35f53a82c908e2e0.html',
 'official_format':'https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html',
}
def get(item):
    name,url=item
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (bibliographic verification)'})
        with urllib.request.urlopen(request,timeout=30) as response:
            data=response.read(); final=response.url
        path=HERE/(name+('.json' if 'api.crossref' in url else '.html'))
        path.write_bytes(data)
        row={'id':name,'url':url,'final_url':final,'status':'retrieved','file':path.name,'bytes':len(data)}
        if 'api.crossref' in url:
            m=json.loads(data)['message']
            row['metadata']={k:m.get(k) for k in ['title','author','publisher','container-title','published','published-print','volume','issue','page','DOI','ISBN']}
    except Exception as error:
        row={'id':name,'url':url,'status':'failed','error':str(error)}
    print(json.dumps(row,ensure_ascii=False),flush=True)
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    results=list(pool.map(get,urls.items()))
(HERE/'retrieval.json').write_text(json.dumps({'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'items':results},ensure_ascii=False,indent=2),'utf-8')
