"""
PSO + 局部精化求解烟幕遮蔽时长的完整脚本
- 先用 PSO（粗 dt）做全局搜索
- 再对 PSO 得到的最优点做局部网格精化（细 dt）
- 输出：最优参数、T_total；保存 CSV/JSON；绘图展示 chi(t) 与距离随时间的曲线

注意：如果在本地跑，请确保已安装 numpy, matplotlib, pandas（pip install numpy matplotlib pandas）。
在本 chat 的运行环境中，结果将保存到 /mnt/data。
"""
import numpy as np
import math
import json
import pandas as pd
import matplotlib.pyplot as plt
from time import time

# -------------------- 常量与初始位置 --------------------
g = 9.8  # 重力加速度 m/s^2

# 真实目标中心 (x,y,z)
P = np.array([0.0, 200.0, 5.0])

# 导弹初始状态
M10 = np.array([20000.0, 0.0, 2000.0])
vM = 300.0
dM = -M10 / np.linalg.norm(M10)  # 指向原点（假目标）
t_hit_origin = np.linalg.norm(M10) / vM  # 导弹到假目标（原点）的时间上界

# 无人机初始状态
F10 = np.array([17800.0, 0.0, 1800.0])

# 烟雾参数
smoke_effect_radius = 10.0  # 点遮蔽判定阈值（m）
cloud_descent_speed = 3.0   # 起爆后云团垂直下沉速度 m/s
cloud_lifetime = 20.0       # 起爆后有效时间 s
z_ground = 0.0

# 时间上界（取导弹撞击假目标的时间或更小的安全值）
t_max_global = min(t_hit_origin, 200.0)


# -------------------- 运动学函数 --------------------
def F_pos(t, v, theta):
    """无人机在时间 t 的位置（匀速水平）"""
    ux = math.cos(theta)
    uy = math.sin(theta)
    return F10 + np.array([v * t * ux, v * t * uy, 0.0])


def M_pos_array(t_arr):
    """导弹在时间数组 t_arr 上的位置（向量化）"""
    t_arr = np.asarray(t_arr)
    return M10.reshape((1, 3)) + np.outer(t_arr, vM * dM)


def smoke_trajectory_before_explosion(t_arr, t_r, v, theta):
    """
    烟弹在起爆前的轨迹（投放点为 F(t_r)，之后水平匀速、垂直自由落体）
    返回 shape (len(t_arr), 3)
    """
    t_arr = np.asarray(t_arr)
    release = F_pos(t_r, v, theta)
    dt = t_arr - t_r
    ux = math.cos(theta); uy = math.sin(theta)
    xs = release[0] + v * dt * ux
    ys = release[1] + v * dt * uy
    zs = release[2] - 0.5 * g * (dt ** 2)
    return np.vstack([xs, ys, zs]).T


def cloud_center_post_explosion(t_arr, t_e, x_e, y_e, z_e):
    """起爆后云心（仅竖直下沉）"""
    t_arr = np.asarray(t_arr)
    dt = t_arr - t_e
    zs = z_e - cloud_descent_speed * dt
    xs = np.full_like(zs, x_e)
    ys = np.full_like(zs, y_e)
    return np.vstack([xs, ys, zs]).T


# -------------------- χ(t) 计算函数 --------------------
def compute_T_total_for_params(theta, v, t_r, T_f, dt=0.05, return_timeseries=False):
    """
    给定参数计算遮蔽总时长 T_total（离散化时间步长 dt）。
    若 return_timeseries=True，返回 (T_total, t_samples, distances, chi_mask)
    否则只返回 T_total。
    """
    # 起爆时刻
    t_e = t_r + T_f
    # 若起爆在导弹撞击之后或超过全局上界，视为不可行
    if t_e >= t_max_global:
        if return_timeseries:
            return 0.0, None, None, None
        return 0.0

    # 起爆点（平抛阶段的轨迹值）
    pos_e = smoke_trajectory_before_explosion(np.array([t_e]), t_r, v, theta)[0]
    x_e, y_e, z_e = pos_e
    # 若起爆点低于地面，视为无效
    if z_e <= z_ground:
        if return_timeseries:
            return 0.0, None, None, None
        return 0.0

    # 云团存在时间 [t_e, min(t_e+cloud_lifetime, t_max_global)]
    t_end = min(t_e + cloud_lifetime, t_max_global)
    t_samples = np.arange(t_e, t_end + 1e-9, dt)
    if t_samples.size == 0:
        if return_timeseries:
            return 0.0, None, None, None
        return 0.0

    # 云心轨迹（起爆后）
    C = cloud_center_post_explosion(t_samples, t_e, x_e, y_e, z_e)
    valid_mask = C[:, 2] > z_ground  # 云心在地面以上

    # 导弹各时刻位置
    M = M_pos_array(t_samples)

    # 计算云心到导弹-目标线段的距离（向量化）
    AB = (P - M)  # shape (N,3)
    AP = C - M    # shape (N,3)
    denom = np.sum(AB * AB, axis=1)
    # 防止 denom=0（导弹到目标），用微小数替代
    denom_safe = np.where(denom < 1e-9, 1e-9, denom)
    t_param = np.sum(AP * AB, axis=1) / denom_safe
    t_param_clamped = np.clip(t_param, 0.0, 1.0)
    closest = M + (t_param_clamped[:, None] * AB)
    dists = np.linalg.norm(C - closest, axis=1)

    between_mask = (t_param >= 0.0) & (t_param <= 1.0)
    within_radius_mask = dists <= smoke_effect_radius

    chi_mask = valid_mask & between_mask & within_radius_mask

    T_total = chi_mask.sum() * dt

    if return_timeseries:
        return T_total, t_samples, dists, chi_mask
    return T_total


