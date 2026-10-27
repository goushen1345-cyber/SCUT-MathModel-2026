from core import *
if __name__=='__main__':
    b=Budget();s=np.load(O/'sources.npz');f=np.load(O/'forecasts.npz')
    old=np.load(O/'margins.npz')['values'].copy()
    values,pairs,meta=build_margins(s['actual'],f['fused'],f['L'],s['release'],b)
    np.savez_compressed(O/'margins.npz',values=values,pairs=pairs,sample_meta=meta)
    finite=np.isfinite(values)&np.isfinite(old);delta=abs(values[finite]-old[finite])
    dump(O/'numeric-correction-v1/impact.json',dict(changed_entries=int((delta>1e-9).sum()),max_margin_change=float(delta.max()),
         new_tree_fits=0,new_lp_calls=0,method='exact decimal rational weight crossing',original='margins.npz preserved in numeric-correction-v1'))
    b.save();event('quantile_corrected',changed=int((delta>1e-9).sum()),max_delta=float(delta.max()))
