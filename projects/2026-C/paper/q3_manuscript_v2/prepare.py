"""Prepare tables and figures from saved, verified Q3 results. No fitting or optimization."""
from pathlib import Path
import argparse, hashlib, json, shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
BASE = PROJECT / "questions/Q3/runs/20260911-four-candidates-v1"
PARAM = PROJECT / "questions/Q3/runs/20260911-parameter-interpretability-v1"
Q2 = PROJECT / "questions/Q2/runs/20260911-annual-validation-v1/delivery_data/summary.json"
SELECTED = "M_q60_b070_w28_h03"

plt.rcParams.update({
    "font.family": "SimSun", "font.size": 10, "axes.unicode_minus": False,
    "text.color": "black", "axes.labelcolor": "black", "xtick.color": "black",
    "ytick.color": "black", "pdf.fonttype": 42, "axes.spines.top": False,
    "axes.spines.right": False, "axes.axisbelow": True, "savefig.facecolor": "white"
})
BLUE, GREEN, ORANGE, RED, GREY = "#386a94", "#5f8768", "#c39243", "#b34e4a", "#777777"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tex_row(values):
    return " & ".join(values) + r" \\" + "\n"


def number(value):
    """Format displayed values without negative zero from solver tolerance."""
    value = float(value)
    if abs(value) < 5e-9:
        value = 0.0
    return f"{value:.2f}"


def interval_label(slot):
    start = slot * 10
    end = start + 10
    return f"{start//60:02d}:{start%60:02d}--{end//60:02d}:{end%60:02d}"