# -------------------- PSO 实现（最大化目标） --------------------
def pso_optimize(objective, bounds, swarm_size=40, iters=200,
                 w_max=0.9, w_min=0.4, c1=1.6, c2=1.6, seed=None, verbose=True):
    """
    简单 PSO（用于最大化 objective(x)）。
    - objective(x) -> scalar (越大越好)。x 为 1D numpy array。
    - bounds: [(low0, high0), (low1, high1), ...]
    返回最佳解 (gbest, gbest_val, history)
    """
    rng = np.random.default_rng(seed)
    d = len(bounds)
    lb = np.array([b[0] for b in bounds])
    ub = np.array([b[1] for b in bounds])

    # 初始化粒子位置与速度
    X = rng.uniform(lb, ub, size=(swarm_size, d))
    V = rng.uniform(-(ub - lb), (ub - lb), size=(swarm_size, d)) * 0.05

    # 评估初始粒子
    pbest = X.copy()
    pbest_val = np.array([objective(x) for x in X])

    # 全局最优
    gidx = int(np.argmax(pbest_val))
    gbest = pbest[gidx].copy()
    gbest_val = float(pbest_val[gidx])

    history = []
    for k in range(iters):
        w = w_max - (w_max - w_min) * (k / max(1, iters - 1))
        r1 = rng.random((swarm_size, d))
        r2 = rng.random((swarm_size, d))
        V = w * V + c1 * r1 * (pbest - X) + c2 * r2 * (gbest - X)
        X = X + V
        # 边界约束
        X = np.clip(X, lb, ub)

        vals = np.array([objective(x) for x in X])

        # 更新个体最优
        improved = vals > pbest_val
        if np.any(improved):
            pbest[improved] = X[improved].copy()
            pbest_val[improved] = vals[improved]

        # 更新全局最优
        idx = int(np.argmax(pbest_val))
        if pbest_val[idx] > gbest_val:
            gbest_val = float(pbest_val[idx])
            gbest = pbest[idx].copy()

        history.append(gbest_val)
        if verbose and ((k + 1) % 50 == 0 or k == 0 or (k + 1) == iters):
            print(f"[PSO] iter {k+1}/{iters}  gbest_val = {gbest_val:.6f}")

    return gbest, gbest_val, history


