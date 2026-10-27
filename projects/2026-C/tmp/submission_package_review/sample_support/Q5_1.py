# -*- coding: utf-8 -*-
"""
修改点：
1) 注释掉 [Greedy] 的逐步打印；
2) 固定外层优化顺序为 [3,2,0,1,4]；
3) 在最终结果中保存“每枚导弹在每个时间点是否被遮挡(0/1)”并绘制折线图。
"""
import numpy as np
import matplotlib.pyplot as plt
import random

# ===================== 0. 参数区 =====================
# 目标与武器
TARGET = np.array([0.0, 200.0, 5.0])
MISSILE_SPEED = 300.0

# 云参数
R_CLOUD = 10.0
CLOUD_SINK_V = 3.0
CLOUD_TAU = 20.0

# 重力
G = 9.81
g_vec = np.array([0.0, 0.0, -G])

# 时间离散
DT = 0.2
RELEASE_DT = 1.0
FUSE_SET = np.arange(0.0, 10.0 + 1e-9, 0.5)  # 0..10 步长 0.5

# 投放约束
MAX_BOMBS_PER_DRONE = 3
MIN_GAP_SAME_DRONE = 1.0

# 外层速度与航向范围（硬边界）
V_LOWER, V_UPPER = 70.0, 140.0

# 外层搜索：先粗再细（5步长、±10邻域，适度减负以顺利跑完）
COARSE_V_SET = np.array([80.0,90,100.0,110.0,120.0,130.0,140.0])


COARSE_THETA_DEG = np.array([0,45, 90,135, 180, 225, 270, 315])
# 扩大范围
COARSE_V_SET = np.arange(80.0, 141.0, 5.0)
COARSE_THETA_DEG = np.arange(90.0, 451.0, 3.0)
V_FINE_OFFSETS = np.arange(-10.0, 10.0 + 1e-9, 5.0)
TH_FINE_OFFSETS_DEG = np.arange(-10.0, 10.0 + 1e-9, 5.0)

# 候选预筛：每机保留 Top-K（适度收敛计算量）
TOPK_PER_DRONE = 60

# 重叠收益系数
ALPHA_OVERLAP = 0.25

# 外层多轮设置（固定顺序）
MAX_OUTER_ROUNDS = 5
IMPROVE_TOL = 1e-3
FIXED_ORDER = [3, 2, 0, 1, 4]

# 角度约束（度）
THETA_BOUNDS_DEG = [
    (45.0, 315.0),   # FY0
    (175.0, 375.0),  # FY1
    (25.0, 160.0),   # FY2
    (180.0, 375.0),  # FY3
    (25.0, 175.0),   # FY4
]

# 初始条件（FY0 & M0）
FY0 = np.array([
    [17800.0,     0.0, 1800.0],
    [12000.0,  1400.0, 1400.0],
    [ 6000.0, -3000.0,  700.0],
    [11000.0,  2000.0, 1800.0],
    [13000.0, -2000.0, 1300.0],
], dtype=float)

M0 = np.array([
    [20000.0,     0.0, 2000.0],
    [19000.0,   600.0, 2100.0],
    [18000.0,  -600.0, 1900.0],
], dtype=float)

drone_init = FY0.copy()
missile_init = M0.copy()
N_DRONES = drone_init.shape[0]
M_MISSILES = missile_init.shape[0]


# ===================== 1. 工具函数 =====================
def unit(v, eps=1e-9):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(n, eps, None)

def wrap_deg(a):
    a2 = np.mod(a, 360.0)
    if a2 < 0: a2 += 360.0
    return a2

def in_bound_deg(theta_deg, lo, hi):
    t = wrap_deg(theta_deg)
    lo2 = wrap_deg(lo)
    span = hi - lo
    if span >= 360 - 1e-9:
        return True
    if hi <= 360 + 1e-9:
        if lo2 <= wrap_deg(hi):
            return lo2 - 1e-9 <= t <= wrap_deg(hi) + 1e-9
        else:
            return (t >= lo2 - 1e-9) or (t <= wrap_deg(hi) + 1e-9)
    else:
        hi2 = hi - 360.0
        return (t >= lo2 - 1e-9) or (t <= hi2 + 1e-9)