def contiguous_emergencies(values, price):
    positive = np.flatnonzero(values > 1e-8)
    if len(positive) == 0:
        return []
    groups, start, previous = [], int(positive[0]), int(positive[0])
    for current in positive[1:]:
        current = int(current)
        if current != previous + 1:
            groups.append((start, previous + 1))
            start = current
        previous = current
    groups.append((start, previous + 1))
    result = []
    for start, end in groups:
        kwh = float(values[start:end].sum())
        cost = float((5 * price[start:end] * values[start:end]).sum())
        end_minute = end * 10
        result.append((f"{start*10//60:02d}:{start*10%60:02d}--{end_minute//60:02d}:{end_minute%60:02d}", kwh, cost))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    out = args.output.resolve()
    figures = out / "figures"
    tables = out / "tables"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    source_paths = [
        BASE / "outputs/summary.json", BASE / "outputs/verification.json",
        BASE / "outputs/sources.npz", BASE / "interpretation/findings.json",
        BASE / "figures-v1/02_information_value.pdf",
        PARAM / "outputs/summary.json", PARAM / "outputs/verification.json",
        PARAM / f"outputs/strategies/{SELECTED}.npz",
        PARAM / f"outputs/strategies/{SELECTED}.daily.csv",
        PARAM / "figures-v1/01_parameter_interpretability.pdf", Q2
    ]
    fingerprints = {str(path.relative_to(PROJECT)): sha(path) for path in source_paths}
    guard = HERE / "source_manifest.json"
    if guard.exists():
        assert read_json(guard)["source_sha256"] == fingerprints, "Q3 writing source changed"
    else:
        guard.write_text(json.dumps({"scope": "read verified Q3 results only", "source_sha256": fingerprints}, ensure_ascii=False, indent=2), encoding="utf-8")

    base_summary = read_json(BASE / "outputs/summary.json")
    param_summary = read_json(PARAM / "outputs/summary.json")
    assert read_json(BASE / "outputs/verification.json")["status"] == "checks_completed"
    assert read_json(PARAM / "outputs/verification.json")["status"] == "checks_completed"
    selected = param_summary["winner"]
    assert selected["label"] == SELECTED

    trace = dict(np.load(PARAM / selected["trace"]))
    sources = dict(np.load(BASE / "outputs/sources.npz"))
    price, actual = sources["price"], sources["actual"]
    days = trace["days"].astype(int)
    q0, versions, execution = trace["q0"], trace["versions"], trace["execution"]
    qf = versions[:, 3]
    assert np.array_equal(days, np.arange(31, 365))
    dates = pd.to_datetime("2025-01-01") + pd.to_timedelta(days, unit="D")
    daily = pd.read_csv(PARAM / selected["daily_csv"], float_precision="round_trip")
    daily["date"] = pd.to_datetime(daily.date)
    daily["month"] = daily.date.dt.month

    annual_records = {row["label"]: row for row in base_summary["annual"]}
    candidate_rows = [
        ("直接采用官方预报", annual_records["S1_raw"]),
        ("历史误差融合预报", annual_records["S2_fused"]),
        ("提升树修正预报", annual_records["S3_tree"]),
        ("融合预报并增加近期误差准备", selected)
    ]
    candidate_tex = ""
    for name, record in candidate_rows:
        values = [name] + [f'{record[key]/1e4:.2f}' for key in ("ordinary_cost", "emergency_cost", "total_cost")] + [str(record["emergency_days"])]
        if name.startswith("融合预报并"):
            values = [r"\textbf{" + values[0] + "}"] + [r"\textbf{" + value + "}" for value in values[1:]]
        candidate_tex += tex_row(values)
    (tables / "candidates.tex").write_text(candidate_tex, encoding="utf-8")

    chosen_dates = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
    slot_map = {str(date.date()): i for i, date in enumerate(dates)}
    display_slots = [60, 72, 84, 96, 108, 120]
    original_body = adjusted_body = ""
    for slot in display_slots:
        original_body += tex_row([interval_label(slot)] + [number(q0[slot_map[date], slot]) for date in chosen_dates])
        adjusted_body += tex_row([interval_label(slot)] + [number(qf[slot_map[date], slot]) for date in chosen_dates])
    for label, getter in [
        ("全天原计划购电量", lambda i: q0[i].sum()),
        ("全天最终普通订单", lambda i: qf[i].sum()),
        ("全天紧急购电量", lambda i: execution[i,:,8].sum()),
        ("普通结算费用 / 元", lambda i: (price*qf[i] + .5*price*np.abs(qf[i]-q0[i])).sum()),
        ("紧急购电费用 / 元", lambda i: (5*price*execution[i,:,8]).sum()),
        ("全天总费用 / 元", lambda i: (price*qf[i] + .5*price*np.abs(qf[i]-q0[i]) + 5*price*execution[i,:,8]).sum())
    ]:
        adjusted_body += tex_row([label] + [number(getter(slot_map[date])) for date in chosen_dates])
    (tables / "original_orders.tex").write_text(original_body, encoding="utf-8")
    (tables / "adjusted_orders.tex").write_text(adjusted_body, encoding="utf-8")

    storage_body = ""
    for block in range(6):
        start, end = block*24, (block+1)*24
        label = f"{start//6:02d}:00--{end//6:02d}:00"
        for field, text in [((5,6), "充电"), ((7,), "放电")]:
            values = []
            for date in chosen_dates:
                i = slot_map[date]
                values.append(float(execution[i,start:end,list(field)].sum()))
            storage_body += tex_row([label if text == "充电" else "", text] + [number(value) for value in values])
    storage_body += tex_row([r"\multicolumn{2}{l}{0:00内部储电量}"] + [number(execution[slot_map[date],0,0]) for date in chosen_dates])
    storage_body += tex_row([r"\multicolumn{2}{l}{24:00内部储电量}"] + [number(execution[slot_map[date],-1,1]) for date in chosen_dates])
    (tables / "storage.tex").write_text(storage_body, encoding="utf-8")

    emergency_body = ""
    emergency_rows = []
    for date in chosen_dates:
        i = slot_map[date]
        groups = contiguous_emergencies(execution[i,:,8], price)
        if not groups:
            emergency_body += tex_row([date[5:].replace("-", "/"), "无紧急购电", "0.00", "0.00"])
            emergency_rows.append({"date": date, "interval": "无紧急购电", "kwh": 0.0, "cost": 0.0})
        else:
            for j, (label, kwh, cost) in enumerate(groups):
                emergency_body += tex_row([date[5:].replace("-", "/") if j == 0 else "", label, f"{kwh:.2f}", f"{cost:.2f}"])
                emergency_rows.append({"date": date, "interval": label, "kwh": kwh, "cost": cost})
    (tables / "emergency.tex").write_text(emergency_body, encoding="utf-8")

    # Final monthly performance, with initial fused strategy as the paired reference.
    initial_record = annual_records["S2_fused"]
    initial_daily = pd.read_csv(BASE / initial_record["daily_csv"], float_precision="round_trip")
    initial_daily["date"] = pd.to_datetime(initial_daily.date)
    merged = daily.merge(initial_daily[["date", "total_cost"]], on="date", suffixes=("_final", "_initial"))
    merged["saving"] = merged.total_cost_initial - merged.total_cost_final
    monthly = daily.groupby("month")[["ordinary_cost", "emergency_cost", "total_cost"]].sum()
    saving = merged.assign(month=merged.date.dt.month).groupby("month").saving.sum().reindex(monthly.index)
    fig, axes = plt.subplots(2, 1, figsize=(7.3, 4.4), sharex=True, gridspec_kw={"height_ratios": [1.4, 1]})
    axes[0].bar(monthly.index, monthly.ordinary_cost/1e4, color=BLUE, width=.63, label="普通结算")
    axes[0].bar(monthly.index, monthly.emergency_cost/1e4, bottom=monthly.ordinary_cost/1e4, color=ORANGE, width=.63, label="紧急购电")
    axes[0].set_ylabel("最终方案费用 / 万元")
    axes[0].legend(frameon=False, ncol=2, loc="upper left")
    axes[1].bar(monthly.index, saving/1e4, color=np.where(saving >= 0, GREEN, ORANGE), width=.63)
    axes[1].axhline(0, color="black", linewidth=.7)
    axes[1].set(xlabel="月份", ylabel="相对初始融合方案节省 / 万元", xticks=monthly.index)
    for axis in axes:
        axis.grid(axis="y", alpha=.17)
    fig.tight_layout()
    generated = []
    for extension in ("pdf", "png"):
        path = figures / f"final_monthly.{extension}"
        kwargs = {"metadata": {"CreationDate": None, "ModDate": None}} if extension == "pdf" else {}
        fig.savefig(path, dpi=300, bbox_inches="tight", **kwargs)
        generated.append(path)
    plt.close(fig)
    pd.DataFrame({"month": monthly.index, "ordinary_cost": monthly.ordinary_cost, "emergency_cost": monthly.emergency_cost, "saving": saving}).to_csv(figures / "final_monthly_input.csv", index=False)

    # Two specified dates: the largest emergency amount and the smallest among the four.
    specified_amounts = {date: float(execution[slot_map[date],:,8].sum()) for date in chosen_dates}
    high = max(chosen_dates, key=lambda date: specified_amounts[date])
    low = min(chosen_dates, key=lambda date: specified_amounts[date])
    plot_dates = [high, low] if high != low else chosen_dates[:2]
    fig, axes = plt.subplots(3, 2, figsize=(7.3, 5.8), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1]})
    for column, date in enumerate(plot_dates):
        i, day = slot_map[date], int(days[slot_map[date]])
        truth = actual[day*144:day*144+144]
        x = np.arange(144)/6
        axes[0,column].step(x, truth[:,0], where="post", color="black", linewidth=1, label="实际负载")
        axes[0,column].step(x, truth[:,1], where="post", color=GREEN, linewidth=1.1, label="实际光伏")
        axes[0,column].step(x, q0[i]*6, where="post", color=GREY, linewidth=.8, linestyle="--", label="零点订单")
        axes[0,column].step(x, qf[i]*6, where="post", color=BLUE, linewidth=1, label="最终订单")
        axes[0,column].set_title(date[5:].replace("-", "月") + "日", fontsize=11)
        state = np.r_[execution[i,0,0], execution[i,:,1]]
        axes[1,column].plot(np.arange(145)/6, state, color=BLUE, linewidth=1.2)
        for bound in (1200, 10800):
            axes[1,column].axhline(bound, color=GREY, linestyle="--", linewidth=.7)
        axes[1,column].set(ylim=(0,12000), yticks=[1200,6000,10800])
        gap = np.maximum((truth[:,0]-truth[:,1])/6-qf[i], 0)
        axes[2,column].fill_between(x, gap, step="post", color="#dddddd", label="普通电后的缺口")
        axes[2,column].step(x, execution[i,:,7], where="post", color=BLUE, linewidth=1, label="电池补充")
        axes[2,column].bar(x, execution[i,:,8], width=1/6, align="edge", color=RED, label="紧急购电")
        axes[2,column].set(xlim=(0,24), xticks=np.arange(0,25,4), xlabel="时刻 / h")
        for axis in axes[:,column]:
            axis.grid(axis="y", alpha=.15)
    axes[0,0].set_ylabel("功率 / kW")
    axes[1,0].set_ylabel("内部储电量 / kWh")
    axes[2,0].set_ylabel("每10分钟电量 / kWh")
    axes[0,0].legend(loc="upper left", ncol=2, fontsize=8, frameon=False, columnspacing=.8)
    axes[2,0].legend(loc="upper left", ncol=2, fontsize=8, frameon=False, columnspacing=.8)
    fig.tight_layout(h_pad=1, w_pad=1)
    for extension in ("pdf", "png"):
        path = figures / f"specified_days.{extension}"
        kwargs = {"metadata": {"CreationDate": None, "ModDate": None}} if extension == "pdf" else {}
        fig.savefig(path, dpi=300, bbox_inches="tight", **kwargs)
        generated.append(path)
    plt.close(fig)

    copy_sources = {
        "information_value": BASE / "figures-v1/02_information_value",
        "parameter_interpretability": PARAM / "figures-v1/01_parameter_interpretability"
    }
    for name, source in copy_sources.items():
        for extension in ("pdf", "png"):
            destination = figures / f"{name}.{extension}"
            shutil.copy2(source.with_suffix(f".{extension}"), destination)
            generated.append(destination)

    initial_fused = annual_records["S2_fused"]
    q2 = read_json(Q2)
    selected_days = daily.set_index(daily.date.dt.strftime("%Y-%m-%d"))
    findings = {
        "selected": selected,
        "initial_fused": initial_fused,
        "saving_vs_initial_fused": initial_fused["total_cost"] - selected["total_cost"],
        "ordinary_change_vs_initial_fused": selected["ordinary_cost"] - initial_fused["ordinary_cost"],
        "emergency_saving_vs_initial_fused": initial_fused["emergency_cost"] - selected["emergency_cost"],
        "emergency_kwh_reduction_pct": (initial_fused["emergency_kwh"]-selected["emergency_kwh"])/initial_fused["emergency_kwh"]*100,
        "saving_vs_q2": q2["total_official_cost"] - selected["total_cost"],
        "cheaper_months_vs_initial": int((saving > 0).sum()),
        "dearer_months_vs_initial": int((saving < 0).sum()),
        "cheaper_days_vs_initial": int((merged.saving > 1e-6).sum()),
        "dearer_days_vs_initial": int((merged.saving < -1e-6).sum()),
        "equal_days_vs_initial": int((merged.saving.abs() <= 1e-6).sum()),
        "best_day_vs_initial": merged.loc[merged.saving.idxmax(), ["date", "saving"]].astype(str).to_dict(),
        "worst_day_vs_initial": merged.loc[merged.saving.idxmin(), ["date", "saving"]].astype(str).to_dict(),
        "specified_emergency_kwh": specified_amounts,
        "plotted_dates": plot_dates,
        "specified_daily": {date: selected_days.loc[date, ["ordinary_cost", "emergency_cost", "total_cost", "emergency_kwh"]].to_dict() for date in chosen_dates},
        "emergency_rows": emergency_rows,
        "information_value": read_json(BASE / "interpretation/findings.json")["information_value"]
    }
    (out / "paper_findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    manifest = {
        "scope": "render saved verified results only; no fitting, optimization, or simulation",
        "source_sha256": fingerprints,
        "script_sha256": sha(__file__),
        "matplotlib": matplotlib.__version__, "font": "SimSun", "dpi": 300,
        "outputs": {str(path.relative_to(out)): sha(path) for path in generated}
    }
    (figures / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "figures": len(generated), "plotted_dates": plot_dates, "specified_emergency": specified_amounts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
