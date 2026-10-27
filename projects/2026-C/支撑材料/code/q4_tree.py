from pathlib import Path
import os,json,time,hashlib,csv,itertools
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import joblib
R=Path(__file__).resolve().parents[1]
P=R
O=R/'reproduced'
DATE=pd.Timestamp('2025-01-01')
N=365*144
N_DAYS=365
SLOTS=144
CAP=5000/6
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def daystr(d):return str((DATE+pd.Timedelta(days=int(d))).date())
class Budget:
 def __init__(self):self.calls=0;self.lp_calls=0;self.price_fits=0
 def check(self):pass
 def save(self):pass
class Logs:
 def event(self,*a,**kw):pass
budget=Budget();logs=Logs()
import q4
class ForecastEngine:
    """Rolling P3 direct-price or P2 residual-price model."""

    def __init__(self, name, features, model_kind, window=56, alpha=10.0,
                 feature_mode="full", max_leaf_nodes=15):
        self.name = name
        self.f = features
        self.model_kind = model_kind
        self.window = int(window)
        self.alpha = float(alpha)
        self.feature_mode = feature_mode
        self.max_leaf_nodes = int(max_leaf_nodes)
        self.cache = {}
        self.model_dir = O / "price_models" / name
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.index = {name: i for i, name in enumerate(self.f.FEATURE_NAMES)}
        if model_kind == "p3":
            if feature_mode == "full":
                self.feature_names = list(self.f.FEATURE_NAMES)
            elif feature_mode == "no_net":
                self.feature_names = [x for x in self.f.FEATURE_NAMES if x != "predicted_net_load_1000kw"]
            elif feature_mode == "history_only":
                self.feature_names = list(self.f.FEATURE_NAMES[:4])
            else:
                raise ValueError(feature_mode)
        else:
            self.feature_names = [
                "matching_weekday_level", "recent_minus_matching", "lag7_minus_matching",
                "attachment1_minus_matching", "predicted_net_load_1000kw",
                "current_day_level", "current_level_decay6h", "last_residual_decay1h",
                "lead_hours", "season_sin", "season_cos",
                *[f"weekday_{i}" for i in range(7)], "release_fraction",
            ]
            if feature_mode == "residual_no_net":
                self.feature_names.remove("predicted_net_load_1000kw")

    def transform(self, full):
        if self.model_kind == "p3":
            return full[:, [self.index[x] for x in self.feature_names]], full[:, self.index["matching_weekday_median4"]]
        match = full[:, self.index["matching_weekday_median4"]]
        cols = {
            "matching_weekday_level": match,
            "recent_minus_matching": full[:, self.index["recent7_median"]] - match,
            "lag7_minus_matching": full[:, self.index["lag7_price"]] - match,
            "attachment1_minus_matching": full[:, self.index["attachment1_base"]] - match,
        }
        for name in (
            "predicted_net_load_1000kw", "current_day_level", "current_level_decay6h",
            "last_residual_decay1h", "lead_hours", "season_sin", "season_cos",
            *[f"weekday_{i}" for i in range(7)], "release_fraction",
        ):
            cols[name] = full[:, self.index[name]]
        return np.column_stack([cols[x] for x in self.feature_names]), match

    def training(self, cutoff):
        xs, ys = [], []
        for origin in range(max(1, cutoff - self.window), cutoff):
            for release in self.f.releases:
                targets, net = self.f.supply_forecast(origin, release)
                valid = (targets < cutoff * q4.SLOTS) & (targets < q4.N_DAYS * q4.SLOTS)
                if not valid.any():
                    continue
                full = self.f.matrix(origin, release, targets[valid], net[valid])
                x, match = self.transform(full)
                y = self.f.prices.reshape(-1)[targets[valid]]
                xs.append(x)
                ys.append(y if self.model_kind == "p3" else y - match)
        x = np.vstack(xs)
        y = np.concatenate(ys)
        assert len(y) >= 500 and np.isfinite(x).all() and np.isfinite(y).all()
        return x, y

    def fit(self, cutoff):
        if cutoff in self.cache:
            return self.cache[cutoff]
        x, y = self.training(cutoff)
        budget.price_fits += 1
        budget.check()
        started = time.perf_counter()
        if self.model_kind == "p3":
            scaler = None
            model = HistGradientBoostingRegressor(
                max_leaf_nodes=self.max_leaf_nodes, max_iter=100, learning_rate=0.05,
                min_samples_leaf=50, l2_regularization=1.0,
                early_stopping=False, random_state=2026,
            )
            with threadpool_limits(limits=1):
                model.fit(x, y)
            detail = {"max_leaf_nodes": self.max_leaf_nodes, "iterations": int(model.n_iter_),
                      "learning_rate": 0.05, "min_samples_leaf": 50}
        else:
            scaler = StandardScaler()
            z = scaler.fit_transform(x)
            model = Ridge(alpha=self.alpha)
            with threadpool_limits(limits=1):
                model.fit(z, y)
            original = model.coef_ / scaler.scale_
            detail = {
                "alpha": self.alpha,
                "coefficients_original": dict(zip(self.feature_names, original.astype(float))),
                "intercept_original": float(model.intercept_ - original @ scaler.mean_),
            }
        path = self.model_dir / f"cutoff-{cutoff:03d}.joblib"
        joblib.dump({"model": model, "scaler": scaler, "features": self.feature_names,
                     "model_kind": self.model_kind, "feature_mode": self.feature_mode}, path, compress=3)
        record = {
            "strategy": self.name, "branch": self.f.branch, "model_kind": self.model_kind,
            "feature_mode": self.feature_mode, "window": self.window, "cutoff_day": int(cutoff),
            "cutoff_datetime": q4.daystr(cutoff) + " 00:00", "latest_target_end": q4.daystr(cutoff) + " 00:00",
            "training_rows": int(len(y)), "feature_names": self.feature_names,
            "model_path": str(path.relative_to(R)), "model_sha256": sha(path),
            "seconds": time.perf_counter() - started, **detail,
        }
        logs.event("price_fit_log", record)
        self.cache[cutoff] = model, scaler
        budget.save()
        return self.cache[cutoff]

    def predict(self, day, release):
        targets, net = self.f.supply_forecast(day, release)
        cutoff = 7 + ((day - 7) // 7) * 7
        model, scaler = self.fit(cutoff)
        full = self.f.matrix(day, release, targets, net)
        x, match = self.transform(full)
        pred = model.predict(x if scaler is None else scaler.transform(x))
        if self.model_kind != "p3":
            pred = match + pred
        pred = np.maximum(pred, 0.001)
        logs.event("price_forecast_log", {
            "strategy": self.name, "branch": self.f.branch, "decision_day": int(day),
            "decision_date": q4.daystr(day), "release_slot": int(release),
            "known_price_intervals_today": int(release), "fit_cutoff_day": int(cutoff),
            "forecast_points": int(len(pred)),
            "sha256": hashlib.sha256(np.asarray(pred, dtype=np.float64).tobytes()).hexdigest(),
        })
        return pred