def clip_to_bounds_center(bounds_list):
    centers = []
    for (lo, hi) in bounds_list:
        span = hi - lo
        center = wrap_deg(lo + span / 2.0)
        centers.append(center)
    return np.array(centers)

def missile_trajectories(m_init, t_grid, speed=MISSILE_SPEED):
    M0 = m_init.copy()
    dir_to_origin = unit(-M0)  # 指向原点
    M = M0[:, None, :] + (speed * t_grid[None, :, None]) * dir_to_origin[:, None, :]
    vec_to_target = TARGET[None, None, :] - M
    Dist = np.linalg.norm(vec_to_target, axis=2)                           # (M, T)
    N_hat = vec_to_target / np.clip(Dist[..., None], 1e-12, None)          # (M, T, 3)
    return M, N_hat, Dist


def compute_horizon(m_init, speed=MISSILE_SPEED):
    dist = np.linalg.norm(m_init, axis=1)
    return float(np.max(dist / speed))

def drone_dir(theta_rad):
    return np.array([np.cos(theta_rad), np.sin(theta_rad), 0.0])

def explosion_point(P_release, V_release, fuse):
    return P_release + V_release * fuse + 0.5 * g_vec * (fuse ** 2)

def cloud_center_at(E, tau, t_sub):
    sink = np.array([0.0, 0.0, -CLOUD_SINK_V])
    return E[None, :] + (t_sub - tau)[:, None] * sink[None, :]


# ===================== 2. 候选生成（含 Top-K 预筛） =====================
def generate_candidates_for_drone(dr_idx, dr_init, v, theta_rad, t_grid, M, N_hat, Dist, topk=TOPK_PER_DRONE):
    Tn = len(t_grid)
    dir_vec = drone_dir(theta_rad)
    V_vec = v * dir_vec
    t_releases = np.arange(0.0, t_grid[-1] + 1e-9, RELEASE_DT)

    cands = []
    for t_rel in t_releases:
        P = dr_init + v * t_rel * dir_vec
        for fuse in FUSE_SET:
            tau = t_rel + fuse
            if tau > t_grid[-1]:           # 起爆晚于地平线
                continue

            E = explosion_point(P, V_vec, fuse)   # (x_e, y_e, z_e)
            if E[2] <= 0.0:                       # 起爆点不得在地面/地下
                continue

            # —— 关键：云团有效到“落地/20s到期/全局上限”的最早时刻 ——
            t_end = min(tau + CLOUD_TAU, tau + E[2] / CLOUD_SINK_V, t_grid[-1])
            if t_end <= tau:
                continue

            j0 = int(np.ceil(tau / DT))
            j1 = int(np.floor(t_end / DT))
            t_sub = t_grid[j0:j1 + 1]

            C = cloud_center_at(E, tau, t_sub)          # (len,3)
            M_sub = M[:, j0:j1 + 1, :]                  # (M,len,3)
            N_sub = N_hat[:, j0:j1 + 1, :]              # (M,len,3)
            Dist_sub = Dist[:, j0:j1 + 1]               # (M,len)

            delta = C[None, :, :] - M_sub               # (M,len,3)
            dot   = np.sum(delta * N_sub, axis=2)       # (M,len)  —— 投影长度
            delta2= np.sum(delta * delta, axis=2)       # (M,len)
            perp2 = delta2 - dot * dot                  # (M,len)

            # —— 线段判定：0 <= dot <= Dist_sub  （不是射线！）
            cond = (perp2 <= (R_CLOUD ** 2) + 1e-12) & (dot >= -1e-12) & (dot <= Dist_sub + 1e-12)

            mask = np.zeros((M_sub.shape[0], Tn), dtype=bool)
            mask[:, j0:j1 + 1] = cond

            score = float(np.count_nonzero(mask) * DT)
            if score <= 1e-12:
                continue

            cands.append({
                'drone': dr_idx,
                't_release': float(t_rel),
                'fuse': float(fuse),
                'tau': float(tau),
                'P': P.copy(),
                'V': V_vec.copy(),
                'E': E.copy(),
                'mask': mask,
                'score': score,
            })

    if not cands:
        return []
    cands.sort(key=lambda x: x['score'], reverse=True)
    kept = cands[:min(topk, len(cands))]
    print(f"    [Cand] 无人机#{dr_idx}: 原始{len(cands)} -> 预筛保留 {len(kept)} (Top-{topk})")
    return kept


