from pathlib import Path
import urllib.request, concurrent.futures, json
HERE=Path(__file__).resolve().parent
items={
 'friedman_article.html':'https://projecteuclid.org/journals/annals-of-statistics/volume-29/issue-5/Greedy-function-approximation-A-gradient-boosting-machine/10.1214/aos/1013203451.full',
 'energyplan_full.pdf':'https://www.ndrc.gov.cn/xxgk/zcfb/ghwb/202203/P020220322582066837126.pdf',
 'scipy_highs.html':'https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html',
 'forecast_baselines.html':'https://otexts.com/fpp3/simple-methods.html',
 'ridge_docs.html':'https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification',
 'boosting_docs.html':'https://scikit-learn.org/stable/modules/ensemble.html#gradient-tree-boosting',
}
def get(item):
 name,url=item
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as r:
   data=r.read()
  (HERE/name).write_bytes(data)
  return {'file':name,'url':url,'status':'retrieved','bytes':len(data)}
 except Exception as e:return {'file':name,'url':url,'status':'failed','error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:result=list(pool.map(get,items.items()))
(HERE/'details_retrieval.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(result,ensure_ascii=False))