# -------------------- 主流程：PSO 搜索 + 局部精化 --------------------
def main():
    t0 = time()
    # 参数边界： theta (rad), v (m/s), t_r (s), T_f (s)
    bounds = [
        (0.0, 2 * math.pi),   # theta
        (70.0, 140.0),        # v
        (0.0, 3.0),           # t_r
        (0.1, 6.0)            # T_f (引信延时)
    ]

    # objective wrapper，用粗 dt（加速 PSO）
    dt_coarse = 0.1

    def objective_from_array(x):
        theta, v, t_r, T_f = float(x[0]), float(x[1]), float(x[2]), float(x[3])
        # 若不满足可行性（起爆晚于击中），compute_T_total_for_params 会返回 0
        val = compute_T_total_for_params(theta, v, t_r, T_f, dt=dt_coarse)
        return val

    print("Start PSO coarse search (dt = {:.3f}s)...".format(dt_coarse))
    swarm_size = 40
    iters = 200
    gbest, gbest_val, hist = pso_optimize(objective_from_array, bounds,
                                          swarm_size=swarm_size, iters=iters,
                                          w_max=0.9, w_min=0.4, c1=1.6, c2=1.6,
                                          seed=42, verbose=True)

    print("\nPSO coarse result:")
    print(" gbest (theta, v, t_r, T_f) =", gbest)
    print(" gbest_val (T_total coarse) =", gbest_val)

    # -------------------- 局部精化（在 gbest 附近做细网格搜索） --------------------
    theta0, v0, t_r0, T_f0 = float(gbest[0]), float(gbest[1]), float(gbest[2]), float(gbest[3])
    print("\nRefining around PSO best...")

    # 局部搜索窗口与步长（可调整）
    theta_grid = np.linspace(max(0.0, theta0 - 0.2), min(2 * math.pi, theta0 + 0.2), 25)
    v_grid = np.linspace(max(70.0, v0 - 10.0), min(140.0, v0 + 10.0), 11)
    t_r_grid = np.linspace(max(0.0, t_r0 - 0.5), t_r0 + 0.5, 21)
    T_f_grid = np.linspace(max(0.1, T_f0 - 0.8), T_f0 + 0.8, 21)

    best_local = {'T_total': -1.0}
    dt_fine = 0.01  # 精化时使用更细的时间步长

    total_iter = len(theta_grid) * len(v_grid) * len(t_r_grid) * len(T_f_grid)
    cnt = 0
    for theta in theta_grid:
        for v in v_grid:
            for t_r in t_r_grid:
                for T_f in T_f_grid:
                    cnt += 1
                    Tt = compute_T_total_for_params(theta, v, t_r, T_f, dt=dt_fine)
                    if Tt > best_local['T_total']:
                        best_local = {'T_total': Tt, 'theta': theta, 'v': v, 't_r': t_r, 'T_f': T_f}
        # optional progress print
        # print(f"Refine progress: theta index {np.where(theta_grid==theta)[0][0]}/{len(theta_grid)}")

    print("\nLocal refinement result:")
    print(best_local)

    # -------------------- 用最优参数计算时间序列并保存 --------------------
    best = best_local
    T_total_best, t_samples_best, dists_best, chi_mask_best = compute_T_total_for_params(
        best['theta'], best['v'], best['t_r'], best['T_f'], dt=dt_fine, return_timeseries=True)

    t_e_best = best['t_r'] + best['T_f']
    pos_e = smoke_trajectory_before_explosion(np.array([t_e_best]), best['t_r'], best['v'], best['theta'])[0]
    x_e, y_e, z_e = pos_e
    print("Total elapsed time: {:.2f} s".format(time() - t0))
    print("\n=== Final Result ===")
    print(f"T_total_max = {T_total_best:.3f} s")
    print(f"theta (rad) = {best['theta']:.6f}, theta (deg) = {np.degrees(best['theta']):.3f}")
    print(f"v = {best['v']:.3f} m/s")
    print(f"t_r = {best['t_r']:.3f} s")
    print(f"T_f = {best['T_f']:.3f} s")
    print(f"t_e = {t_e_best:.3f} s")
    print(f"explosion center = ({x_e:.3f}, {y_e:.3f}, {z_e:.3f}) m")
    print("====================")

    # 保存时间序列 CSV
    df = pd.DataFrame({
        'time': t_samples_best,
        'distance_to_segment': dists_best,
        'chi': chi_mask_best.astype(int)
    })
    csv_path = "results/chi_timeseries_pso_best.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved time series CSV to: {csv_path}")

    # 保存搜索 summary
    summary = {
        'T_total_max': float(T_total_best),
        'theta_rad': float(best['theta']),
        'theta_deg': float(np.degrees(best['theta'])),
        'v': float(best['v']),
        't_r': float(best['t_r']),
        'T_f': float(best['T_f']),
        't_e': float(t_e_best),
        'explosion_center': [float(x_e), float(y_e), float(z_e)]
    }
    json_path = "results/pso_search_summary.json"
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved search summary JSON to: {json_path}")

    # 绘图：chi(t)
    plt.figure(figsize=(9, 3.5))
    plt.plot(t_samples_best, chi_mask_best, linewidth=2)
    plt.xlabel("time (s)")
    plt.ylabel("chi(t) (1 = blocked)")
    plt.title("χ(t) over time for the PSO-refined best solution")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 绘图：distance to line
    plt.figure(figsize=(9, 3.5))
    plt.plot(t_samples_best, dists_best, linewidth=2)
    plt.axhline(smoke_effect_radius, linestyle='--', label=f"radius = {smoke_effect_radius} m")
    plt.xlabel("time (s)")
    plt.ylabel("distance from cloud center to missile-target segment (m)")
    plt.title("Distance-to-line over time (best solution)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    


if __name__ == "__main__":
    main()