# ===================== 3. 内层贪心选择（含重叠收益，已去掉逐步打印） =====================
def greedy_select(candidates, t_grid, alpha_overlap=ALPHA_OVERLAP, return_covered=False):
    if not candidates:
        return ([], 0.0, None) if return_covered else ([], 0.0)
    M = candidates[0]['mask'].shape[0]
    Tn = len(t_grid)
    covered = np.zeros((M, Tn), dtype=bool)
    chosen = []
    per_drone_count = {}
    per_drone_times = {}

    def conflict(dr, t_rel, per_times):
        for tr in per_times.get(dr, []):
            if abs(tr - t_rel) < MIN_GAP_SAME_DRONE - 1e-9:
                return True
        return False

    while True:
        best_idx = -1
        best_gain = 0.0
        for idx, c in enumerate(candidates):
            dr = c['drone']
            if per_drone_count.get(dr, 0) >= MAX_BOMBS_PER_DRONE:
                continue
            if conflict(dr, c['t_release'], per_drone_times):
                continue
            m = c['mask']
            new_cover = m & (~covered)
            overlap   = m & covered
            gain = (np.count_nonzero(new_cover) + alpha_overlap * np.count_nonzero(overlap)) * DT
            if gain > best_gain + 1e-12:
                best_gain = gain
                best_idx = idx
        if best_idx < 0 or best_gain <= 1e-12:
            break
        c = candidates.pop(best_idx)
        covered |= c['mask']
        dr = c['drone']
        per_drone_count[dr] = per_drone_count.get(dr, 0) + 1
        per_drone_times.setdefault(dr, []).append(c['t_release'])
        chosen.append(c)

    total_cover_time = float(np.count_nonzero(covered) * DT)
    if return_covered:
        return chosen, total_cover_time, covered
    else:
        return chosen, total_cover_time


# ===================== 4. 外层评估和合并 =====================
def build_candidates_for_all(v_list, theta_list, t_grid, M, N_hat, Dist , topk=TOPK_PER_DRONE):
    per_drone_cands = []
    total = 0
    for i in range(N_DRONES):
        c_i = generate_candidates_for_drone(i, drone_init[i], v_list[i], theta_list[i], t_grid, M, N_hat, Dist, topk=topk)
        total += len(c_i)
        per_drone_cands.append(c_i)
    print(f"[Eval] 候选（预筛后）总数={total}")
    all_cands = [c for L in per_drone_cands for c in L]
    chosen, tot = greedy_select(all_cands, t_grid, alpha_overlap=ALPHA_OVERLAP, return_covered=False)
    return per_drone_cands, chosen, tot

def merge_and_eval(per_drone_cands_fixed, cand_i_new, t_grid):
    all_cands = []
    target_idx = cand_i_new[0]['drone'] if len(cand_i_new) > 0 else None
    for j, L in enumerate(per_drone_cands_fixed):
        if target_idx is not None and j == target_idx:
            all_cands.extend(cand_i_new)
        else:
            all_cands.extend(L)
    chosen, tot = greedy_select(all_cands, t_grid, alpha_overlap=ALPHA_OVERLAP, return_covered=False)
    return chosen, tot


# ===================== 5. 单轮（粗+细）坐标优化（带角度约束过滤） =====================
def one_round_coord(v_init, th_init, t_grid, M, N_hat,Dist, order=None):
    N = len(v_init)
    v_best = v_init.copy()
    th_best = th_init.copy()

    print("[Round] 构建初始候选并评估...")
    per_cands, chosen, best_tot = build_candidates_for_all(v_best, th_best, t_grid, M, N_hat,Dist, topk=TOPK_PER_DRONE)
    print(f"[Round] 初始总遮蔽={best_tot:.2f}s（去重），弹数={len(chosen)}\n")

    # 固定顺序
    idxs = order[:] if order is not None else list(range(N))

    # 粗搜
    print(f"[Round-粗] 顺序：{idxs}")
    for i in idxs:
        lo_deg, hi_deg = THETA_BOUNDS_DEG[i]
        print(f"[Round-粗] 优化无人机#{i} (θ∈[{lo_deg},{hi_deg}]°)")
        local_best = best_tot
        best_v_i, best_th_i = v_best[i], th_best[i]
        for v in COARSE_V_SET:
            for th_deg in COARSE_THETA_DEG:
                if not in_bound_deg(th_deg, lo_deg, hi_deg):
                    continue
                th = np.deg2rad(wrap_deg(th_deg))
                cand_i = generate_candidates_for_drone(i, drone_init[i], v, th, t_grid, M, N_hat,Dist, topk=TOPK_PER_DRONE)
                chosen_try, tot_try = merge_and_eval(per_cands, cand_i, t_grid)
                print(f"    尝试 v={v:.1f}, θ={th_deg:6.1f}° -> 遮蔽={tot_try:.2f}s")
                if tot_try > local_best + 1e-6:
                    local_best = tot_try
                    best_v_i, best_th_i = v, th
                    best_chosen = chosen_try
                    best_cand_i = cand_i
        if local_best > best_tot + 1e-6:
            v_best[i], th_best[i] = best_v_i, best_th_i
            per_cands[i] = best_cand_i
            chosen, best_tot = best_chosen, local_best
            print(f"[Round-粗] 采纳 无人机#{i} -> v={best_v_i:.1f}, θ={np.rad2deg(best_th_i):.1f}°，"
                  f"总遮蔽={best_tot:.2f}s\n")
        else:
            print(f"[Round-粗] 无人机#{i} 未改进，保持 v={v_best[i]:.1f}, θ={np.rad2deg(th_best[i]):.1f}°\n")

    # 细搜
    print(f"[Round-细] 顺序：{idxs}")
    for i in idxs:
        lo_deg, hi_deg = THETA_BOUNDS_DEG[i]
        print(f"[Round-细] 细化无人机#{i} (θ∈[{lo_deg},{hi_deg}]°)")
        local_best = best_tot
        best_v_i, best_th_i = v_best[i], th_best[i]
        v_center, th_center = v_best[i], th_best[i]
        center_deg = wrap_deg(np.rad2deg(th_center))
        for dv in V_FINE_OFFSETS:
            v = np.clip(v_center + dv, V_LOWER, V_UPPER)
            for dth_deg in TH_FINE_OFFSETS_DEG:
                th_deg = center_deg + dth_deg
                if not in_bound_deg(th_deg, lo_deg, hi_deg):
                    continue
                th = np.deg2rad(wrap_deg(th_deg))
                cand_i = generate_candidates_for_drone(i, drone_init[i], v, th, t_grid, M, N_hat,Dist, topk=TOPK_PER_DRONE)
                chosen_try, tot_try = merge_and_eval(per_cands, cand_i, t_grid)
                print(f"    尝试 v={v:.1f}, θ={th_deg:6.1f}° -> 遮蔽={tot_try:.2f}s")
                if tot_try > local_best + 1e-6:
                    local_best = tot_try
                    best_v_i, best_th_i = v, th
                    best_chosen = chosen_try
                    best_cand_i = cand_i
        if local_best > best_tot + 1e-6:
            v_best[i], th_best[i] = best_v_i, best_th_i
            per_cands[i] = best_cand_i
            chosen, best_tot = best_chosen, local_best
            print(f"[Round-细] 采纳 无人机#{i} -> v={best_v_i:.1f}, θ={np.rad2deg(best_th_i):.1f}°，"
                  f"总遮蔽={best_tot:.2f}s\n")
        else:
            print(f"[Round-细] 无人机#{i} 未改进，保持 v={v_best[i]:.1f}, θ={np.rad2deg(th_best[i]):.1f}°\n")

    # 最终评估一遍（这次返回 covered 用于画图）
    all_cands = [c for L in per_cands for c in L]
    chosen, best_tot, covered = greedy_select(all_cands, t_grid, alpha_overlap=ALPHA_OVERLAP, return_covered=True)
    return v_best, th_best, chosen, best_tot, covered


# ===================== 6. 外层多轮主控（固定顺序 3,2,0,1,4） =====================
def outer_optimize_multi(t_grid, M, N_hat,Dist, max_rounds=MAX_OUTER_ROUNDS, tol=IMPROVE_TOL):
    N = N_DRONES
    th0_deg = clip_to_bounds_center(THETA_BOUNDS_DEG)
    v_best = np.full(N, 110.0)
    th_best = np.deg2rad(th0_deg)

    print("========== 外层多轮优化（固定顺序 3,2,0,1,4）开始 ==========")
    order = None
    v_best, th_best, chosen, best_tot, covered = one_round_coord(v_best, th_best, t_grid, M, N_hat,Dist, order=order)
    print(f"[Multi] 结束第 1 轮：遮蔽={best_tot:.2f}s\n")

    for r in range(2, max_rounds + 1):
        prev = best_tot
        print(f"========== 第 {r} 轮（顺序 {order}） ==========")
        v_best, th_best, chosen, best_tot, covered = one_round_coord(v_best, th_best, t_grid, M, N_hat,Dist, order=order)
        improve = best_tot - prev
        print(f"[Multi] 本轮提升：{improve:.4f}s，累计最优遮蔽={best_tot:.2f}s\n")
        if improve <= tol:
            print(f"[Multi] 改进 ({improve:.4f}s) ≤ tol ({tol}), 提前停止。")
            break

    return v_best, th_best, chosen, best_tot, covered


# ===================== 7. 主流程（并绘制遮蔽0/1折线图） =====================
def main():
    T_end = compute_horizon(missile_init, MISSILE_SPEED)
    t_grid = np.arange(0.0, T_end + 1e-9, DT)

    print("========== 参数 & 角度约束 ==========")
    print(f"alpha_overlap = {ALPHA_OVERLAP}, TopK={TOPK_PER_DRONE}, 多轮上限={MAX_OUTER_ROUNDS}")
    print(f"固定优化顺序：{FIXED_ORDER}")
    print("Angle bounds per drone (deg):")
    for i, (lo, hi) in enumerate(THETA_BOUNDS_DEG):
        print(f"  d{i}: [{lo}, {hi}]")
    print("====================================\n")

    M, N_hat, Dist = missile_trajectories(missile_init, t_grid)

    v_best, th_best, chosen, best_tot, covered = outer_optimize_multi(t_grid, M, N_hat, Dist)

    print("\n========== 最终结果 ==========")
    for i in range(N_DRONES):
        print(f"无人机#{i}: v={v_best[i]:.1f} m/s, θ={np.rad2deg(th_best[i]):.1f}°")
    print(f"总遮蔽时长（去重统计）：{best_tot:.2f} s")
    print(f"选中干扰弹数：{len(chosen)}")

    for k, c in enumerate(chosen, 1):
        E = c['E']
        print(f"  弹#{k}: 无人机#{c['drone']}, 释放t={c['t_release']:.2f}s, 引信={c['fuse']:.2f}s, "
              f"起爆t={c['tau']:.2f}s, 起爆点E=({E[0]:.2f}, {E[1]:.2f}, {E[2]:.2f})")

    # 保存遮蔽0/1矩阵（missiles × time）
    blocked01 = covered.astype(int)  # shape (M, Tn)
    np.save('/mnt/data/blocked01.npy', blocked01)
    np.save('/mnt/data/t_grid.npy', t_grid)
    print(f"已保存遮蔽矩阵 blocked01.npy 和时间轴 t_grid.npy；矩阵形状={blocked01.shape}。")

    # 绘制折线图（每枚导弹一条 0/1 曲线）
    plt.figure(figsize=(10, 4))
    for m in range(blocked01.shape[0]):
        plt.plot(t_grid, (m+1)*blocked01[m], label=f"Missile #{m}")
    plt.yticks([0, 1])
    plt.xlabel("Time (s)")
    plt.ylabel("Blocked (0/1)")
    plt.title("Missile Blocked State Over Time (Final Plan)")
    plt.grid(True, linestyle=':')
    plt.legend(loc='best', fontsize=8, ncol=blocked01.shape[0])
    plt.tight_layout()
    plt.show()

    print("如需下载：")
    print("[Blocked Matrix] blocked01.npy ->", "sandbox:/mnt/data/blocked01.npy")
    print("[Time Grid]      t_grid.npy     ->", "sandbox:/mnt/data/t_grid.npy")

if __name__ == "__main__":
    main()
